"""Isolated Administration Channel for Mock Node.

Allows test runners and graders to inspect/modify node state and configure fault injection
without interfering with the serial wire protocol.
Provides both direct Python API and an optional HTTP endpoint on localhost.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any

from mock_node.faults import FaultConfig, FaultType
from mock_node.node import MockNode


class AdminChannel:
    """Administration Channel providing programmatic and HTTP access to MockNode."""

    def __init__(self, node: MockNode) -> None:
        self.node = node
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None

    # --- Programmatic Python API for Graders & Runners ---

    def get_state(self) -> dict[str, Any]:
        """Read the full state snapshot of the node."""
        return self.node.state.snapshot()

    def get_pin(self, pin: int) -> int:
        """Read current logical value of a GPIO pin."""
        return self.node.state.get_pin_value(pin)

    def set_pin(self, pin: int, value: int) -> None:
        """Directly set the logical value of a GPIO pin from outside."""
        self.node.state.set_pin_value(pin, value)

    def set_fault(self, fault_config: FaultConfig) -> None:
        """Inject or reconfigure a deterministic fault."""
        self.node.fault_injector.reset(fault_config)

    def clear_faults(self) -> None:
        """Clear active fault injection."""
        self.node.fault_injector.reset(FaultConfig(fault_type=FaultType.NONE))

    def get_audit_logs(self) -> list[dict[str, Any]]:
        """Retrieve complete ground-truth audit logs of all requests and responses."""
        return list(self.node.audit_logs)

    def clear_audit_logs(self) -> None:
        """Clear internal audit log entries."""
        self.node.audit_logs.clear()

    # --- HTTP Admin Server ---

    def start_http_server(self, host: str = "127.0.0.1", port: int = 8800) -> int:
        """Start an HTTP admin server on a background thread."""
        if self._server is not None:
            return self._server.server_port

        channel_self = self

        class AdminHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                # Silence standard request logging to avoid cluttering test outputs
                pass

            def do_GET(self) -> None:
                if self.path == "/admin/state":
                    self._send_json(200, channel_self.get_state())
                elif self.path == "/admin/logs":
                    self._send_json(200, channel_self.get_audit_logs())
                elif self.path.startswith("/admin/pins/"):
                    try:
                        pin_str = self.path.split("/")[-1]
                        val = channel_self.get_pin(int(pin_str))
                        self._send_json(200, {"pin": int(pin_str), "value": val})
                    except Exception as exc:
                        self._send_json(400, {"error": str(exc)})
                else:
                    self._send_json(404, {"error": "Not found"})

            def do_POST(self) -> None:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    payload = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "Invalid JSON body"})
                    return

                if self.path.startswith("/admin/pins/"):
                    try:
                        pin_str = self.path.split("/")[-1]
                        val = int(payload.get("value", 0))
                        channel_self.set_pin(int(pin_str), val)
                        self._send_json(200, {"pin": int(pin_str), "value": val, "status": "ok"})
                    except Exception as exc:
                        self._send_json(400, {"error": str(exc)})
                elif self.path == "/admin/fault":
                    try:
                        fault_type_str = payload.get("fault_type", "none")
                        cfg = FaultConfig(
                            fault_type=FaultType(fault_type_str),
                            target_cmd=payload.get("target_cmd"),
                            target_pin=payload.get("target_pin"),
                            delay_seconds=float(payload.get("delay_seconds", 0.0)),
                            error_message=payload.get("error_message", "Hardware fault simulated"),
                            abnormal_value=payload.get("abnormal_value", "999"),
                            trigger_after_count=int(payload.get("trigger_after_count", 0)),
                            seed=int(payload.get("seed", 42)),
                        )
                        channel_self.set_fault(cfg)
                        self._send_json(200, {"status": "ok", "fault_type": fault_type_str})
                    except Exception as exc:
                        self._send_json(400, {"error": str(exc)})
                elif self.path == "/admin/fault/clear":
                    channel_self.clear_faults()
                    self._send_json(200, {"status": "ok", "fault_type": "none"})
                else:
                    self._send_json(404, {"error": "Not found"})

            def _send_json(self, status: int, data: Any) -> None:
                body = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer((host, port), AdminHandler)
        actual_port = self._server.server_port
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        return actual_port

    def stop_http_server(self) -> None:
        """Stop background HTTP admin server."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._server_thread = None


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP Server for concurrent admin requests."""

    daemon_threads = True
    allow_reuse_address = True
