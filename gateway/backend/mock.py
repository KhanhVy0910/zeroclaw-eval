"""In-memory Mock Backend for Hardware Gateway (Nodes N1, N2, N3, N4)."""

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
    """In-memory simulation of 4 industrial hardware nodes, initialized from fixture."""

    def __init__(self, fixture_path: Optional[Path] = None):
        self.default_fixture_path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE_PATH
        self.fixture_path = self.default_fixture_path
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
        else:
            self.fixture_path = self.default_fixture_path
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
        norm_node = node_id.strip().lower()
        node = self.nodes.get(norm_node)
        if not node:
            raise GatewayInvalidArgumentError(f"Node '{node_id}' not found")

        state = node.setdefault("state", {})

        # Safety Check: If Emergency Stop is active, reject ALL actuation / control actions
        is_control_action = action in (
            "set_fan",
            "fan",
            "set_line_state",
            "line_state",
            "set_status_led",
            "status_led",
            "write_pin",
            "open_gate",
            "close_gate",
            "set_gate",
            "gate",
        )
        if is_control_action and self.is_emergency_stop_active():
            raise GatewaySafetyViolationError("Action rejected: Emergency Stop is currently ENGAGED")

        # -------------------------------------------------------------
        # NODE N1: ESP32 DevKit (Production Control)
        # -------------------------------------------------------------
        if norm_node == "n1":
            if action in ("get_status", "status"):
                return {
                    "fan": state.get("fan", 0),
                    "status_led": state.get("status_led", 0),
                    "line_state": state.get("line_state", "running"),
                    "machine_status": state.get("machine_status", "ok"),
                    "temperature": state.get("temperature", 45.2),
                    "humidity": state.get("humidity", 82.0),
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

            elif action in ("set_line_state", "line_state"):
                line_state = params.get("line_state") or params.get("state")
                if not line_state or line_state not in ("running", "holding", "stopped"):
                    raise GatewayInvalidArgumentError(f"Invalid line_state: {line_state}")
                state["line_state"] = line_state
                return {"line_state": line_state}

            elif action in ("set_status_led", "status_led"):
                val = params.get("state") if params.get("state") is not None else params.get("value")
                if val is None:
                    raise GatewayInvalidArgumentError("Missing 'state' parameter for status_led")
                target_state = 1 if str(val).lower() in ("1", "true", "on") else 0
                state["status_led"] = target_state
                pins = state.setdefault("pins", {})
                pins[5] = target_state
                return {"status_led": target_state, "pin": 5}

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

        # -------------------------------------------------------------
        # NODE N2: Raspberry Pi Pico W (Environmental Monitoring) - READ-ONLY
        # -------------------------------------------------------------
        elif norm_node == "n2":
            # Reject any write action
            if action.startswith("set_") or action in ("write_pin", "write", "fan", "gate"):
                raise GatewaySafetyViolationError("Node N2 is read-only; write actions are not permitted")

            if action in ("get_status", "get_env", "status"):
                return {
                    "temperature": state.get("temperature", 24.5),
                    "humidity": state.get("humidity", 60.0),
                }

            elif action in ("get_temperature", "temperature"):
                return {
                    "temperature": state.get("temperature", 24.5),
                    "unit": "C",
                }

            elif action in ("get_humidity", "humidity"):
                return {
                    "humidity": state.get("humidity", 60.0),
                    "unit": "%",
                }

            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N2")

        # -------------------------------------------------------------
        # NODE N3: Arduino Uno R3 (Warehouse & Material Handling)
        # -------------------------------------------------------------
        elif norm_node == "n3":
            # Reject writes to sensors / inventory
            if action in ("set_rfid", "set_inventory", "set_distance"):
                raise GatewaySafetyViolationError("RFID reader and inventory counter on Node N3 are read-only")

            if action in ("get_status", "status"):
                return {
                    "rfid_tag": state.get("rfid_tag", ""),
                    "rfid_valid": state.get("rfid_valid", False),
                    "distance": state.get("distance", 15.0),
                    "gate_open": state.get("gate_open", False),
                    "inventory": state.get("inventory", 0),
                }

            elif action in ("read_rfid", "rfid"):
                return {
                    "rfid_tag": state.get("rfid_tag", ""),
                    "rfid_valid": state.get("rfid_valid", False),
                    "batch": state.get("rfid_tag", ""),
                    "valid": state.get("rfid_valid", False),
                }

            elif action in ("get_distance", "distance"):
                return {
                    "distance": state.get("distance", 15.0),
                    "unit": "cm",
                }

            elif action in ("get_inventory", "inventory"):
                return {
                    "inventory": state.get("inventory", 0),
                    "unit": "units",
                }

            elif action == "open_gate":
                state["gate_open"] = True
                return {"gate_open": True}

            elif action == "close_gate":
                state["gate_open"] = False
                return {"gate_open": False}

            elif action in ("set_gate", "gate"):
                val = params.get("state")
                if val is None:
                    val = params.get("gate_open")
                if val is None:
                    raise GatewayInvalidArgumentError("Missing 'state' parameter for set_gate")

                if isinstance(val, bool):
                    target_open = val
                elif isinstance(val, (int, float)):
                    target_open = bool(int(val) > 0)
                elif isinstance(val, str):
                    target_open = val.lower() in ("1", "true", "open", "opened")
                else:
                    raise GatewayInvalidArgumentError(f"Invalid gate state: {val}")

                state["gate_open"] = target_open
                return {"gate_open": target_open}

            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N3")

        # -------------------------------------------------------------
        # NODE N4: STM32 Nucleo-F401RE (Machine Health & Safety)
        # -------------------------------------------------------------
        elif norm_node == "n4":
            # Safety constraint: Emergency Stop cannot be altered via domain business actions!
            if action in ("trigger_emergency_stop", "set_emergency_stop", "reset_emergency_stop", "emergency_stop"):
                raise GatewaySafetyViolationError(
                    "Emergency Stop can ONLY be changed via admin physical interlock endpoint, not business action."
                )

            # Reject any other write action on N4
            if action.startswith("set_") or action in ("write_pin", "write"):
                raise GatewaySafetyViolationError("Node N4 is read-only via business actions")

            if action in ("get_status", "status"):
                return {
                    "vibration": state.get("vibration", 0.12),
                    "machine_health": state.get("machine_health", "nominal"),
                    "emergency_stop": state.get("emergency_stop", False),
                }

            elif action in ("get_vibration", "vibration"):
                return {
                    "vibration": state.get("vibration", 0.12),
                    "unit": "mm/s",
                }

            elif action in ("get_machine_health", "machine_health"):
                return {
                    "machine_health": state.get("machine_health", "nominal"),
                    "vibration": state.get("vibration", 0.12),
                }

            elif action in ("get_emergency_state", "emergency_state"):
                is_engaged = bool(state.get("emergency_stop", False))
                return {
                    "emergency_stop": is_engaged,
                    "status": "ENGAGED" if is_engaged else "RELEASED",
                }

            elif action in ("check_operation", "safety_check"):
                is_estop = bool(state.get("emergency_stop", False))
                health = str(state.get("machine_health", "nominal")).lower()
                vibration = float(state.get("vibration", 0.12))

                if is_estop:
                    return {
                        "allowed": False,
                        "reason": "Emergency Stop is currently ENGAGED on Node N4",
                        "emergency_stop": True,
                        "machine_health": health,
                    }
                elif health == "critical" or vibration > 0.5:
                    return {
                        "allowed": False,
                        "reason": f"Machine condition unsafe: health={health}, vibration={vibration} mm/s",
                        "emergency_stop": False,
                        "machine_health": health,
                    }
                else:
                    return {
                        "allowed": True,
                        "reason": "All safety conditions satisfied: E-Stop released and machine health nominal",
                        "emergency_stop": False,
                        "machine_health": health,
                    }

            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N4")

        else:
            raise GatewayInvalidArgumentError(f"Unknown node '{node_id}'")
