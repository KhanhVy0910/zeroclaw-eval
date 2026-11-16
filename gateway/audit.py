"""Command audit logger for Hardware Gateway.

Records every business request and response with timestamps into a dedicated JSONL file.
Serves as the authoritative source of truth for safety graders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditLogger:
    """Append-only audit logger for node commands."""

    def __init__(self, log_path: Optional[Path] = None, log_file: Optional[Path] = None) -> None:
        target = log_path or log_file
        if target is None:
            target = Path(__file__).resolve().parent / "data" / "command_log.jsonl"
        self.log_path = Path(target)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_command(
        self,
        node_id: str,
        endpoint: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        response: Optional[Dict[str, Any]] = None,
        ok: bool = True,
        duration_ms: float = 0.0,
        request_id: Optional[str] = None,
        error: Optional[Dict[str, Any]] = None,
        decision: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an executed command and write it to the audit log synchronously."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Determine decision and rejection reason
        dec = decision or ("accepted" if ok else "rejected")
        rejection_reason = reason
        if not ok and rejection_reason is None and error:
            if isinstance(error, dict):
                rejection_reason = error.get("message") or str(error)
            else:
                rejection_reason = str(error)

        entry = {
            "timestamp": timestamp,
            "request_id": request_id,
            "node_id": node_id.strip().lower() if node_id else "",
            "tool": action,
            "action": action,
            "endpoint": endpoint,
            "params": params or {},
            "ok": ok,
            "decision": dec,
            "reason": rejection_reason,
            "duration_ms": round(duration_ms, 2),
            "response": response,
            "error": error,
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return entry

    async def log(
        self,
        node_id: str,
        action: str,
        endpoint: str,
        request_payload: Optional[Dict[str, Any]] = None,
        response_payload: Optional[Dict[str, Any]] = None,
        status: str = "OK",
        latency_ms: float = 0.0,
        request_id: Optional[str] = None,
        decision: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async convenience method to log request and response."""
        ok = status == "OK"
        error_val = None
        if not ok and isinstance(response_payload, dict) and "error" in response_payload:
            error_val = response_payload["error"]

        return self.record_command(
            node_id=node_id,
            endpoint=endpoint,
            action=action,
            params=request_payload,
            response=response_payload,
            ok=ok,
            duration_ms=latency_ms,
            request_id=request_id,
            error=error_val,
            decision=decision,
            reason=reason,
        )

    async def get_logs(
        self, node_id: Optional[str] = None, limit: Optional[int] = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve recorded logs, optionally filtered by node_id."""
        if not self.log_path.exists():
            return []

        entries = []
        normalized_node = node_id.strip().lower() if node_id else None

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if normalized_node is None or entry.get("node_id") == normalized_node:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

        if limit and limit > 0:
            return entries[-limit:]
        return entries

    async def clear(self) -> None:
        """Clear the command log file."""
        if self.log_path.exists():
            with open(self.log_path, "w", encoding="utf-8") as f:
                pass
