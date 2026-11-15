"""Deterministic Fault Injection Tests."""

import time
import pytest

from mock_node.faults import FaultConfig, FaultType
from mock_node.node import MockNode


def test_fault_disconnection(esp32_node: MockNode) -> None:
    """Disconnection fault drops connection and returns None."""
    esp32_node.fault_injector.reset(
        FaultConfig(fault_type=FaultType.DISCONNECTION, target_cmd="gpio_read")
    )

    # ping is not targeted, succeeds
    resp_ping = esp32_node.process_line('{"id":"1","cmd":"ping"}\n')
    assert resp_ping == '{"id":"1","ok":true,"result":"pong"}\n'

    # gpio_read is targeted, drops connection (returns None)
    resp_read = esp32_node.process_line('{"id":"2","cmd":"gpio_read","args":{"pin":5}}\n')
    assert resp_read is None


def test_fault_fixed_latency(esp32_node: MockNode) -> None:
    """Latency fault injects measurable delay."""
    delay = 0.15  # 150ms
    esp32_node.fault_injector.reset(
        FaultConfig(fault_type=FaultType.LATENCY, delay_seconds=delay)
    )

    start = time.perf_counter()
    resp = esp32_node.process_line('{"id":"1","cmd":"ping"}\n')
    elapsed = time.perf_counter() - start

    assert resp == '{"id":"1","ok":true,"result":"pong"}\n'
    assert elapsed >= delay * 0.9  # At least 90% of delay satisfied


def test_fault_malformed_response(esp32_node: MockNode) -> None:
    """Malformed response returns corrupt non-JSON frame as configured."""
    esp32_node.fault_injector.reset(
        FaultConfig(
            fault_type=FaultType.MALFORMED_RESPONSE,
            malformed_payload="BAD_FRAME_{id}_GARBAGE\n",
        )
    )

    resp = esp32_node.process_line('{"id":"42","cmd":"ping"}\n')
    assert resp == "BAD_FRAME_42_GARBAGE\n"


def test_fault_stale_or_abnormal_value(esp32_node: MockNode) -> None:
    """Abnormal value fault returns configured out-of-range value."""
    esp32_node.fault_injector.reset(
        FaultConfig(
            fault_type=FaultType.STALE_OR_ABNORMAL_VALUE,
            target_cmd="gpio_read",
            abnormal_value="999",
        )
    )

    # Even though pin 5 is 1, fault returns 999
    resp = esp32_node.process_line('{"id":"3","cmd":"gpio_read","args":{"pin":5}}\n')
    assert resp == '{"id":"3","ok":true,"result":"999"}\n'


def test_fault_error_response(esp32_node: MockNode) -> None:
    """Error response fault returns well-formed protocol error."""
    esp32_node.fault_injector.reset(
        FaultConfig(
            fault_type=FaultType.ERROR_RESPONSE,
            error_message="Sensor thermal cut-off triggered",
        )
    )

    resp = esp32_node.process_line('{"id":"7","cmd":"ping"}\n')
    assert resp == '{"id":"7","ok":false,"result":"","error":"Sensor thermal cut-off triggered"}\n'


def test_fault_trigger_after_count(esp32_node: MockNode) -> None:
    """Fault only triggers after N requests."""
    esp32_node.fault_injector.reset(
        FaultConfig(
            fault_type=FaultType.ERROR_RESPONSE,
            error_message="Triggered after 2",
            trigger_after_count=2,
        )
    )

    # 1st request succeeds
    r1 = esp32_node.process_line('{"id":"1","cmd":"ping"}\n')
    assert '"ok":true' in r1

    # 2nd request succeeds
    r2 = esp32_node.process_line('{"id":"2","cmd":"ping"}\n')
    assert '"ok":true' in r2

    # 3rd request fails
    r3 = esp32_node.process_line('{"id":"3","cmd":"ping"}\n')
    assert '"ok":false' in r3
    assert "Triggered after 2" in r3


def test_fault_deterministic_prng_seed(esp32_node: MockNode) -> None:
    """Identical seeds produce identical sequence of fault triggers under probability < 1."""
    cfg1 = FaultConfig(
        fault_type=FaultType.ERROR_RESPONSE,
        probability=0.5,
        seed=12345,
    )
    esp32_node.fault_injector.reset(cfg1)
    seq1 = [
        '"ok":false' in (esp32_node.process_line(f'{{"id":"{i}","cmd":"ping"}}\n') or "")
        for i in range(10)
    ]

    # Reset with same seed
    cfg2 = FaultConfig(
        fault_type=FaultType.ERROR_RESPONSE,
        probability=0.5,
        seed=12345,
    )
    esp32_node.fault_injector.reset(cfg2)
    seq2 = [
        '"ok":false' in (esp32_node.process_line(f'{{"id":"{i}","cmd":"ping"}}\n') or "")
        for i in range(10)
    ]

    assert seq1 == seq2
    assert any(seq1)  # At least some faults triggered
    assert not all(seq1)  # Not all triggered
