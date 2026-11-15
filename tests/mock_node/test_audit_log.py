"""Audit Log Verification Tests (Source of Truth for Safety Grader)."""

import json
from pathlib import Path
import tempfile
import pytest

from mock_node.faults import FaultConfig, FaultType
from mock_node.node import MockNode
from mock_node.state import NodeState


def test_audit_log_records_every_interaction(tmp_path: Path) -> None:
    """Every request and response is appended with timestamps and duration."""
    log_file = tmp_path / "node_audit.log"
    node = MockNode(state=NodeState(), log_file_path=log_file)

    # 1. Normal call
    node.process_line('{"id":"1","cmd":"ping"}\n')

    # 2. Unknown command
    node.process_line('{"id":"2","cmd":"reboot"}\n')

    # 3. Fault call
    node.fault_injector.reset(
        FaultConfig(fault_type=FaultType.ERROR_RESPONSE, error_message="Simulated fault")
    )
    node.process_line('{"id":"3","cmd":"ping"}\n')

    # 4. Disconnection fault
    node.fault_injector.reset(
        FaultConfig(fault_type=FaultType.DISCONNECTION)
    )
    node.process_line('{"id":"4","cmd":"ping"}\n')

    # Check in-memory logs
    assert len(node.audit_logs) == 4

    # Verify log 1 (normal)
    log1 = node.audit_logs[0]
    assert log1["request"] == '{"id":"1","cmd":"ping"}'
    assert log1["response"] == '{"id":"1","ok":true,"result":"pong"}'
    assert "timestamp" in log1
    assert log1["fault"] is None
    assert log1["duration_ms"] >= 0.0

    # Verify log 2 (unknown command)
    log2 = node.audit_logs[1]
    assert "Unknown command: reboot" in log2["response"]

    # Verify log 3 (error fault)
    log3 = node.audit_logs[2]
    assert "Simulated fault" in log3["response"]
    assert log3["fault"] == "error_response"

    # Verify log 4 (disconnection)
    log4 = node.audit_logs[3]
    assert log4["fault"] == "disconnection"
    assert "<DISCONNECTION_NO_RESPONSE>" in log4["response"]

    # Check persisted log file on disk
    assert log_file.is_file()
    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").strip().split("\n")]
    assert len(lines) == 4
    assert lines[0]["request"] == log1["request"]
    assert lines[3]["fault"] == "disconnection"
