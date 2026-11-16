"""In-memory Mock Backend for Hardware Gateway (Nodes N1, N2, N3, N4)."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from gateway.backend.base import (
    Backend,
    GatewayConnectionError,
    GatewayDeviceError,
    GatewayInvalidArgumentError,
    GatewaySafetyStateUnknownError,
    GatewaySafetyViolationError,
)

DEFAULT_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "default_world.yaml"


class MockBackend(Backend):
    """In-memory simulation of 4 industrial hardware nodes, initialized from fixture."""

    def __init__(self, fixture_path: Optional[Path] = None):
        self.default_fixture_path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE_PATH
        self.fixture_path = self.default_fixture_path
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self._qr_counter = 0
        self._ir_counter = 0
        self._load_fixture()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_fixture(self) -> None:
        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {self.fixture_path}")
        with open(self.fixture_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        raw_nodes = data.get("nodes", {})
        self.nodes = copy.deepcopy(raw_nodes)

        # Initialize queue counters based on existing fixtures
        n3_queue = self.nodes.get("n3", {}).get("state", {}).get("quarantine_queue", [])
        self._qr_counter = len(n3_queue)
        n4_queue = self.nodes.get("n4", {}).get("state", {}).get("inspection_queue", [])
        self._ir_counter = len(n4_queue)

    async def reset(self, fixture_path: Optional[Path] = None) -> None:
        """Reset state back to initial fixture values."""
        if fixture_path:
            self.fixture_path = Path(fixture_path)
        else:
            self.fixture_path = self.default_fixture_path
        self._load_fixture()

    async def get_node_state(self, node_id: str) -> Dict[str, Any]:
        """Get copy of in-memory state for a given node."""
        norm_node = node_id.strip().lower()
        node = self.nodes.get(norm_node)
        if not node:
            raise GatewayInvalidArgumentError(f"Node '{node_id}' does not exist")
        return copy.deepcopy(node.get("state", {}))

    async def set_node_state(self, node_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Admin helper: directly update node state fields."""
        norm_node = node_id.strip().lower()
        node = self.nodes.get(norm_node)
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

    def are_interlocks_violated(self) -> tuple[bool, str]:
        """Check if machine interlocks (guard door, light curtain) on N4 are violated."""
        n4_node = self.nodes.get("n4")
        if not n4_node:
            return False, ""
        interlocks = n4_node.get("state", {}).get("interlocks", {})
        guard = str(interlocks.get("guard_door", "closed")).lower()
        curtain = str(interlocks.get("light_curtain", "clear")).lower()

        if guard == "open":
            return True, "Safety interlock guard door is OPEN"
        if curtain == "interrupted":
            return True, "Safety interlock light curtain is INTERRUPTED"
        return False, ""

    def calculate_n4_health(self) -> Dict[str, Any]:
        """Calculate machine health SOLELY from N4 data (vibration, motor_current, anomaly_history).
        
        Rule: Machine health is completely independent of Node N1!
        """
        n4_node = self.nodes.get("n4")
        if not n4_node:
            return {
                "health_score": 0.0,
                "health_status": "critical",
                "anomaly_detected": True,
            }
        state = n4_node.get("state", {})
        vib = state.get("vibration", {})
        if isinstance(vib, dict):
            vibration_rms = float(vib.get("rms", 0.13))
        else:
            vibration_rms = float(vib)

        motor_current = float(state.get("motor_current", 8.4))
        anomaly_history = state.get("anomaly_history", [])

        # Diagnostics evaluation
        if vibration_rms > 0.5 or motor_current > 20.0 or len(anomaly_history) >= 5:
            health_score = 35.0
            health_status = "critical"
            anomaly_detected = True
        elif vibration_rms > 0.3 or motor_current > 15.0 or len(anomaly_history) > 0:
            health_score = 70.0
            health_status = "warning"
            anomaly_detected = True
        else:
            health_score = 95.0
            health_status = "nominal"
            anomaly_detected = False

        state["health_score"] = health_score
        state["health_status"] = health_status
        state["anomaly_detected"] = anomaly_detected
        state["machine_health"] = health_status

        return {
            "health_score": health_score,
            "health_status": health_status,
            "machine_health": health_status,
            "anomaly_detected": anomaly_detected,
            "vibration_rms": vibration_rms,
            "motor_current": motor_current,
        }

    # -----------------------------------------------------------------
    # ADMIN QUEUE MANAGEMENT HELPERS
    # -----------------------------------------------------------------
    async def review_quarantine_request(self, request_id: str, decision: str) -> Dict[str, Any]:
        """Admin only: approve or reject lot quarantine request in N3 queue."""
        dec = decision.strip().lower()
        if dec not in ("approved", "rejected"):
            raise GatewayInvalidArgumentError("Decision must be 'approved' or 'rejected'")

        n3_node = self.nodes.get("n3")
        if not n3_node:
            raise GatewayDeviceError("Node N3 not available")
        state = n3_node.setdefault("state", {})
        queue = state.setdefault("quarantine_queue", [])

        target = None
        for item in queue:
            if item.get("id") == request_id:
                target = item
                break

        if not target:
            raise GatewayInvalidArgumentError(f"Quarantine request '{request_id}' not found")

        target["status"] = dec
        target["reviewed_at"] = self._now_iso()

        # If approved, update lot status in material table
        lot_id = target.get("lot_id")
        lots = state.setdefault("lots", {})
        if dec == "approved" and lot_id in lots:
            lots[lot_id]["status"] = "quarantined"

        return {
            "request_id": request_id,
            "lot_id": lot_id,
            "status": dec,
            "lot_status": lots.get(lot_id, {}).get("status") if lot_id in lots else None,
            "timestamp": self._now_iso(),
        }

    async def review_inspection_request(self, request_id: str, decision: str) -> Dict[str, Any]:
        """Admin only: approve or reject maintenance inspection request in N4 queue."""
        dec = decision.strip().lower()
        if dec not in ("approved", "rejected"):
            raise GatewayInvalidArgumentError("Decision must be 'approved' or 'rejected'")

        n4_node = self.nodes.get("n4")
        if not n4_node:
            raise GatewayDeviceError("Node N4 not available")
        state = n4_node.setdefault("state", {})
        queue = state.setdefault("inspection_queue", [])

        target = None
        for item in queue:
            if item.get("id") == request_id:
                target = item
                break

        if not target:
            raise GatewayInvalidArgumentError(f"Inspection request '{request_id}' not found")

        target["status"] = dec
        target["reviewed_at"] = self._now_iso()

        return {
            "request_id": request_id,
            "equipment_id": target.get("equipment_id"),
            "status": dec,
            "timestamp": self._now_iso(),
        }

    async def set_lot_status(self, lot_id: str, status: str) -> Dict[str, Any]:
        """Admin only: directly update lot status in N3."""
        stat = status.strip().lower()
        if stat not in ("approved", "quarantined", "unknown"):
            raise GatewayInvalidArgumentError("Lot status must be 'approved', 'quarantined', or 'unknown'")

        n3_node = self.nodes.get("n3")
        if not n3_node:
            raise GatewayDeviceError("Node N3 not available")
        state = n3_node.setdefault("state", {})
        lots = state.setdefault("lots", {})
        if lot_id not in lots:
            raise GatewayInvalidArgumentError(f"Lot '{lot_id}' not found in warehouse")

        lots[lot_id]["status"] = stat
        return {
            "lot_id": lot_id,
            "status": stat,
            "timestamp": self._now_iso(),
        }

    # -----------------------------------------------------------------
    # DOMAIN ACTION EXECUTION
    # -----------------------------------------------------------------
    async def execute_action(
        self, node_id: str, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a domain action against a node with runtime safety enforcement."""
        params = params or {}
        norm_node = node_id.strip().lower()
        node = self.nodes.get(norm_node)
        if not node:
            raise GatewayInvalidArgumentError(f"Node '{node_id}' not found")

        state = node.setdefault("state", {})
        ts = self._now_iso()

        # -------------------------------------------------------------
        # RUNTIME SAFETY ENFORCEMENT FOR R2 & R3 CONTROL ACTIONS
        # Gateway RE-CHECKS safety at execution time; never trusts past checks!
        # -------------------------------------------------------------
        estop_engaged = self.is_emergency_stop_active()

        # Rule 3: Emergency Stop behavior
        # When E-Stop is active:
        # - set_line_state start/run -> REJECTED
        # - hold and stop -> ACCEPTED
        # - set_fan, set_status_light, close_gate -> ACCEPTED
        # - open_gate -> REJECTED

        if norm_node == "n1" and action in ("set_line_state", "line_state"):
            target_line_state = str(params.get("line_state") or params.get("state") or "").strip().lower()
            if target_line_state in ("start", "run", "running"):
                # Check N4 availability (Condition 5)
                n4_node = self.nodes.get("n4")
                if not n4_node:
                    raise GatewaySafetyStateUnknownError("SAFETY_STATE_UNKNOWN: Cannot verify safety conditions; Node N4 disconnected or unavailable")
                # Check E-Stop (Condition 2)
                if estop_engaged:
                    raise GatewaySafetyViolationError("Action rejected: Emergency Stop is currently ENGAGED on Node N4")
                # Check Interlocks (Condition 3)
                violated, reason = self.are_interlocks_violated()
                if violated:
                    raise GatewaySafetyViolationError(f"Action rejected: {reason}")
                # Check N4 Machine Health & Vibration (Condition 4)
                health = self.calculate_n4_health()
                if health["health_status"] == "critical" or health["vibration_rms"] > 0.5:
                    raise GatewaySafetyViolationError(
                        f"Action rejected: Unsafe machine condition on Node N4 (status={health['health_status']}, vibration RMS={health['vibration_rms']} mm/s)"
                    )

        if norm_node == "n3" and action in ("open_gate", "set_gate", "set_gate_state", "gate"):
            target_open = False
            if action == "open_gate":
                target_open = True
            else:
                val = params.get("state") if params.get("state") is not None else params.get("gate_open")
                if isinstance(val, bool):
                    target_open = val
                elif isinstance(val, (int, float)):
                    target_open = int(val) > 0
                elif isinstance(val, str):
                    target_open = val.lower() in ("1", "true", "open", "opened")

            if target_open:
                # Check N4 availability (Condition 5)
                n4_node = self.nodes.get("n4")
                if not n4_node:
                    raise GatewaySafetyStateUnknownError("SAFETY_STATE_UNKNOWN: Cannot verify safety conditions; Node N4 disconnected or unavailable")
                # Check E-Stop (Condition 2)
                if estop_engaged:
                    raise GatewaySafetyViolationError("Action rejected: Gate cannot be opened while Emergency Stop is ENGAGED")
                # Option B (Condition 3): Interlock violation blocks opening warehouse gate!
                violated, reason = self.are_interlocks_violated()
                if violated:
                    raise GatewaySafetyViolationError(f"Action rejected: Gate cannot be opened while safety interlocks are violated ({reason})")

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
                    "timestamp": ts,
                }

            elif action in ("get_line_status", "line_status"):
                return {
                    "line_state": state.get("line_state", "running"),
                    "speed": state.get("speed", 100),
                    "lot_id": state.get("lot_id", "LOT-2026-N1-001"),
                    "timestamp": ts,
                }

            elif action in ("get_fan_status", "fan_status"):
                fan_id = params.get("fan_id")
                fans = state.setdefault("fans", {
                    "1": {"fan_id": 1, "state": 0, "speed": 0, "rpm": 0},
                    "2": {"fan_id": 2, "state": 0, "speed": 0, "rpm": 0},
                })
                if fan_id is not None:
                    fid_str = str(fan_id)
                    if fid_str not in fans:
                        raise GatewayInvalidArgumentError(f"Invalid fan_id: {fan_id}. Available: 1, 2")
                    f_info = copy.deepcopy(fans[fid_str])
                    f_info["timestamp"] = ts
                    return f_info
                return {"fans": copy.deepcopy(fans), "timestamp": ts}

            elif action in ("get_equipment_temperature", "equipment_temperature"):
                eq_id = params.get("equipment_id")
                temps = state.setdefault("equipment_temperature", {
                    "motor": 45.2,
                    "control_cabinet": 36.8,
                })
                if eq_id is not None:
                    eq_key = str(eq_id).strip().lower()
                    if eq_key not in temps:
                        raise GatewayInvalidArgumentError(f"Invalid equipment_id: {eq_id}. Available: 'motor', 'control_cabinet'")
                    return {
                        "equipment_id": eq_key,
                        "temperature": temps[eq_key],
                        "unit": "C",
                        "timestamp": ts,
                    }
                return {"equipment_temperature": copy.deepcopy(temps), "unit": "C", "timestamp": ts}

            elif action in ("get_output_counter", "output_counter"):
                cnt = state.setdefault("output_counter", {
                    "total_units": 1520,
                    "good_units": 1498,
                    "defective_units": 22,
                })
                res = copy.deepcopy(cnt)
                res["timestamp"] = ts
                return res

            elif action in ("set_fan_state", "set_fan", "fan"):
                fan_id = params.get("fan_id", 1)
                fid_str = str(fan_id)
                val = params.get("state") if params.get("state") is not None else params.get("value")
                if val is None:
                    raise GatewayInvalidArgumentError("Missing 'state' parameter for set_fan_state")

                if isinstance(val, bool):
                    target_state = 1 if val else 0
                elif isinstance(val, (int, float)):
                    target_state = 1 if int(val) > 0 else 0
                elif isinstance(val, str):
                    target_state = 1 if val.lower() in ("1", "true", "on", "enable") else 0
                else:
                    raise GatewayInvalidArgumentError(f"Invalid fan state value: {val}")

                fans = state.setdefault("fans", {
                    "1": {"fan_id": 1, "state": 0, "speed": 0, "rpm": 0},
                    "2": {"fan_id": 2, "state": 0, "speed": 0, "rpm": 0},
                })
                if fid_str not in fans:
                    fans[fid_str] = {"fan_id": int(fan_id), "state": 0, "speed": 0, "rpm": 0}

                speed_param = params.get("speed")
                if speed_param is None:
                    speed = 100 if target_state else 0
                else:
                    speed = int(speed_param)

                rpm = speed * 25 if target_state else 0
                fans[fid_str]["state"] = target_state
                fans[fid_str]["speed"] = speed
                fans[fid_str]["rpm"] = rpm

                # Backward compatibility for fan 1
                if fid_str == "1":
                    state["fan"] = target_state
                    state.setdefault("pins", {})[2] = target_state

                return {
                    "fan": target_state,
                    "fan_id": int(fan_id),
                    "state": target_state,
                    "speed": speed,
                    "rpm": rpm,
                    "pin": 2,
                    "pin_value": target_state,
                    "timestamp": ts,
                }

            elif action in ("set_status_light", "set_status_led", "status_led", "status_light"):
                val = params.get("state") if params.get("state") is not None else params.get("value")
                if val is None:
                    val = params.get("color")
                if val is None:
                    raise GatewayInvalidArgumentError("Missing 'state' or 'color' parameter for status light")

                val_str = str(val).lower()
                if val_str in ("green", "1", "true", "on"):
                    color = "green"
                    led_state = 1
                elif val_str in ("yellow", "warn", "warning"):
                    color = "yellow"
                    led_state = 1
                elif val_str in ("red", "fault", "error"):
                    color = "red"
                    led_state = 1
                else:
                    color = "off"
                    led_state = 0

                state["status_light"] = color
                state["status_led"] = led_state
                state.setdefault("pins", {})[5] = led_state
                return {"status_light": color, "status_led": led_state, "timestamp": ts}

            elif action in ("set_line_state", "line_state"):
                raw_state = params.get("line_state") or params.get("state")
                if not raw_state:
                    raise GatewayInvalidArgumentError("Missing 'line_state' parameter")
                norm_st = str(raw_state).strip().lower()
                state_map = {
                    "start": "running",
                    "run": "running",
                    "running": "running",
                    "hold": "holding",
                    "holding": "holding",
                    "stop": "stopped",
                    "stopped": "stopped",
                    "fault": "fault",
                }
                if norm_st not in state_map:
                    raise GatewayInvalidArgumentError(
                        f"Invalid line_state: '{raw_state}'. Allowed: 'run' (or 'start'), 'hold', 'stop', 'fault'"
                    )
                final_state = state_map[norm_st]
                state["line_state"] = final_state
                return {"line_state": final_state, "timestamp": ts}

            elif action == "write_pin":
                pin = params.get("pin")
                value = params.get("value")
                if pin is None or value is None:
                    raise GatewayInvalidArgumentError("Missing pin or value")
                pins = state.setdefault("pins", {})
                pins[int(pin)] = int(value)
                return {"pin": int(pin), "value": int(value), "timestamp": ts}

            elif action == "read_pin":
                pin = params.get("pin")
                if pin is None:
                    raise GatewayInvalidArgumentError("Missing pin")
                pins = state.setdefault("pins", {})
                return {"pin": int(pin), "value": pins.get(int(pin), 0), "timestamp": ts}

            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N1")

        # -------------------------------------------------------------
        # NODE N2: Raspberry Pi Pico W (Environmental Monitoring)
        # -------------------------------------------------------------
        elif norm_node == "n2":
            # Reject actuation / control actions on N2
            if (action.startswith("set_") and action not in ("set_threshold", "update_threshold")) or action in ("write_pin", "write", "fan", "gate"):
                raise GatewaySafetyViolationError("Node N2 is environmental sensing and strictly read-only; write actions are not permitted")

            if action in ("get_status", "get_env", "status"):
                return {
                    "temperature": state.get("temperature", 24.5),
                    "humidity": state.get("humidity", 60.0),
                    "timestamp": ts,
                }

            elif action in ("get_temperature", "temperature"):
                zone_id = params.get("zone_id")
                if not zone_id:
                    return {
                        "temperature": state.get("temperature", 24.5),
                        "unit": "C",
                        "timestamp": ts,
                    }
                zones = state.setdefault("zones", {
                    "hall": {"temperature": 23.5, "humidity": 55.0},
                    "storage": {"temperature": 20.2, "humidity": 50.0},
                    "production_floor": {"temperature": 25.8, "humidity": 62.0},
                })
                zone_key = str(zone_id).strip().lower()
                if zone_key not in zones:
                    raise GatewayInvalidArgumentError(f"Unknown zone_id: '{zone_id}'. Available: 'hall', 'storage', 'production_floor'")
                return {
                    "zone_id": zone_key,
                    "temperature": zones[zone_key]["temperature"],
                    "unit": "C",
                    "timestamp": ts,
                }

            elif action in ("get_humidity", "humidity"):
                zone_id = params.get("zone_id")
                if not zone_id:
                    return {
                        "humidity": state.get("humidity", 60.0),
                        "unit": "%",
                        "timestamp": ts,
                    }
                zones = state.setdefault("zones", {
                    "hall": {"temperature": 23.5, "humidity": 55.0},
                    "storage": {"temperature": 20.2, "humidity": 50.0},
                    "production_floor": {"temperature": 25.8, "humidity": 62.0},
                })
                zone_key = str(zone_id).strip().lower()
                if zone_key not in zones:
                    raise GatewayInvalidArgumentError(f"Unknown zone_id: '{zone_id}'. Available: 'hall', 'storage', 'production_floor'")
                return {
                    "zone_id": zone_key,
                    "humidity": zones[zone_key]["humidity"],
                    "unit": "%",
                    "timestamp": ts,
                }

            elif action in ("get_air_quality", "air_quality"):
                air = state.setdefault("air_quality", {"pm25": 18.5, "pm10": 32.0, "co2": 520.0})
                res = copy.deepcopy(air)
                res["timestamp"] = ts
                return res

            elif action in ("get_environment_history", "environment_history"):
                hist = state.setdefault("measurement_history", [])
                return {"history": copy.deepcopy(hist), "timestamp": ts}

            elif action in ("get_thresholds", "thresholds"):
                thresh = state.setdefault("thresholds", {
                    "temp_max": 35.0,
                    "humidity_max": 75.0,
                    "co2_max": 1000.0,
                    "pm25_max": 50.0,
                })
                return {"thresholds": copy.deepcopy(thresh), "timestamp": ts}

            elif action in ("update_threshold", "set_threshold"):
                name = params.get("threshold_name") or params.get("name")
                val = params.get("value")
                if not name or val is None:
                    raise GatewayInvalidArgumentError("Missing 'threshold_name' or 'value'")
                thresh = state.setdefault("thresholds", {})
                thresh[str(name)] = float(val)
                return {"threshold_name": str(name), "value": float(val), "timestamp": ts}

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
                    "rfid_tag": state.get("rfid_tag", "BATCH-A100"),
                    "rfid_valid": state.get("rfid_valid", True),
                    "distance": state.get("distance", 15.0),
                    "gate_open": state.get("gate_open", False),
                    "inventory": state.get("inventory_count", 150) if "inventory_count" in state else state.get("inventory", 150),
                    "timestamp": ts,
                }

            elif action in ("read_rfid", "rfid"):
                reader_id = params.get("reader_id", "gate_reader")
                readers = state.get("rfid_readers")
                r_key = str(reader_id).strip().lower()
                if readers and isinstance(readers, dict) and r_key in readers:
                    card_id = readers[r_key].get("card_id", "")
                    is_valid = True
                else:
                    card_id = state.get("rfid_tag", "BATCH-A100")
                    is_valid = state.get("rfid_valid", True)

                return {
                    "reader_id": r_key,
                    "card_id": card_id,
                    "batch": card_id,
                    "valid": is_valid,
                    "timestamp": ts,
                }

            elif action in ("get_lot_info", "lot_info"):
                lot_id = params.get("lot_id")
                if not lot_id:
                    raise GatewayInvalidArgumentError("Missing 'lot_id' parameter")
                lots = state.setdefault("lots", {})
                lot_entry = lots.get(lot_id)
                if not lot_entry:
                    return {
                        "lot_id": lot_id,
                        "expiry_date": None,
                        "status": "unknown",
                        "timestamp": ts,
                    }
                res = copy.deepcopy(lot_entry)
                res["timestamp"] = ts
                return res

            elif action in ("get_inventory", "inventory"):
                item_id = params.get("item_id")
                loc_id = params.get("location_id")
                inv = state.get("inventory")
                if not item_id or not isinstance(inv, dict):
                    # Backward compatibility
                    inv_val = state.get("inventory_count", 150) if "inventory_count" in state else state.get("inventory", 150)
                    return {"inventory": inv_val, "unit": "units", "timestamp": ts}

                item_data = inv.get(item_id, {})
                if loc_id:
                    qty = item_data.get(loc_id, 0)
                    return {"item_id": item_id, "location_id": loc_id, "quantity": qty, "timestamp": ts}
                total_qty = sum(item_data.values()) if isinstance(item_data, dict) else 0
                return {"item_id": item_id, "total_quantity": total_qty, "locations": item_data, "timestamp": ts}

            elif action in ("get_gate_status", "gate_status"):
                gate_state = state.get("gate", {}).get("state", "closed")
                is_open = gate_state == "open" or state.get("gate_open", False)
                return {
                    "gate_state": "open" if is_open else "closed",
                    "is_open": is_open,
                    "gate_open": is_open,
                    "timestamp": ts,
                }

            elif action in ("open_gate",):
                state.setdefault("gate", {})["state"] = "open"
                state["gate_open"] = True
                return {"gate_open": True, "gate_state": "open", "timestamp": ts}

            elif action in ("close_gate",):
                state.setdefault("gate", {})["state"] = "closed"
                state["gate_open"] = False
                return {"gate_open": False, "gate_state": "closed", "timestamp": ts}

            elif action in ("set_gate", "set_gate_state", "gate"):
                val = params.get("state") if params.get("state") is not None else params.get("gate_open")
                if val is None:
                    raise GatewayInvalidArgumentError("Missing 'state' parameter for gate")

                if isinstance(val, bool):
                    target_open = val
                elif isinstance(val, (int, float)):
                    target_open = int(val) > 0
                elif isinstance(val, str):
                    target_open = val.lower() in ("1", "true", "open", "opened")
                else:
                    raise GatewayInvalidArgumentError(f"Invalid gate state: {val}")

                state.setdefault("gate", {})["state"] = "open" if target_open else "closed"
                state["gate_open"] = target_open
                return {"gate_open": target_open, "gate_state": "open" if target_open else "closed", "timestamp": ts}

            elif action in ("request_lot_quarantine", "quarantine_lot"):
                # Rule 4: Creates PENDING record in queue only! Lot status in warehouse table is NOT changed!
                lot_id = params.get("lot_id")
                reason = params.get("reason", "Flagged by agent inspection")
                if not lot_id:
                    raise GatewayInvalidArgumentError("Missing 'lot_id' parameter")

                self._qr_counter += 1
                req_id = f"QR-{self._qr_counter:04d}"
                entry = {
                    "id": req_id,
                    "lot_id": lot_id,
                    "reason": reason,
                    "requested_at": ts,
                    "status": "pending",
                }
                queue = state.setdefault("quarantine_queue", [])
                queue.append(entry)

                return {
                    "request_id": req_id,
                    "lot_id": lot_id,
                    "status": "pending",
                    "message": "Quarantine request registered in queue; pending administrator approval",
                    "timestamp": ts,
                }

            elif action in ("get_distance", "distance"):
                return {"distance": state.get("distance", 15.0), "unit": "cm", "timestamp": ts}

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

            # Reject any direct write to hardware on N4
            if action.startswith("set_") or action in ("write_pin", "write"):
                raise GatewaySafetyViolationError("Node N4 physical sensors are read-only via business actions")

            if action in ("get_status", "status"):
                health = self.calculate_n4_health()
                return {
                    "vibration": state.get("vibration", {}).get("rms", 0.12) if isinstance(state.get("vibration"), dict) else state.get("vibration", 0.12),
                    "machine_health": health["health_status"],
                    "emergency_stop": state.get("emergency_stop", False),
                    "timestamp": ts,
                }

            elif action in ("get_vibration", "vibration"):
                vib = state.get("vibration")
                if vib is None:
                    vib = {"x": 0.08, "y": 0.09, "z": 0.06, "rms": 0.13}
                if isinstance(vib, dict):
                    res = copy.deepcopy(vib)
                    res["vibration"] = res.get("rms", 0.13)
                else:
                    res = {"rms": float(vib), "vibration": float(vib)}
                res["unit"] = "mm/s"
                res["timestamp"] = ts
                return res

            elif action in ("get_motor_current", "motor_current"):
                current = float(state.get("motor_current", 8.4))
                return {"motor_current": current, "unit": "A", "timestamp": ts}

            elif action in ("get_machine_health", "machine_health", "health"):
                health = self.calculate_n4_health()
                health["timestamp"] = ts
                return health

            elif action in ("get_emergency_state", "emergency_state", "emergency"):
                is_engaged = bool(state.get("emergency_stop", False))
                return {
                    "emergency_stop": is_engaged,
                    "status": "ENGAGED" if is_engaged else "RELEASED",
                    "timestamp": ts,
                }

            elif action in ("get_interlock_status", "interlock_status", "interlocks"):
                interlocks = state.setdefault("interlocks", {
                    "guard_door": "closed",
                    "light_curtain": "clear",
                })
                res = copy.deepcopy(interlocks)
                res["timestamp"] = ts
                return res

            elif action in ("create_inspection_request", "request_inspection"):
                # Rule 4: Creates PENDING record in maintenance queue only!
                eq_id = params.get("equipment_id", "motor")
                reason = params.get("reason", "Vibration / operational abnormality detected")
                self._ir_counter += 1
                req_id = f"IR-{self._ir_counter:04d}"
                entry = {
                    "id": req_id,
                    "equipment_id": eq_id,
                    "reason": reason,
                    "requested_at": ts,
                    "status": "pending",
                }
                queue = state.setdefault("inspection_queue", [])
                queue.append(entry)

                return {
                    "request_id": req_id,
                    "equipment_id": eq_id,
                    "status": "pending",
                    "message": "Maintenance inspection request registered in queue; pending administrator approval",
                    "timestamp": ts,
                }

            elif action in ("check_operation_permit", "check_operation", "safety_check", "check"):
                # Advisory pre-check only
                is_estop = bool(state.get("emergency_stop", False))
                interlocks_violated, int_reason = self.are_interlocks_violated()
                health = self.calculate_n4_health()

                if is_estop:
                    allowed = False
                    reason = "Emergency Stop is currently ENGAGED on Node N4"
                elif interlocks_violated:
                    allowed = False
                    reason = int_reason
                elif health["health_status"] == "critical" or health["vibration_rms"] > 0.5:
                    allowed = False
                    reason = f"Machine condition unsafe: health={health['health_status']}, vibration={health['vibration_rms']} mm/s"
                else:
                    allowed = True
                    reason = "All safety conditions satisfied: E-Stop released, interlocks clear, machine health nominal"

                return {
                    "allowed": allowed,
                    "reason": reason,
                    "emergency_stop": is_estop,
                    "interlocks_violated": interlocks_violated,
                    "machine_health": health["health_status"],
                    "advisory_notice": "check_operation_permit is advisory only; Gateway enforces safety checks at command execution time",
                    "timestamp": ts,
                }

            else:
                raise GatewayInvalidArgumentError(f"Action '{action}' not supported for node N4")

        else:
            raise GatewayInvalidArgumentError(f"Unknown node '{node_id}'")
