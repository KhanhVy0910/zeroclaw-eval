"""Protocol Verification Tests with Golden Fixtures.

All golden fixtures are drawn directly from:
- firmware/zeroclaw-fw-protocol/src/command.rs
- firmware/zeroclaw-fw-protocol/src/response.rs
- crates/zeroclaw-hardware/examples/esp32_sim.rs
- docs/findings.md (Question 2)
"""

import json
from pathlib import Path
import pytest

from mock_node.node import MockNode


# ==============================================================================
# GOLDEN FIXTURES (Source of truth from ZeroClaw codebase)
# ==============================================================================

GOLDEN_PING_REQUEST = '{"id":"1","cmd":"ping"}\n'
GOLDEN_PING_RESPONSE = '{"id":"1","ok":true,"result":"pong"}\n'

GOLDEN_CAPABILITIES_REQUEST = '{"id":"5","cmd":"capabilities"}\n'

GOLDEN_GPIO_READ_REQUEST = '{"id":"3","cmd":"gpio_read","args":{"pin":5}}\n'
GOLDEN_GPIO_READ_RESPONSE = '{"id":"3","ok":true,"result":"1"}\n'

GOLDEN_GPIO_WRITE_REQUEST = '{"id":"2","cmd":"gpio_write","args":{"pin":13,"value":1}}\n'
GOLDEN_GPIO_WRITE_RESPONSE = '{"id":"2","ok":true,"result":"done"}\n'

GOLDEN_GPIO_WRITE_WHITESPACE_REQUEST = '{"id":"1", "cmd": "gpio_write", "args": {"pin":13,"value":1}}\n'

GOLDEN_UNKNOWN_CMD_REQUEST = '{"id":"4","cmd":"reboot"}\n'
GOLDEN_UNKNOWN_CMD_RESPONSE_SUBSTRING = '"ok":false,"result":"","error":"Unknown command: reboot"'


def test_golden_ping(esp32_node: MockNode) -> None:
    """Golden test: ping command returns pong."""
    response = esp32_node.process_line(GOLDEN_PING_REQUEST)
    assert response == GOLDEN_PING_RESPONSE


def test_golden_capabilities(esp32_node: MockNode) -> None:
    """Golden test: capabilities command returns JSON description with GPIO pins and pin_devices."""
    response = esp32_node.process_line(GOLDEN_CAPABILITIES_REQUEST)
    assert response is not None
    assert response.endswith("\n")

    parsed = json.loads(response.strip())
    assert parsed["id"] == "5"
    assert parsed["ok"] is True

    # The result field itself is stringified JSON
    caps_data = json.loads(parsed["result"])
    assert caps_data["board"] == "esp32-sim-smartroom"
    assert set(caps_data["gpio"]) == {2, 5, 12, 13, 14}
    assert "reading_lamp" in caps_data["pin_devices"]["12"]["device"]
    assert "motion_sensor" in caps_data["pin_devices"]["5"]["device"]


def test_golden_gpio_read(esp32_node: MockNode) -> None:
    """Golden test: gpio_read returns pin value (motion sensor on pin 5 returns 1)."""
    response = esp32_node.process_line(GOLDEN_GPIO_READ_REQUEST)
    assert response == GOLDEN_GPIO_READ_RESPONSE


def test_golden_gpio_write(esp32_node: MockNode) -> None:
    """Golden test: gpio_write sets pin value and returns done."""
    # Initially pin 13 is 0
    assert esp32_node.state.get_pin_value(13) == 0

    response = esp32_node.process_line(GOLDEN_GPIO_WRITE_REQUEST)
    assert response == GOLDEN_GPIO_WRITE_RESPONSE
    assert esp32_node.state.get_pin_value(13) == 1

    # Now read back pin 13
    read_resp = esp32_node.process_line('{"id":"10","cmd":"gpio_read","args":{"pin":13}}\n')
    assert read_resp == '{"id":"10","ok":true,"result":"1"}\n'


def test_golden_whitespace_resilience(esp32_node: MockNode) -> None:
    """Golden test: request JSON containing whitespace is correctly parsed."""
    response = esp32_node.process_line(GOLDEN_GPIO_WRITE_WHITESPACE_REQUEST)
    assert response == '{"id":"1","ok":true,"result":"done"}\n'


def test_golden_unknown_command(esp32_node: MockNode) -> None:
    """Golden test: unknown command returns error format without crashing."""
    response = esp32_node.process_line(GOLDEN_UNKNOWN_CMD_REQUEST)
    assert response is not None
    assert GOLDEN_UNKNOWN_CMD_RESPONSE_SUBSTRING in response
    parsed = json.loads(response.strip())
    assert parsed["id"] == "4"
    assert parsed["ok"] is False
    assert parsed["result"] == ""
    assert "Unknown command: reboot" in parsed["error"]


def test_invalid_pin_returns_error(esp32_node: MockNode) -> None:
    """Golden test: reading or writing an unsupported pin returns error in protocol format."""
    # Read unsupported pin 99
    resp = esp32_node.process_line('{"id":"99","cmd":"gpio_read","args":{"pin":99}}\n')
    parsed = json.loads(resp.strip())
    assert parsed["id"] == "99"
    assert parsed["ok"] is False
    assert parsed["result"] == ""
    assert "Invalid pin 99" in parsed["error"]

    # Write unsupported pin 99
    resp_write = esp32_node.process_line('{"id":"100","cmd":"gpio_write","args":{"pin":99,"value":1}}\n')
    parsed_write = json.loads(resp_write.strip())
    assert parsed_write["id"] == "100"
    assert parsed_write["ok"] is False
    assert parsed_write["result"] == ""
    assert "pin 99 not configured" in parsed_write["error"]


def test_malformed_json_request(esp32_node: MockNode) -> None:
    """Golden test: corrupt JSON line yields parse error response with id 0."""
    resp = esp32_node.process_line('{"id": 1, invalid_json\n')
    assert resp is not None
    parsed = json.loads(resp.strip())
    assert parsed["id"] == "0"
    assert parsed["ok"] is False
    assert parsed["result"] == ""
    assert "parse error" in parsed["error"]
