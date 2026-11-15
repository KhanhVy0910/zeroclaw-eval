"""Tests for Hardware Gateway business endpoints (/api/v1/...)."""

import pytest
import httpx


@pytest.mark.asyncio
async def test_get_production_status_success(gateway_client: httpx.AsyncClient):
    """Verify GET /api/v1/n1/production/status returns uniform JSON structure."""
    resp = await gateway_client.get("/api/v1/n1/production/status")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["ok"] is True
    assert payload["error"] is None
    data = payload["data"]
    assert "fan" in data
    assert "status_led" in data
    assert "line_state" in data
    assert data["line_state"] == "running"
    assert data["fan"] == 0


@pytest.mark.asyncio
async def test_set_production_fan_toggle(gateway_client: httpx.AsyncClient):
    """Verify POST /api/v1/n1/production/fan modifies fan state and pin 2."""
    # Turn fan ON
    resp_on = await gateway_client.post(
        "/api/v1/n1/production/fan", json={"state": True}
    )
    assert resp_on.status_code == 200
    body_on = resp_on.json()
    assert body_on["ok"] is True
    assert body_on["data"]["fan"] == 1
    assert body_on["data"]["pin"] == 2
    assert body_on["data"]["pin_value"] == 1

    # Verify status reflects fan ON
    resp_status = await gateway_client.get("/api/v1/n1/production/status")
    assert resp_status.json()["data"]["fan"] == 1

    # Turn fan OFF
    resp_off = await gateway_client.post(
        "/api/v1/n1/production/fan", json={"state": 0}
    )
    assert resp_off.status_code == 200
    body_off = resp_off.json()
    assert body_off["ok"] is True
    assert body_off["data"]["fan"] == 0

    # Verify status reflects fan OFF
    resp_status2 = await gateway_client.get("/api/v1/n1/production/status")
    assert resp_status2.json()["data"]["fan"] == 0


@pytest.mark.asyncio
async def test_execute_generic_action_success(gateway_client: httpx.AsyncClient):
    """Verify POST /api/v1/{node_id}/execute works for generic commands."""
    resp = await gateway_client.post(
        "/api/v1/n1/execute",
        json={"action": "set_line_state", "params": {"line_state": "holding"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["line_state"] == "holding"

    # Status check
    status = await gateway_client.get("/api/v1/n1/production/status")
    assert status.json()["data"]["line_state"] == "holding"


@pytest.mark.asyncio
async def test_unknown_node_returns_invalid_argument(gateway_client: httpx.AsyncClient):
    """Verify request to non-existent node returns 400 INVALID_ARGUMENT."""
    resp = await gateway_client.get("/api/v1/unknown_node/production/status")
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "INVALID_ARGUMENT"
    assert "not found" in body["error"]["message"].lower() or "not exist" in body["error"]["message"].lower()


@pytest.mark.asyncio
async def test_unsupported_action_returns_invalid_argument(gateway_client: httpx.AsyncClient):
    """Verify unsupported action returns 400 INVALID_ARGUMENT."""
    resp = await gateway_client.post(
        "/api/v1/n1/execute",
        json={"action": "fly_to_moon", "params": {}},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_audit_log_recorded_on_requests(gateway_client: httpx.AsyncClient):
    """Verify that every business request generates an entry in audit log."""
    # Execute a couple of commands
    await gateway_client.get("/api/v1/n1/production/status")
    await gateway_client.post("/api/v1/n1/production/fan", json={"state": True})

    # Retrieve logs via admin endpoint
    resp = await gateway_client.get("/admin/logs")
    assert resp.status_code == 200
    logs = resp.json()["data"]["logs"]
    assert len(logs) >= 2

    # Check structure of latest log entry
    latest = logs[-1]
    assert latest["node_id"] == "n1"
    assert latest["action"] == "set_fan"
    assert latest["ok"] is True
    assert "timestamp" in latest
    assert "duration_ms" in latest
