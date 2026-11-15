"""Serial hardware backend placeholder.

NOT IMPLEMENTED.
Reserved for the physical hardware stage on Jetson Nano / USB Serial dongles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from gateway.backend.base import Backend


class SerialBackend(Backend):
    """Serial communication backend via RS232 / USB CDC.

    Status: NOT IMPLEMENTED.
    This backend will be implemented when physical hardware (ESP32, Pico W, Uno, STM32)
    is deployed to an Industrial Gateway (e.g. Jetson Nano).
    """

    def __init__(self, port_map: Optional[Dict[str, str]] = None, baudrate: int = 115200):
        self.port_map = port_map or {}
        self.baudrate = baudrate

    async def get_node_state(self, node_id: str) -> Dict[str, Any]:
        raise NotImplementedError(
            "SerialBackend is NOT IMPLEMENTED. Physical serial hardware is deferred to Jetson Nano stage."
        )

    async def set_node_state(self, node_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError(
            "SerialBackend is NOT IMPLEMENTED. Physical serial hardware is deferred to Jetson Nano stage."
        )

    async def execute_action(
        self, node_id: str, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "SerialBackend is NOT IMPLEMENTED. Physical serial hardware is deferred to Jetson Nano stage."
        )

    async def reset(self, fixture_path: Optional[Path] = None) -> None:
        raise NotImplementedError(
            "SerialBackend is NOT IMPLEMENTED. Physical serial hardware is deferred to Jetson Nano stage."
        )
