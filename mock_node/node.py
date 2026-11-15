"""Mock Node Core Engine.

Combines NodeState, DeterministicFaultInjector, and AuditLogger.
Executes the exact ZeroClaw firmware serial protocol.
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Any

from mock_node.faults import DeterministicFaultInjector, FaultConfig, FaultType
from mock_node.protocol import ZcCommand, ZcResponse
from mock_node.state import NodeState


class MockNode:
    """Mock Node executing the ZeroClaw Serial JSON protocol."""

    def __init__(
        self,
        state: NodeState | None = None,
        fault_config: FaultConfig | None = None,
        log_file_path: str | Path | None = None,
    ) -> None:
        self.state = state or NodeState()
        self.fault_injector = DeterministicFaultInjector(fault_config)
        self.log_file_path = Path(log_file_path) if log_file_path else None
        self.audit_logs: list[dict[str, Any]] = []

        if self.log_file_path:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            # Create or truncate log file on startup
            if not self.log_file_path.exists():
                self.log_file_path.touch()

    @classmethod
    def from_fixture(
        cls,
        fixture_path: str | Path,
        fault_config: FaultConfig | None = None,
        log_file_path: str | Path | None = None,
    ) -> MockNode:
        """Construct a MockNode from a YAML or JSON fixture file."""
        state = NodeState.from_file(fixture_path)
        return cls(state=state, fault_config=fault_config, log_file_path=log_file_path)

    def process_line(self, line: str | bytes) -> str | None:
        """Process one incoming serial line from the host.

        Returns:
            The raw response string ending in newline '\\n', or None if connection was dropped
            due to a simulated disconnection fault.
        """
        start_time = time.perf_counter()
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        raw_request = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else str(line)
        raw_request_clean = raw_request.rstrip("\r\n")

        # 1. Parse line into ZcCommand
        req_id = "0"
        try:
            cmd = ZcCommand.from_line(raw_request_clean)
            req_id = cmd.id
        except ValueError as exc:
            err_resp = ZcResponse.error_response("0", f"parse error: {exc}")
            wire_resp = err_resp.to_wire_line()
            self._record_audit(timestamp, raw_request_clean, wire_resp, start_time, fault="parse_error")
            return wire_resp

        # 2. Evaluate Fault Injection
        decision = self.fault_injector.evaluate(cmd.cmd, cmd.args, req_id)
        if decision.injected:
            if decision.fault_type == FaultType.DISCONNECTION:
                self._record_audit(timestamp, raw_request_clean, "<DISCONNECTION_NO_RESPONSE>", start_time, fault="disconnection")
                return None

            if decision.delay_seconds > 0:
                time.sleep(decision.delay_seconds)

            if decision.custom_raw_response is not None:
                self._record_audit(timestamp, raw_request_clean, decision.custom_raw_response, start_time, fault="malformed_response")
                return decision.custom_raw_response

            if decision.error_override is not None:
                err_resp = ZcResponse.error_response(req_id, decision.error_override)
                wire_resp = err_resp.to_wire_line()
                self._record_audit(timestamp, raw_request_clean, wire_resp, start_time, fault="error_response")
                return wire_resp

            if decision.override_result is not None:
                resp = ZcResponse.success(req_id, decision.override_result)
                wire_resp = resp.to_wire_line()
                self._record_audit(timestamp, raw_request_clean, wire_resp, start_time, fault="stale_or_abnormal_value")
                return wire_resp

        # 3. Normal command dispatch strictly based on verified commands
        resp = self._dispatch(cmd)
        wire_resp = resp.to_wire_line()
        self._record_audit(timestamp, raw_request_clean, wire_resp, start_time, fault=None)
        return wire_resp

    def _dispatch(self, cmd: ZcCommand) -> ZcResponse:
        """Dispatch commands strictly according to the ZeroClaw wire protocol."""
        if cmd.cmd == "ping":
            return ZcResponse.success(cmd.id, "pong")

        if cmd.cmd == "capabilities":
            caps = self.state.get_capabilities_payload()
            return ZcResponse.success(cmd.id, json.dumps(caps, separators=(",", ":")))

        if cmd.cmd == "gpio_read":
            pin = cmd.args.get("pin")
            if pin is None:
                return ZcResponse.error_response(cmd.id, "Invalid pin -1")
            try:
                pin_num = int(pin)
            except (ValueError, TypeError):
                return ZcResponse.error_response(cmd.id, f"Invalid pin {pin}")

            if not self.state.is_pin_supported(pin_num):
                return ZcResponse.error_response(cmd.id, f"Invalid pin {pin_num}")

            val = self.state.get_pin_value(pin_num)
            return ZcResponse.success(cmd.id, str(val))

        if cmd.cmd == "gpio_write":
            pin = cmd.args.get("pin")
            val = cmd.args.get("value")
            if pin is None or val is None:
                return ZcResponse.error_response(cmd.id, "Missing pin or value")
            try:
                pin_num = int(pin)
                val_num = int(val)
            except (ValueError, TypeError):
                return ZcResponse.error_response(cmd.id, "pin and value must be integers")

            if not self.state.is_pin_supported(pin_num):
                return ZcResponse.error_response(cmd.id, f"pin {pin_num} not configured")

            self.state.set_pin_value(pin_num, val_num)
            return ZcResponse.success(cmd.id, "done")

        # Command is not supported in the real firmware protocol
        return ZcResponse.error_response(cmd.id, f"Unknown command: {cmd.cmd}")

    def _record_audit(
        self,
        timestamp: str,
        request: str,
        response: str,
        start_time: float,
        fault: str | None = None,
    ) -> None:
        """Log audit entry to memory and persistent log file."""
        duration_ms = round((time.perf_counter() - start_time) * 1000, 3)
        entry = {
            "timestamp": timestamp,
            "request": request,
            "response": response.rstrip("\r\n"),
            "duration_ms": duration_ms,
            "fault": fault,
        }
        self.audit_logs.append(entry)

        if self.log_file_path:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
