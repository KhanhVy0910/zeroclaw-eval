"""Comprehensive tests for Hardware Gateway 4-Node architecture (Task T5).

Verifies:
1. All 4 nodes (N1, N2, N3, N4) respond correctly on domain endpoints.
2. Read-only nodes and sensors strictly reject write operations with SAFETY_VIOLATION.
3. Emergency Stop on N4 blocks actuation/control across all nodes while allowing reads.
4. Emergency Stop cannot be altered via business endpoints (only via admin).
5. Fault injection on one node is strictly isolated from other nodes.
6. Concurrent calls to Node N4 (e.g. from maintenance and safety) execute sequentially.
7. Fixtures can be loaded dynamically for different scenarios.
"""

import asyncio
import time
from pathlib import Path
import pytest
import httpx


@pytest.mark.asyncio
async def test_all_four_nodes_respond_correctly(gateway_client: httpx.AsyncClient):
    """Verify all 4 nodes return correct structured domain responses."""
    # ── NODE N1: ESP32 Production Control ─────────────────────
    r_n1_status = await gateway_client.get("/api/v1/n1/production/status")
    assert r_n1_status.status_code == 200
    n1_data = r_n1_status.json()["data"]
    assert n1_data["fan"] == 0
    assert n1_data["status_led"] == 0
    assert n1_data["line_state"] == "running"
    assert n1_data["machine_status"] == "ok"
    assert n1_data["temperature"] == 45.2
    assert n1_data["humidity"] == 82.0

    # Actuate N1 line_state
    r_n1_line = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "holding"}
    )
    assert r_n1_line.status_code == 200
    assert r_n1_line.json()["data"]["line_state"] == "holding"

    # Actuate N1 fan
    r_n1_fan = await gateway_client.post(
        "/api/v1/n1/production/fan", json={"state": True}
    )
    assert r_n1_fan.status_code == 200
    assert r_n1_fan.json()["data"]["fan"] == 1

    # ── NODE N2: Pico W Environmental Monitoring ──────────────
    r_n2_status = await gateway_client.get("/api/v1/n2/environment/status")
    assert r_n2_status.status_code == 200
    n2_data = r_n2_status.json()["data"]
    assert n2_data["temperature"] == 24.5
    assert n2_data["humidity"] == 60.0

    r_n2_temp = await gateway_client.get("/api/v1/n2/environment/temperature")
    assert r_n2_temp.status_code == 200
    assert r_n2_temp.json()["data"]["temperature"] == 24.5
    assert r_n2_temp.json()["data"]["unit"] == "C"

    r_n2_hum = await gateway_client.get("/api/v1/n2/environment/humidity")
    assert r_n2_hum.status_code == 200
    assert r_n2_hum.json()["data"]["humidity"] == 60.0
    assert r_n2_hum.json()["data"]["unit"] == "%"

    # ── NODE N3: Arduino Uno Warehouse & Materials ───────────
    r_n3_status = await gateway_client.get("/api/v1/n3/warehouse/status")
    assert r_n3_status.status_code == 200
    n3_data = r_n3_status.json()["data"]
    assert n3_data["rfid_tag"] == "BATCH-A100"
    assert n3_data["rfid_valid"] is True
    assert n3_data["distance"] == 15.0
    assert n3_data["gate_open"] is False
    assert n3_data["inventory"] == 150

    r_n3_rfid = await gateway_client.get("/api/v1/n3/warehouse/rfid")
    assert r_n3_rfid.status_code == 200
    assert r_n3_rfid.json()["data"]["batch"] == "BATCH-A100"
    assert r_n3_rfid.json()["data"]["valid"] is True

    r_n3_dist = await gateway_client.get("/api/v1/n3/warehouse/distance")
    assert r_n3_dist.status_code == 200
    assert r_n3_dist.json()["data"]["distance"] == 15.0

    r_n3_inv = await gateway_client.get("/api/v1/n3/warehouse/inventory")
    assert r_n3_inv.status_code == 200
    assert r_n3_inv.json()["data"]["inventory"] == 150

    # Actuate N3 servo gate
    r_n3_gate = await gateway_client.post(
        "/api/v1/n3/warehouse/gate", json={"state": "open"}
    )
    assert r_n3_gate.status_code == 200
    assert r_n3_gate.json()["data"]["gate_open"] is True

    # ── NODE N4: STM32 Nucleo Health & Safety ────────────────
    r_n4_status = await gateway_client.get("/api/v1/n4/maintenance/status")
    assert r_n4_status.status_code == 200
    n4_data = r_n4_status.json()["data"]
    assert n4_data["vibration"] == 0.12
    assert n4_data["machine_health"] == "nominal"
    assert n4_data["emergency_stop"] is False

    r_n4_vib = await gateway_client.get("/api/v1/n4/maintenance/vibration")
    assert r_n4_vib.status_code == 200
    assert r_n4_vib.json()["data"]["vibration"] == 0.12

    r_n4_health = await gateway_client.get("/api/v1/n4/maintenance/health")
    assert r_n4_health.status_code == 200
    assert r_n4_health.json()["data"]["machine_health"] == "nominal"

    r_n4_estop = await gateway_client.get("/api/v1/n4/safety/emergency")
    assert r_n4_estop.status_code == 200
    assert r_n4_estop.json()["data"]["emergency_stop"] is False
    assert r_n4_estop.json()["data"]["status"] == "RELEASED"

    r_n4_check = await gateway_client.get("/api/v1/n4/safety/check")
    assert r_n4_check.status_code == 200
    assert r_n4_check.json()["data"]["allowed"] is True


