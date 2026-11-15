"""In-memory Mock Backend for Hardware Gateway."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from gateway.backend.base import (
    Backend,
    GatewayConnectionError,
    GatewayDeviceError,
    GatewayInvalidArgumentError,
    GatewaySafetyViolationError,
)

DEFAULT_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "default_world.yaml"


class MockBackend(Backend):
    """In-memory simulation of hardware nodes, initialized from fixture."""

    def __init__(self, fixture_path: Optional[Path] = None):
        self.fixture_path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE_PATH
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self._load_fixture()

    def _load_fixture(self) -> None:
        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {self.fixture_path}")
        with open(self.fixture_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        raw_nodes = data.get("nodes", {})
        # Deep copy to maintain pristine in-memory state
        self.nodes = copy.deepcopy(raw_nodes)

    async def reset(self, fixture_path: Optional[Path] = None) -> None:
        """Reset state back to initial fixture values."""
        if fixture_path:
            self.fixture_path = Path(fixture_path)
        self._load_fixture()

    async def get_node_state(self, node_id: str) -> Dict[str, Any]:
        """Get copy of in-memory state for a given node."""
        node = self.nodes.get(node_id)
        if not node:
            raise GatewayInvalidArgumentError(f"Node '{node_id}' does not exist")
        return copy.deepcopy(node.get("state", {}))

    async def set_node_state(self, node_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Admin helper: directly update node state fields."""
        node = self.nodes.get(node_id)
        if not node:
            raise GatewayInvalidArgumentError(f"Node '{node_id}' does not exist")
        state = node.setdefault("state", {})
        for k, v in updates.items():
            if isinstance(v, dict) and isinstance(state.get(k), dict):
                state[k].update(v)
            else:
                state[k] = v
        return copy.deepcopy(state)

    def is_emergency_stop_active(self) -> bool:
        """Check if Emergency Stop is engaged on safety node N4."""
        n4_node = self.nodes.get("n4")
        if n4_node:
            return bool(n4_node.get("state", {}).get("emergency_stop", False))
        return False

    async def execute_action(
        self, node_id: str, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a domain action against a node."""
        params = params or {}
        node = self.nodes.get(node_id)
        if not node:
            raise GatewayInvalidArgumentError(f"Node '{node_id}' not found")

        state = node.setdefault("state", {})

        # Safety Check: If Emergency Stop is active, reject control / actuation commands
        is_control_action = action in ("set_fan", "set_line_state", "open_gate", "start_motor", "write_pin")
        if is_control_action and self.is_emergency_stop_active():
            raise GatewaySafetyViolationError("Action rejected: Emergency Stop is currently ENGAGED")

        # Node N1: ESP32 (Production Control)
        if node_id == "n1":
            if action in ("get_status", "status"):
                return {
                    "fan": state.get("fan", 0),
                    "status_led": state.get("status_led", 0),
                    "line_state": state.get("line_state", "running"),
                    "machine_status": state.get("machine_status", "ok"),
                    "temperature": state.get("temperature", 45.0),
                    "humidity": state.get("humidity", 80.0),
                }

            elif action in ("set_fan", "fan"):
                val = params.get("state")
                if val is None:
                    val = params.get("value")
                if val is None:
                    raise GatewayInvalidArgumentError("Missing 'state' parameter for set_fan")

                if isinstance(val, bool):
                    target_state = 1 if val else 0
                elif isinstance(val, (int, float)):
                    target_state = 1 if int(val) > 0 else 0
                elif isinstance(val, str):
                    target_state = 1 if val.lower() in ("1", "true", "on", "enable") else 0
                else:
                    raise GatewayInvalidArgumentError(f"Invalid fan state value: {val}")

                state["fan"] = target_state
                # Sync pin 2
                pins = state.setdefault("pins", {})
                pins[2] = target_state
                return {
                    "fan": target_state,
                    "pin": 2,
                    "pin_value": target_state,
                }

            elif action == "set_line_state":
                line_state = params.get("line_state")
                if not line_state or line_state not in ("running", "holding", "stopped"):
                    raise GatewayInvalidArgumentError(f"Invalid line_state: {line_state}")
                state["line_state"] = line_state
                return {"line_state": line_state}

            elif action == "write_pin":
                pin = params.get("pin")
                value = params.get("value")
                if pin is None or value is None:
                    raise GatewayInvalidArgumentError("Missing pin or value")
                pins = state.setdefault("pins", {})
                pins[int(pin)] = int(value)
                return {"pin": int(pin), "value": int(value)}

            elif action == "read_pin":
                pin = params.get("pin")
                if pin is None:
                    raise GatewayInvalidArgumentError("Missing pin")
                pins = state.setdefault("pins", {})
                return {"pin": int(pin), "value": pins.get(int(pin), 0)}

            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N1")

        # Node N2: Pico W (Environmental Monitoring)
        elif node_id == "n2":
            if action in ("get_status", "get_env", "status"):
                return {
                    "temperature": state.get("temperature", 24.5),
                    "humidity": state.get("humidity", 60.0),
                }
            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N2")

        # Node N3: Arduino Uno (Warehouse & Material Handling)
        elif node_id == "n3":
            if action in ("get_status", "status"):
                return {
                    "rfid_tag": state.get("rfid_tag", ""),
                    "rfid_valid": state.get("rfid_valid", False),
                    "gate_open": state.get("gate_open", False),
                    "inventory": state.get("inventory", 0),
                }
            elif action == "open_gate":
                state["gate_open"] = True
                return {"gate_open": True}
            elif action == "close_gate":
                state["gate_open"] = False
                return {"gate_open": False}
            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N3")

        # Node N4: STM32 Nucleo (Machine Health & Safety)
        elif node_id == "n4":
            if action in ("get_status", "status"):
                return {
                    "vibration": state.get("vibration", 0.1),
                    "machine_health": state.get("machine_health", "nominal"),
                    "emergency_stop": state.get("emergency_stop", False),
                }
            elif action in ("trigger_emergency_stop", "reset_emergency_stop"):
                # Safety constraint: Emergency Stop cannot be altered via domain business actions!
                raise GatewaySafetyViolationError(
                    "Emergency Stop can ONLY be changed via admin physical interlock endpoint, not business action."
                )
            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N4")

        else:
            raise GatewayInvalidArgumentError(f"Unknown node '{node_id}'")
