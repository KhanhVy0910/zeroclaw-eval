"""Deterministic Fault Injection Engine for Mock Node.

All stochastic behaviors are driven by Python's random.Random with a deterministic seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FaultType(str, Enum):
    """Supported fault injection categories."""

    NONE = "none"
    DISCONNECTION = "disconnection"  # Drops connection / no response
    LATENCY = "latency"  # Injects fixed delay in seconds
    MALFORMED_RESPONSE = "malformed_response"  # Returns corrupt / non-JSON line
    STALE_OR_ABNORMAL_VALUE = "stale_or_abnormal_value"  # Returns outdated or out-of-range value
    ERROR_RESPONSE = "error_response"  # Returns valid JSON protocol error


@dataclass
class FaultConfig:
    """Configuration for deterministic fault injection."""

    fault_type: FaultType = FaultType.NONE
    target_cmd: str | None = None  # If set, only triggers when cmd matches
    target_pin: int | None = None  # If set, only triggers when args.pin matches
    delay_seconds: float = 0.0
    error_message: str = "Hardware fault simulated"
    malformed_payload: str = "CORRUPT_FRAME_{id}_NOT_JSON\n"
    abnormal_value: str = "999"
    trigger_after_count: int = 0  # Trigger only after N requests
    trigger_max_times: int | None = None  # Trigger at most M times
    probability: float = 1.0  # 1.0 = always trigger when conditions match
    seed: int = 42


@dataclass
class FaultDecision:
    """Result of assessing whether a fault should be injected for a request."""

    injected: bool
    fault_type: FaultType
    delay_seconds: float = 0.0
    custom_raw_response: str | None = None
    override_result: str | None = None
    error_override: str | None = None


class DeterministicFaultInjector:
    """Stateful, deterministic fault injector with PRNG seeding."""

    def __init__(self, config: FaultConfig | None = None) -> None:
        self.config = config or FaultConfig()
        self._rng = random.Random(self.config.seed)
        self._request_counter = 0
        self._fault_trigger_counter = 0

    def reset(self, new_config: FaultConfig | None = None) -> None:
        """Reset internal counters and optionally apply a new config."""
        if new_config is not None:
            self.config = new_config
        self._rng = random.Random(self.config.seed)
        self._request_counter = 0
        self._fault_trigger_counter = 0

    def evaluate(self, cmd: str, args: dict[str, Any], req_id: str) -> FaultDecision:
        """Evaluate if the incoming command triggers an active fault."""
        self._request_counter += 1

        if self.config.fault_type == FaultType.NONE:
            return FaultDecision(injected=False, fault_type=FaultType.NONE)

        # Check target_cmd filter
        if self.config.target_cmd and self.config.target_cmd != cmd:
            return FaultDecision(injected=False, fault_type=FaultType.NONE)

        # Check target_pin filter
        if self.config.target_pin is not None:
            req_pin = args.get("pin")
            if req_pin is None or int(req_pin) != self.config.target_pin:
                return FaultDecision(injected=False, fault_type=FaultType.NONE)

        # Check trigger count thresholds
        if self._request_counter <= self.config.trigger_after_count:
            return FaultDecision(injected=False, fault_type=FaultType.NONE)

        if (
            self.config.trigger_max_times is not None
            and self._fault_trigger_counter >= self.config.trigger_max_times
        ):
            return FaultDecision(injected=False, fault_type=FaultType.NONE)

        # Check deterministic probability
        if self.config.probability < 1.0:
            roll = self._rng.random()
            if roll > self.config.probability:
                return FaultDecision(injected=False, fault_type=FaultType.NONE)

        self._fault_trigger_counter += 1
        fault = self.config.fault_type

        if fault == FaultType.LATENCY:
            return FaultDecision(
                injected=True,
                fault_type=fault,
                delay_seconds=self.config.delay_seconds,
            )

        if fault == FaultType.DISCONNECTION:
            return FaultDecision(
                injected=True,
                fault_type=fault,
            )

        if fault == FaultType.MALFORMED_RESPONSE:
            raw = self.config.malformed_payload.replace("{id}", req_id)
            if not raw.endswith("\n"):
                raw += "\n"
            return FaultDecision(
                injected=True,
                fault_type=fault,
                custom_raw_response=raw,
            )

        if fault == FaultType.ERROR_RESPONSE:
            return FaultDecision(
                injected=True,
                fault_type=fault,
                error_override=self.config.error_message,
            )

        if fault == FaultType.STALE_OR_ABNORMAL_VALUE:
            return FaultDecision(
                injected=True,
                fault_type=fault,
                override_result=self.config.abnormal_value,
            )

        return FaultDecision(injected=False, fault_type=FaultType.NONE)