@pytest.mark.asyncio
async def test_read_only_nodes_reject_writes(gateway_client: httpx.AsyncClient):
    """Verify that read-only nodes and read-only sensors reject write attempts."""
    # N2 (Pico W) is strictly read-only
    r_n2_write = await gateway_client.post(
        "/api/v1/n2/execute", json={"action": "set_temperature", "params": {"temperature": 30.0}}
    )
    assert r_n2_write.status_code == 403
    body_n2 = r_n2_write.json()
    assert body_n2["ok"] is False
    assert body_n2["error"]["code"] == "SAFETY_VIOLATION"
    assert "read-only" in body_n2["error"]["message"].lower()

    # N3: RFID and inventory cannot be overwritten via domain action
    r_n3_rfid = await gateway_client.post(
        "/api/v1/n3/execute", json={"action": "set_rfid", "params": {"rfid_tag": "HACK"}}
    )
    assert r_n3_rfid.status_code == 403
    assert r_n3_rfid.json()["error"]["code"] == "SAFETY_VIOLATION"

    # N4: Machine health cannot be set via business action
    r_n4_write = await gateway_client.post(
        "/api/v1/n4/execute", json={"action": "set_machine_health", "params": {"machine_health": "bad"}}
    )
    assert r_n4_write.status_code == 403
    assert r_n4_write.json()["error"]["code"] == "SAFETY_VIOLATION"


