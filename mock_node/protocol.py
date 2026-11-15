"""ZeroClaw Serial JSON Protocol Parser and Serializer.

Verified against:
- firmware/zeroclaw-fw-protocol/src/command.rs
- firmware/zeroclaw-fw-protocol/src/response.rs
- firmware/zeroclaw-fw-protocol/src/parse.rs
- crates/zeroclaw-hardware/src/peripherals/serial.rs
- crates/zeroclaw-hardware/examples/esp32_sim.rs
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ZcCommand:
    """Incoming command from ZeroClaw Host."""

    id: str
    cmd: str
    args: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_line(cls, line: str | bytes) -> ZcCommand:
        """Parse a single JSON line into a ZcCommand.

        Raises ValueError if line is not valid JSON or missing required fields.
        """
        if isinstance(line, bytes):
            line_str = line.decode("utf-8", errors="replace").strip()
        else:
            line_str = line.strip()

        if not line_str:
            raise ValueError("Empty request line")

        try:
            data = json.loads(line_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON request: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Request JSON must be an object")

        raw_id = data.get("id", "0")
        cmd = data.get("cmd")
        if not cmd or not isinstance(cmd, str):
            raise ValueError("Request must contain non-empty string 'cmd' field")

        raw_args = data.get("args", {})
        if not isinstance(raw_args, dict):
            raw_args = {}

        return cls(id=str(raw_id), cmd=cmd, args=raw_args)


@dataclass
class ZcResponse:
    """Device response sent back to ZeroClaw Host."""

    id: str
    ok: bool
    result: str = ""
    error: str | None = None

    def to_wire_line(self) -> str:
        """Serialize into newline-delimited JSON strictly following the firmware contract.

        Success format:
            {"id":"<id>","ok":true,"result":"<result>"}
        Error format:
            {"id":"<id>","ok":false,"result":"","error":"<error>"}
        """
        if self.ok:
            payload: dict[str, Any] = {
                "id": str(self.id),
                "ok": True,
                "result": str(self.result),
            }
        else:
            payload = {
                "id": str(self.id),
                "ok": False,
                "result": "",
                "error": str(self.error or ""),
            }

        # Compact JSON without space after separators to match write_ok / write_err format
        return json.dumps(payload, separators=(",", ":")) + "\n"

    @classmethod
    def success(cls, id: str, result: str) -> ZcResponse:
        """Create success response."""
        return cls(id=str(id), ok=True, result=result, error=None)

    @classmethod
    def error_response(cls, id: str, error: str) -> ZcResponse:
        """Create error response."""
        return cls(id=str(id), ok=False, result="", error=error)
