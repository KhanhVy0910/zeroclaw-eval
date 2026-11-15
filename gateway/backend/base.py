"""Abstract base backend interface for Hardware Gateway."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


class GatewayError(Exception):
    """Base error for Hardware Gateway operations."""

    def __init__(self, message: str, code: str = "EXECUTION_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class GatewayConnectionError(GatewayError):
    """Raised when communication with node or peripheral fails."""

    def __init__(self, message: str = "Connection to node lost or unreachable"):
        super().__init__(message, code="CONNECTION_ERROR")


class GatewayDeviceError(GatewayError):
    """Raised when hardware device reports an internal fault or hardware failure."""

    def __init__(self, message: str = "Device internal failure"):
        super().__init__(message, code="DEVICE_ERROR")


class GatewayInvalidArgumentError(GatewayError):
    """Raised when request arguments are invalid, missing or out of bounds."""

    def __init__(self, message: str = "Invalid argument"):
        super().__init__(message, code="INVALID_ARGUMENT")


class GatewayExecutionError(GatewayError):
    """Raised when an action fails during execution."""

    def __init__(self, message: str = "Action execution failed"):
        super().__init__(message, code="EXECUTION_ERROR")


class GatewaySafetyViolationError(GatewayError):
    """Raised when an action violates safety constraints (e.g. command while Emergency Stop is active)."""

    def __init__(self, message: str = "Action blocked by safety interlock"):
        super().__init__(message, code="SAFETY_VIOLATION")


class Backend(ABC):
    """Abstract interface for hardware access backends (Mock, Serial, etc.)."""

    @abstractmethod
    async def get_node_state(self, node_id: str) -> Dict[str, Any]:
        """Retrieve full state dictionary for a specific node."""
        raise NotImplementedError

    @abstractmethod
    async def set_node_state(self, node_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update state dictionary for a specific node."""
        raise NotImplementedError

    @abstractmethod
    async def execute_action(
        self, node_id: str, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a domain action on a node (e.g. get_status, set_fan)."""
        raise NotImplementedError

    @abstractmethod
    async def reset(self, fixture_path: Optional[Path] = None) -> None:
        """Reset backend state to default fixture values."""
        raise NotImplementedError