@pytest.mark.asyncio
async def test_emergency_stop_blocks_control_actions_across_nodes(gateway_client: httpx.AsyncClient):
    """Verify that activating Emergency Stop blocks all control actions and check_operation fails."""
    # Initially E-Stop is released
    check_before = await gateway_client.get("/api/v1/n4/safety/check")
    assert check_before.json()["data"]["allowed"] is True

    # 1. Admin engages Emergency Stop
    r_engage = await gateway_client.post(
        "/admin/nodes/n4/emergency_stop", json={"emergency_stop": True}
    )
    assert r_engage.status_code == 200
    assert r_engage.json()["data"]["emergency_stop"] is True

    # 2. Verify safety check immediately reflects refusal
    check_during = await gateway_client.get("/api/v1/n4/safety/check")
    assert check_during.status_code == 200
    assert check_during.json()["data"]["allowed"] is False
    assert "emergency stop" in check_during.json()["data"]["reason"].lower()

    # 3. Under Rule 3: Line start on N1 MUST BE REJECTED with 403, but fan and stop are allowed
    r_line_start = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "start"}
    )
    assert r_line_start.status_code == 403
    assert r_line_start.json()["ok"] is False
    assert r_line_start.json()["error"]["code"] == "SAFETY_VIOLATION"
    assert "emergency stop" in r_line_start.json()["error"]["message"].lower()

    # Fan control and stop/hold are allowed during E-Stop
    r_fan = await gateway_client.post("/api/v1/n1/production/fan", json={"state": True})
    assert r_fan.status_code == 200
    assert r_fan.json()["ok"] is True

    r_stop = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "stop"}
    )
    assert r_stop.status_code == 200

    # 4. Under Rule 3: Gate OPEN on N3 MUST BE REJECTED with 403, but CLOSE is allowed
    r_gate_open = await gateway_client.post(
        "/api/v1/n3/warehouse/gate", json={"state": "open"}
    )
    assert r_gate_open.status_code == 403
    assert r_gate_open.json()["error"]["code"] == "SAFETY_VIOLATION"

    r_gate_close = await gateway_client.post(
        "/api/v1/n3/warehouse/gate", json={"state": "closed"}
    )
    assert r_gate_close.status_code == 200

    # 5. READ actions across all nodes must STILL SUCCEED
    r_n1_read = await gateway_client.get("/api/v1/n1/production/status")
    assert r_n1_read.status_code == 200
    assert r_n1_read.json()["ok"] is True

    r_n2_read = await gateway_client.get("/api/v1/n2/environment/status")
    assert r_n2_read.status_code == 200

    r_n3_read = await gateway_client.get("/api/v1/n3/warehouse/status")
    assert r_n3_read.status_code == 200

    r_n4_read = await gateway_client.get("/api/v1/n4/maintenance/status")
    assert r_n4_read.status_code == 200

    # 6. Admin releases Emergency Stop
    r_release = await gateway_client.post(
        "/admin/nodes/n4/emergency_stop", json={"emergency_stop": False}
    )
    assert r_release.status_code == 200
    assert r_release.json()["data"]["emergency_stop"] is False

    # 7. Now control actions succeed again
    r_fan_after = await gateway_client.post("/api/v1/n1/production/fan", json={"state": True})
    assert r_fan_after.status_code == 200
    assert r_fan_after.json()["data"]["fan"] == 1

    r_gate_after = await gateway_client.post("/api/v1/n3/warehouse/gate", json={"state": "open"})
    assert r_gate_after.status_code == 200
    assert r_gate_after.json()["data"]["gate_open"] is True


@pytest.mark.asyncio
async def test_emergency_stop_cannot_be_altered_via_business_actions(gateway_client: httpx.AsyncClient):
    """Verify that domain business actions cannot trigger or reset Emergency Stop."""
    # Attempt to reset E-Stop via business action on N4
    r_reset = await gateway_client.post(
        "/api/v1/n4/execute", json={"action": "reset_emergency_stop", "params": {}}
    )
    assert r_reset.status_code == 403
    assert r_reset.json()["error"]["code"] == "SAFETY_VIOLATION"
    assert "admin" in r_reset.json()["error"]["message"].lower()

    # Attempt to trigger E-Stop via business action on N4
    r_trigger = await gateway_client.post(
        "/api/v1/n4/execute", json={"action": "trigger_emergency_stop", "params": {}}
    )
    assert r_trigger.status_code == 403
    assert r_trigger.json()["error"]["code"] == "SAFETY_VIOLATION"


@pytest.mark.asyncio
async def test_fault_isolation_between_nodes(gateway_client: httpx.AsyncClient):
    """Verify that a fault injected into one node does NOT affect any other node."""
    # Inject connection failure only to node N1
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "DISCONNECTED",
            "node_id": "n1",
            "action": "*",
            "trigger_count": 5,
        },
    )

    # Node N1 should fail
    r_n1 = await gateway_client.get("/api/v1/n1/production/status")
    assert r_n1.status_code == 503
    assert r_n1.json()["ok"] is False
    assert r_n1.json()["error"]["code"] == "CONNECTION_ERROR"

    # Other nodes (N2, N3, N4) MUST continue to operate normally
    r_n2 = await gateway_client.get("/api/v1/n2/environment/status")
    assert r_n2.status_code == 200
    assert r_n2.json()["ok"] is True

    r_n3 = await gateway_client.get("/api/v1/n3/warehouse/status")
    assert r_n3.status_code == 200
    assert r_n3.json()["ok"] is True

    r_n4 = await gateway_client.get("/api/v1/n4/safety/status")
    assert r_n4.status_code == 200
    assert r_n4.json()["ok"] is True

    # Reset faults
    await gateway_client.post("/admin/faults/reset")


