"""Node State representation and fixture loader."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PinDefinition:
    """Definition and current value of a single GPIO pin."""

    pin: int
    direction: str = "output"  # "input" or "output"
    value: int = 0
    device_name: str | None = None
    description: str | None = None


@dataclass
class NodeState:
    """In-memory state of a mock hardware node."""

    board: str = "esp32-sim-smartroom"
    description: str = "Smart-room simulator"
    pins: dict[int, PinDefinition] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeState:
        """Construct NodeState from a parsed dictionary."""
        board = data.get("board", "esp32-sim-smartroom")
        description = data.get("description", "Mock hardware node")
        pins: dict[int, PinDefinition] = {}

        raw_pins = data.get("pins", {})
        if isinstance(raw_pins, list):
            for p in raw_pins:
                if isinstance(p, dict) and "pin" in p:
                    pin_num = int(p["pin"])
                    pins[pin_num] = PinDefinition(
                        pin=pin_num,
                        direction=p.get("direction", "output"),
                        value=int(p.get("value", 0)),
                        device_name=p.get("device_name"),
                        description=p.get("description"),
                    )
        elif isinstance(raw_pins, dict):
            for k, v in raw_pins.items():
                pin_num = int(k)
                if isinstance(v, dict):
                    pins[pin_num] = PinDefinition(
                        pin=pin_num,
                        direction=v.get("direction", "output"),
                        value=int(v.get("value", 0)),
                        device_name=v.get("device_name"),
                        description=v.get("description"),
                    )
                else:
                    pins[pin_num] = PinDefinition(
                        pin=pin_num,
                        direction="output",
                        value=int(v),
                    )

        return cls(board=board, description=description, pins=pins)

    @classmethod
    def from_file(cls, file_path: str | Path) -> NodeState:
        """Load initial state from a YAML or JSON fixture file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Fixture file not found: {path}")

        content = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content) or {}
        else:
            data = json.loads(content)

        return cls.from_dict(data)

    def is_pin_supported(self, pin: int) -> bool:
        """Check if a pin is defined in this node."""
        return pin in self.pins

    def get_pin_value(self, pin: int) -> int:
        """Get the current logical value (0 or 1) of a pin."""
        if pin not in self.pins:
            raise KeyError(f"Pin {pin} is not configured")
        return self.pins[pin].value

    def set_pin_value(self, pin: int, value: int) -> None:
        """Set pin value (clamped to 0 or 1)."""
        if pin not in self.pins:
            raise KeyError(f"Pin {pin} is not configured")
        self.pins[pin].value = 1 if value != 0 else 0

    def get_capabilities_payload(self) -> dict[str, Any]:
        """Generate the dictionary returned by the 'capabilities' command."""
        gpio_list = sorted(self.pins.keys())
        pin_devices: dict[str, dict[str, str]] = {}
        for pin_num, pin_def in self.pins.items():
            if pin_def.device_name:
                pin_devices[str(pin_num)] = {
                    "device": pin_def.device_name,
                    "direction": pin_def.direction,
                    "description": pin_def.description or pin_def.device_name,
                }

        return {
            "gpio": gpio_list,
            "board": self.board,
            "description": self.description,
            "pin_devices": pin_devices,
        }

    def snapshot(self) -> dict[str, Any]:
        """Export current state snapshot for admin inspection."""
        return {
            "board": self.board,
            "description": self.description,
            "pins": {
                pin_num: {
                    "direction": p.direction,
                    "value": p.value,
                    "device_name": p.device_name,
                    "description": p.description,
                }
                for pin_num, p in self.pins.items()
            },
        }
