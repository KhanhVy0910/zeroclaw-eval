"""Deterministic Fault Injection engine for Hardware Gateway."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from gateway.backend.base import (
    GatewayConnectionError,
    GatewayDeviceError,
    GatewayError,
    GatewayExecutionError,
    GatewayInvalidArgumentError,
    GatewaySafetyViolationError,
)


class FaultType(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    LATENCY_MS = "LATENCY_MS"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    STALE_VALUE = "STALE_VALUE"
    ABNORMAL_VALUE = "ABNORMAL_VALUE"
    ERROR_RESPONSE = "ERROR_RESPONSE"


@dataclass
class FaultRule:
    fault_type: FaultType
    node_id: str = "*"  # "*" means any node
    action: str = "*"   # "*" means any action
    params: Dict[str, Any] = field(default_factory=dict)
    trigger_count: Optional[int] = None  # None = infinite, >0 = count down
    active: bool = True
    executions: int = 0


class FaultInjector:
    """Manages deterministic fault injection rules and intercepts requests/responses."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self._rng = random.Random(seed)
        self.rules: List[FaultRule] = []

    def set_seed(self, seed: int) -> None:
        """Reset RNG with fixed seed for determinism."""
        self.seed = seed
        self._rng = random.Random(seed)

    def add_rule(
        self,
        fault_type: str | FaultType,
        node_id: str = "*",
        action: str = "*",
        params: Optional[Dict[str, Any]] = None,
        trigger_count: Optional[int] = None,
    ) -> FaultRule:
        """Add a fault injection rule."""
        if isinstance(fault_type, str):
            fault_type = FaultType(fault_type.upper())
        rule = FaultRule(
            fault_type=fault_type,
            node_id=node_id,
            action=action,
            params=params or {},
            trigger_count=trigger_count,
        )
        self.rules.append(rule)
        return rule

    def clear(self) -> None:
        """Clear all active fault injection rules."""
        self.rules.clear()
        self.set_seed(self.seed)

    def list_rules(self) -> List[Dict[str, Any]]:
        """List active rules."""
        return [
            {
                "fault_type": r.fault_type.value,
                "node_id": r.node_id,
                "action": r.action,
                "params": r.params,
                "trigger_count": r.trigger_count,
                "active": r.active,
                "executions": r.executions,
            }
            for r in self.rules
        ]

    def _matches(self, rule: FaultRule, node_id: str, action: str) -> bool:
        if not rule.active:
            return False
        if rule.trigger_count is not None and rule.trigger_count <= 0:
            return False
        if rule.node_id != "*" and rule.node_id != node_id:
            return False
        if rule.action != "*" and rule.action != action:
            return False
        return True

    def _consume_trigger(self, rule: FaultRule) -> None:
        rule.executions += 1
        if rule.trigger_count is not None:
            rule.trigger_count -= 1
            if rule.trigger_count <= 0:
                rule.active = False

    async def check_pre_execution(self, node_id: str, action: str) -> None:
        """Check and apply faults before action execution (DISCONNECTED, LATENCY_MS, ERROR_RESPONSE)."""
        for rule in list(self.rules):
            if not self._matches(rule, node_id, action):
                continue

            if rule.fault_type == FaultType.LATENCY_MS:
                latency_ms = float(rule.params.get("latency_ms", 100))
                self._consume_trigger(rule)
                await asyncio.sleep(latency_ms / 1000.0)

            elif rule.fault_type == FaultType.DISCONNECTED:
                self._consume_trigger(rule)
                msg = rule.params.get("message", f"Node '{node_id}' disconnected / unreachable")
                raise GatewayConnectionError(msg)

            elif rule.fault_type == FaultType.ERROR_RESPONSE:
                self._consume_trigger(rule)
                code = rule.params.get("code", "EXECUTION_ERROR")
                msg = rule.params.get("message", "Simulated error response")
                if code == "CONNECTION_ERROR":
                    raise GatewayConnectionError(msg)
                elif code == "DEVICE_ERROR":
                    raise GatewayDeviceError(msg)
                elif code == "INVALID_ARGUMENT":
                    raise GatewayInvalidArgumentError(msg)
                elif code == "SAFETY_VIOLATION":
                    raise GatewaySafetyViolationError(msg)
                else:
                    raise GatewayExecutionError(msg)

    def check_post_execution(
        self, node_id: str, action: str, data: Dict[str, Any]
    ) -> Dict[str, Any] | str:
        """Check and mutate action result (MALFORMED_RESPONSE, STALE_VALUE, ABNORMAL_VALUE)."""
        result = dict(data) if isinstance(data, dict) else data

        for rule in list(self.rules):
            if not self._matches(rule, node_id, action):
                continue

            if rule.fault_type == FaultType.MALFORMED_RESPONSE:
                self._consume_trigger(rule)
                return rule.params.get("raw_text", "MALFORMED_RAW_RESPONSE_PARSE_ERROR_0xDEAD")

            elif rule.fault_type == FaultType.STALE_VALUE:
                self._consume_trigger(rule)
                stale_data = rule.params.get("stale_data", {"stale": True, "value": "FROZEN_READING"})
                return stale_data

            elif rule.fault_type == FaultType.ABNORMAL_VALUE:
                self._consume_trigger(rule)
                field_name = rule.params.get("field", "temperature")
                abnormal_val = rule.params.get("value", 999.9)
                if isinstance(result, dict):
                    result[field_name] = abnormal_val
                return result

        return result
