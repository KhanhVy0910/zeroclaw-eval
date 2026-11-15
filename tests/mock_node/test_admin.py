"""Administration Channel Tests (Programmatic and HTTP)."""

import json
import urllib.request
import pytest

from mock_node.admin import AdminChannel
from mock_node.faults import FaultConfig, FaultType
from mock_node.node import MockNode


def test_admin_programmatic_read_write_state(esp32_node: MockNode) -> None:
    """Admin channel can inspect and modify state directly."""
    admin = AdminChannel(esp32_node)

    # Inspect initial state
    assert admin.get_pin(13) == 0
    snapshot = admin.get_state()
    assert snapshot["board"] == "esp32-sim-smartroom"
    assert snapshot["pins"][13]["value"] == 0

    # Modify state via admin
    admin.set_pin(13, 1)
    assert admin.get_pin(13) == 1

    # Wire protocol call now sees the new state
    resp = esp32_node.process_line('{"id":"1","cmd":"gpio_read","args":{"pin":13}}\n')
    assert resp == '{"id":"1","ok":true,"result":"1"}\n'


def test_admin_fault_injection_control(esp32_node: MockNode) -> None:
    """Admin channel can set and clear faults dynamically."""
    admin = AdminChannel(esp32_node)

    # Normal call
    r1 = esp32_node.process_line('{"id":"1","cmd":"ping"}\n')
    assert '"ok":true' in r1

    # Admin injects error fault
    admin.set_fault(
        FaultConfig(fault_type=FaultType.ERROR_RESPONSE, error_message="Admin forced error")
    )
    r2 = esp32_node.process_line('{"id":"2","cmd":"ping"}\n')
    assert '"ok":false' in r2
    assert "Admin forced error" in r2

    # Admin clears fault
    admin.clear_faults()
    r3 = esp32_node.process_line('{"id":"3","cmd":"ping"}\n')
    assert '"ok":true' in r3


def test_admin_http_endpoints(esp32_node: MockNode) -> None:
    """Admin HTTP server serves status and controls state via REST API."""
    admin = AdminChannel(esp32_node)
    port = admin.start_http_server(port=0)  # Bind to free OS port
    base_url = f"http://127.0.0.1:{port}"

    try:
        # GET /admin/state
        req = urllib.request.urlopen(f"{base_url}/admin/state")
        assert req.status == 200
        data = json.loads(req.read().decode())
        assert data["board"] == "esp32-sim-smartroom"

        # GET /admin/pins/12
        req_pin = urllib.request.urlopen(f"{base_url}/admin/pins/12")
        assert req_pin.status == 200
        data_pin = json.loads(req_pin.read().decode())
        assert data_pin["pin"] == 12
        assert data_pin["value"] == 0

        # POST /admin/pins/12 to set value = 1
        post_req = urllib.request.Request(
            f"{base_url}/admin/pins/12",
            data=json.dumps({"value": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(post_req) as post_resp:
            assert post_resp.status == 200
            res = json.loads(post_resp.read().decode())
            assert res["value"] == 1

        # Check in node that pin 12 is indeed 1
        assert admin.get_pin(12) == 1

        # POST /admin/fault
        fault_payload = json.dumps(
            {"fault_type": "error_response", "error_message": "HTTP injected error"}
        ).encode("utf-8")
        fault_req = urllib.request.Request(
            f"{base_url}/admin/fault",
            data=fault_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(fault_req) as f_resp:
            assert f_resp.status == 200

        # Wire protocol now returns the injected error
        wire_resp = esp32_node.process_line('{"id":"10","cmd":"ping"}\n')
        assert "HTTP injected error" in wire_resp

        # POST /admin/fault/clear
        clear_req = urllib.request.Request(
            f"{base_url}/admin/fault/clear",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(clear_req) as c_resp:
            assert c_resp.status == 200

        # Back to normal
        wire_resp2 = esp32_node.process_line('{"id":"11","cmd":"ping"}\n')
        assert '"ok":true' in wire_resp2
    finally:
        admin.stop_http_server()
