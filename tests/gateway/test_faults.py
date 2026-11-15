"""Tests for deterministic fault injection engine in Hardware Gateway."""

import time
import pytest
import httpx


@pytest.mark.asyncio
async def test_fault_disconnection(gateway_client: httpx.AsyncClient):
    """Verify DISCONNECTED fault triggers 503 CONNECTION_ERROR."""
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "DISCONNECTED",
            "node_id": "n1",
            "action": "*",
            "params": {"message": "Hardware link physically disconnected"},
            "trigger_count": 1,
        },
    )

    # 1st call should trigger DISCONNECTED
    resp = await gateway_client.get("/api/v1/n1/production/status")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "CONNECTION_ERROR"
    assert "physically disconnected" in body["error"]["message"]

    # 2nd call should succeed because trigger_count was 1
    resp2 = await gateway_client.get("/api/v1/n1/production/status")
    assert resp2.status_code == 200
    assert resp2.json()["ok"] is True


@pytest.mark.asyncio
async def test_fault_fixed_latency(gateway_client: httpx.AsyncClient):
    """Verify LATENCY_MS fault delays response by configured duration."""
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "LATENCY_MS",
            "node_id": "n1",
            "action": "set_fan",
            "params": {"latency_ms": 150},
            "trigger_count": 1,
        },
    )

    t0 = time.time()
    resp = await gateway_client.post("/api/v1/n1/production/fan", json={"state": True})
    elapsed = time.time() - t0

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert elapsed >= 0.14, f"Expected latency >= 140ms, got {elapsed*1000:.1f}ms"


@pytest.mark.asyncio
async def test_fault_malformed_response(gateway_client: httpx.AsyncClient):
    """Verify MALFORMED_RESPONSE fault returns raw invalid payload."""
    raw_payload = "CORRUPTED_SERIAL_STREAM_ERROR_CHECKSUM_FAILED"
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "MALFORMED_RESPONSE",
            "node_id": "n1",
            "action": "get_status",
            "params": {"raw_text": raw_payload},
            "trigger_count": 1,
        },
    )

    resp = await gateway_client.get("/api/v1/n1/production/status")
    assert resp.status_code == 200
    # Response is raw string, not valid JSON
    assert resp.text == raw_payload


@pytest.mark.asyncio
async def test_fault_abnormal_value(gateway_client: httpx.AsyncClient):
    """Verify ABNORMAL_VALUE alters sensor field reading."""
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "ABNORMAL_VALUE",
            "node_id": "n1",
            "action": "get_status",
            "params": {"field": "temperature", "value": 999.9},
            "trigger_count": 1,
        },
    )

    resp = await gateway_client.get("/api/v1/n1/production/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["temperature"] == 999.9


@pytest.mark.asyncio
async def test_fault_stale_value(gateway_client: httpx.AsyncClient):
    """Verify STALE_VALUE returns frozen stale reading."""
    stale_payload = {"fan": 0, "status_led": 0, "line_state": "stale_frozen", "timestamp": "2000-01-01T00:00:00Z"}
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "STALE_VALUE",
            "node_id": "n1",
            "action": "get_status",
            "params": {"stale_data": stale_payload},
            "trigger_count": 1,
        },
    )

    resp = await gateway_client.get("/api/v1/n1/production/status")
    assert resp.status_code == 200
    assert resp.json()["data"]["line_state"] == "stale_frozen"


@pytest.mark.asyncio
async def test_fault_error_response_device_error(gateway_client: httpx.AsyncClient):
    """Verify ERROR_RESPONSE injects DEVICE_ERROR."""
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "ERROR_RESPONSE",
            "node_id": "n1",
            "action": "set_fan",
            "params": {"code": "DEVICE_ERROR", "message": "Motor driver overcurrent trip"},
            "trigger_count": 1,
        },
    )

    resp = await gateway_client.post("/api/v1/n1/production/fan", json={"state": True})
    assert resp.status_code == 500
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "DEVICE_ERROR"
    assert "overcurrent trip" in body["error"]["message"]