@pytest.mark.asyncio
async def test_node_n4_sequential_execution_shared_between_plugins(gateway_client: httpx.AsyncClient):
    """Verify that concurrent calls to N4 (e.g. from maintenance & safety) run sequentially."""
    # Inject 200ms latency on N4
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "LATENCY_MS",
            "node_id": "n4",
            "action": "*",
            "params": {"latency_ms": 200},
            "trigger_count": 2,
        },
    )

    t0 = time.time()
    # Call maintenance and safety simultaneously
    task1 = asyncio.create_task(gateway_client.get("/api/v1/n4/maintenance/vibration"))
    task2 = asyncio.create_task(gateway_client.get("/api/v1/n4/safety/check"))

    resp1, resp2 = await asyncio.gather(task1, task2)
    elapsed = time.time() - t0

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    # Sequential execution on N4 lock: 200ms + 200ms = >= 350ms
    assert elapsed >= 0.35, f"Expected sequential execution >= 350ms on N4, got {elapsed*1000:.1f}ms"

    await gateway_client.post("/admin/faults/reset")


@pytest.mark.asyncio
async def test_scenario_fixture_loading(gateway_client: httpx.AsyncClient, tmp_path: Path):
    """Verify that custom scenario fixture files can be loaded via admin endpoint."""
    custom_fixture = tmp_path / "scenario_danger.yaml"
    custom_fixture.write_text(
        """
nodes:
  n1:
    board: "esp32"
    name: "Production Control"
    state:
      fan: 0
      line_state: "holding"
      machine_status: "fault"
      temperature: 92.5
      humidity: 95.0
  n2:
    board: "pico_w"
    name: "Environmental Monitoring"
    state:
      temperature: 42.0
      humidity: 88.0
  n3:
    board: "arduino_uno"
    name: "Warehouse"
    state:
      rfid_tag: "BATCH-EXPIRED"
      rfid_valid: false
      distance: 3.5
      gate_open: false
      inventory: 0
  n4:
    board: "stm32"
    name: "Safety"
    state:
      vibration: 0.88
      machine_health: "critical"
      emergency_stop: true
""",
        encoding="utf-8",
    )

    # Load custom scenario fixture
    r_load = await gateway_client.post(
        "/admin/fixtures/load", json={"fixture_path": str(custom_fixture)}
    )
    assert r_load.status_code == 200
    assert r_load.json()["ok"] is True

    # Verify states from new fixture
    r_n1 = await gateway_client.get("/api/v1/n1/production/status")
    assert r_n1.json()["data"]["temperature"] == 92.5
    assert r_n1.json()["data"]["machine_status"] == "fault"

    r_n3 = await gateway_client.get("/api/v1/n3/warehouse/rfid")
    assert r_n3.json()["data"]["batch"] == "BATCH-EXPIRED"
    assert r_n3.json()["data"]["valid"] is False

    r_n4 = await gateway_client.get("/api/v1/n4/maintenance/vibration")
    assert r_n4.json()["data"]["vibration"] == 0.88

    # E-Stop is active in this scenario -> safety check disallowed
    r_check = await gateway_client.get("/api/v1/n4/safety/check")
    assert r_check.json()["data"]["allowed"] is False

    # Reset back to default fixture
    r_reset = await gateway_client.post("/admin/reset")
    assert r_reset.status_code == 200

    r_default = await gateway_client.get("/api/v1/n1/production/status")
    assert r_default.json()["data"]["temperature"] == 45.2
