"""Tests for Hardware Gateway Admin endpoints (/admin/...)."""

import pytest
import httpx


@pytest.mark.asyncio
async def test_admin_get_and_set_node_state(gateway_client: httpx.AsyncClient):
    """Verify admin can inspect and directly modify in-memory node state."""
    # Get initial state of N1
    resp = await gateway_client.get("/admin/nodes/n1/state")
    assert resp.status_code == 200
    initial_state = resp.json()["data"]
    assert initial_state["fan"] == 0

    # Admin updates temperature and fan
    update_resp = await gateway_client.post(
        "/admin/nodes/n1/state",
        json={"state": {"fan": 1, "temperature": 88.5}},
    )
    assert update_resp.status_code == 200
    updated_state = update_resp.json()["data"]
    assert updated_state["fan"] == 1
    assert updated_state["temperature"] == 88.5

    # Verify via business endpoint
    status_resp = await gateway_client.get("/api/v1/n1/production/status")
    assert status_resp.json()["data"]["fan"] == 1
    assert status_resp.json()["data"]["temperature"] == 88.5


@pytest.mark.asyncio
async def test_admin_reset_to_fixture(gateway_client: httpx.AsyncClient):
    """Verify admin reset restores fixture values and clears faults."""
    # Modify state
    await gateway_client.post(
        "/admin/nodes/n1/state", json={"state": {"fan": 1, "line_state": "holding"}}
    )
    # Add a fault
    await gateway_client.post(
        "/admin/faults",
        json={"fault_type": "DISCONNECTED", "node_id": "n1"},
    )

    # Perform Admin Reset
    reset_resp = await gateway_client.post("/admin/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["data"]["reset"] is True

    # Verify state restored to initial fixture
    state_resp = await gateway_client.get("/admin/nodes/n1/state")
    restored_state = state_resp.json()["data"]
    assert restored_state["fan"] == 0
    assert restored_state["line_state"] == "running"

    # Verify fault cleared (status call succeeds without 503)
    status_resp = await gateway_client.get("/api/v1/n1/production/status")
    assert status_resp.status_code == 200


@pytest.mark.asyncio
async def test_emergency_stop_interlock(gateway_client: httpx.AsyncClient):
    """Verify Emergency Stop engaged on N4 blocks line start with SAFETY_VIOLATION, while fan/stop are allowed."""
    # Ensure initial state: fan control works
    resp1 = await gateway_client.post(
        "/api/v1/n1/production/fan", json={"state": True}
    )
    assert resp1.status_code == 200

    # Engage Emergency Stop on N4 via admin endpoint
    await gateway_client.post(
        "/admin/nodes/n4/state", json={"state": {"emergency_stop": True}}
    )

    # Attempt line start on N1: MUST be blocked with 403 SAFETY_VIOLATION
    resp_blocked = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "start"}
    )
    assert resp_blocked.status_code == 403
    body = resp_blocked.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "SAFETY_VIOLATION"
    assert "Emergency Stop" in body["error"]["message"]

    # Rule 3: Fan control and line stop/hold are STILL ALLOWED when E-Stop is active
    resp_fan = await gateway_client.post(
        "/api/v1/n1/production/fan", json={"state": False}
    )
    assert resp_fan.status_code == 200

    resp_stop = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "stop"}
    )
    assert resp_stop.status_code == 200

    # Release Emergency Stop via admin endpoint
    await gateway_client.post(
        "/admin/nodes/n4/state", json={"state": {"emergency_stop": False}}
    )

    # Line start works again
    resp_start = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "start"}
    )
    assert resp_start.status_code == 200
    resp_released = await gateway_client.post(
        "/api/v1/n1/production/fan", json={"state": False}
    )
    assert resp_released.status_code == 200
    assert resp_released.json()["ok"] is True


@pytest.mark.asyncio
async def test_admin_logs_filtering_and_clearing(gateway_client: httpx.AsyncClient):
    """Verify log query, node filtering, and clear."""
    # Clear logs first
    clear_resp = await gateway_client.post("/admin/logs/clear")
    assert clear_resp.status_code == 200

    # Execute calls to n1 and n2
    await gateway_client.get("/api/v1/n1/production/status")
    await gateway_client.post(
        "/api/v1/n2/execute", json={"action": "get_status", "params": {}}
    )

    # Query all logs
    all_logs = await gateway_client.get("/admin/logs")
    assert len(all_logs.json()["data"]["logs"]) == 2

    # Query n1 logs only
    n1_logs = await gateway_client.get("/admin/logs?node_id=n1")
    assert len(n1_logs.json()["data"]["logs"]) == 1
    assert n1_logs.json()["data"]["logs"][0]["node_id"] == "n1"

    # Clear logs
    await gateway_client.post("/admin/logs/clear")
    cleared = await gateway_client.get("/admin/logs")
    assert len(cleared.json()["data"]["logs"]) == 0
