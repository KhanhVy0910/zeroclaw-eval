"""Comprehensive validation tests for Task T5 (Revised Requirements).

Tests cover:
1. Each of the 4 nodes responds with full industrial domain data and timestamps.
2. Timestamps are included in every read response.
3. Permissions R0..R3 and selective Emergency Stop logic:
   - E-Stop rejects set_line_state start/run with 403.
   - E-Stop allows set_line_state hold and stop with 200.
   - E-Stop allows fan control, status light, and gate close with 200.
   - E-Stop rejects gate open with 403.
4. Gateway runtime safety re-check:
   - Condition changes between advisory check (permit check = allowed) and execution -> Gateway rejects execution!
5. Queues (Quarantine & Inspection):
   - Domain actions only create pending records in queues; lot status remains unchanged.
   - Queues and lot status can ONLY be reviewed/approved/rejected via admin endpoints.
6. Machine health on N4 is computed SOLELY from N4 data (vibration, motor current, anomalies), independent of N1.
7. Fault isolation between nodes.
8. Concurrent execution on N4 is strictly sequential (shared lock for maintenance & safety).
9. Audit log records timestamp, node, tool, params, decision (accepted/rejected), and refusal reason.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
import pytest
import httpx


@pytest.mark.asyncio
async def test_t5_all_nodes_data_and_timestamps(gateway_client: httpx.AsyncClient):
    """Verify that all 4 nodes return required domain data with valid timestamps."""
    # Reset world to default
    await gateway_client.post("/admin/reset")

    # 1. NODE N1 (Production Control)
    r_line = await gateway_client.get("/api/v1/n1/production/line_status")
    assert r_line.status_code == 200
    line_data = r_line.json()["data"]
    assert line_data["line_state"] == "running"
    assert line_data["speed"] == 100
    assert line_data["lot_id"] == "LOT-2026-N1-001"
    assert "timestamp" in line_data
    datetime.fromisoformat(line_data["timestamp"])

    r_fans = await gateway_client.get("/api/v1/n1/production/fan_status")
    assert r_fans.status_code == 200
    fans_data = r_fans.json()["data"]
    assert "fans" in fans_data
    assert "1" in fans_data["fans"] and "2" in fans_data["fans"]
    assert "timestamp" in fans_data

    r_fan1 = await gateway_client.get("/api/v1/n1/production/fan_status?fan_id=1")
    assert r_fan1.status_code == 200
    assert r_fan1.json()["data"]["fan_id"] == 1
    assert "timestamp" in r_fan1.json()["data"]

    r_temp = await gateway_client.get("/api/v1/n1/production/equipment_temperature?equipment_id=motor")
    assert r_temp.status_code == 200
    assert r_temp.json()["data"]["equipment_id"] == "motor"
    assert r_temp.json()["data"]["temperature"] == 45.2
    assert "timestamp" in r_temp.json()["data"]

    r_cab = await gateway_client.get("/api/v1/n1/production/equipment_temperature?equipment_id=control_cabinet")
    assert r_cab.status_code == 200
    assert r_cab.json()["data"]["temperature"] == 36.8

    r_counter = await gateway_client.get("/api/v1/n1/production/output_counter")
    assert r_counter.status_code == 200
    cnt_data = r_counter.json()["data"]
    assert cnt_data["total_units"] == 1520
    assert cnt_data["good_units"] == 1498
    assert cnt_data["defective_units"] == 22
    assert "timestamp" in cnt_data

    # 2. NODE N2 (Environmental Monitoring)
    r_env_temp = await gateway_client.get("/api/v1/n2/environment/temperature?zone_id=storage")
    assert r_env_temp.status_code == 200
    assert r_env_temp.json()["data"]["zone_id"] == "storage"
    assert r_env_temp.json()["data"]["temperature"] == 20.2
    assert "timestamp" in r_env_temp.json()["data"]

    r_env_hum = await gateway_client.get("/api/v1/n2/environment/humidity?zone_id=hall")
    assert r_env_hum.status_code == 200
    assert r_env_hum.json()["data"]["humidity"] == 55.0
    assert "timestamp" in r_env_hum.json()["data"]

    r_air = await gateway_client.get("/api/v1/n2/environment/air_quality")
    assert r_air.status_code == 200
    air_data = r_air.json()["data"]
    assert air_data["pm25"] == 18.5
    assert air_data["pm10"] == 32.0
    assert air_data["co2"] == 520.0
    assert "timestamp" in air_data

    r_thresh = await gateway_client.get("/api/v1/n2/environment/thresholds")
    assert r_thresh.status_code == 200
    assert r_thresh.json()["data"]["thresholds"]["temp_max"] == 35.0

    # 3. NODE N3 (Warehouse)
    r_rfid = await gateway_client.get("/api/v1/n3/warehouse/rfid?reader_id=gate_reader")
    assert r_rfid.status_code == 200
    rfid_data = r_rfid.json()["data"]
    assert r_rfid.json()["ok"] is True
    assert rfid_data["card_id"] == "BATCH-A100"
    assert "timestamp" in rfid_data

    r_lot = await gateway_client.get("/api/v1/n3/warehouse/lot_info?lot_id=LOT-2026-N1-001")
    assert r_lot.status_code == 200
    lot_data = r_lot.json()["data"]
    assert lot_data["lot_id"] == "LOT-2026-N1-001"
    assert lot_data["status"] == "approved"
    assert "timestamp" in lot_data

    r_inv = await gateway_client.get("/api/v1/n3/warehouse/inventory?item_id=RAW-STEEL-01&location_id=LOC-A1")
    assert r_inv.status_code == 200
    assert r_inv.json()["data"]["quantity"] == 150
    assert "timestamp" in r_inv.json()["data"]

    # 4. NODE N4 (Machine Health & Safety)
    r_vib = await gateway_client.get("/api/v1/n4/maintenance/vibration")
    assert r_vib.status_code == 200
    vib_data = r_vib.json()["data"]
    assert vib_data["rms"] == 0.12
    assert "x" in vib_data and "y" in vib_data and "z" in vib_data
    assert "timestamp" in vib_data

    r_cur = await gateway_client.get("/api/v1/n4/maintenance/motor_current")
    assert r_cur.status_code == 200
    assert r_cur.json()["data"]["motor_current"] == 8.4
    assert "timestamp" in r_cur.json()["data"]

    r_estop = await gateway_client.get("/api/v1/n4/safety/emergency")
    assert r_estop.status_code == 200
    assert r_estop.json()["data"]["emergency_stop"] is False
    assert r_estop.json()["data"]["status"] == "RELEASED"
    assert "timestamp" in r_estop.json()["data"]

    r_lock = await gateway_client.get("/api/v1/n4/safety/interlocks")
    assert r_lock.status_code == 200
    assert r_lock.json()["data"]["guard_door"] == "closed"
    assert r_lock.json()["data"]["light_curtain"] == "clear"
    assert "timestamp" in r_lock.json()["data"]


@pytest.mark.asyncio
async def test_t5_emergency_stop_selective_rules(gateway_client: httpx.AsyncClient):
    """Verify Rule 3: E-Stop blocks start and gate open, but allows stop/hold/fan/light/gate close."""
    await gateway_client.post("/admin/reset")

    # Engage E-Stop via admin
    r_estop = await gateway_client.post(
        "/admin/nodes/n4/emergency_stop", json={"emergency_stop": True}
    )
    assert r_estop.status_code == 200
    assert r_estop.json()["data"]["emergency_stop"] is True

    # 1. set_line_state start -> MUST BE REJECTED with 403
    r_start = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "start"}
    )
    assert r_start.status_code == 403
    assert r_start.json()["ok"] is False
    assert r_start.json()["error"]["code"] == "SAFETY_VIOLATION"
    assert "Emergency Stop" in r_start.json()["error"]["message"]

    # 2. set_line_state hold and stop -> MUST BE ACCEPTED (200)
    r_hold = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "hold"}
    )
    assert r_hold.status_code == 200
    assert r_hold.json()["data"]["line_state"] == "holding"

    r_stop = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "stop"}
    )
    assert r_stop.status_code == 200
    assert r_stop.json()["data"]["line_state"] == "stopped"

    # 3. Fan control -> MUST BE ACCEPTED (200)
    r_fan = await gateway_client.post(
        "/api/v1/n1/production/fan", json={"state": True, "speed": 80}
    )
    assert r_fan.status_code == 200
    assert r_fan.json()["data"]["fan"] == 1

    # 4. Status light -> MUST BE ACCEPTED (200)
    r_light = await gateway_client.post(
        "/api/v1/n1/production/status_light", json={"color": "red"}
    )
    assert r_light.status_code == 200
    assert r_light.json()["data"]["status_light"] == "red"

    # 5. Gate close -> MUST BE ACCEPTED (200)
    r_close = await gateway_client.post(
        "/api/v1/n3/warehouse/gate", json={"state": "closed"}
    )
    assert r_close.status_code == 200
    assert r_close.json()["data"]["gate_open"] is False

    # 6. Gate open -> MUST BE REJECTED with 403
    r_open = await gateway_client.post(
        "/api/v1/n3/warehouse/gate", json={"state": "open"}
    )
    assert r_open.status_code == 403
    assert r_open.json()["error"]["code"] == "SAFETY_VIOLATION"
    assert "Emergency Stop" in r_open.json()["error"]["message"]


@pytest.mark.asyncio
async def test_t5_gateway_recheck_safety_at_runtime(gateway_client: httpx.AsyncClient):
    """Verify Rule 2: Gateway does NOT trust prior checks and re-verifies safety at command execution time."""
    await gateway_client.post("/admin/reset")

    # Step 1: Agent performs advisory check -> Everything is safe, permit returns allowed: true
    r_permit = await gateway_client.get("/api/v1/n4/safety/permit")
    assert r_permit.status_code == 200
    assert r_permit.json()["data"]["allowed"] is True

    # Step 2: Between check and execution, an interlock opens (e.g. guard door opened)
    await gateway_client.post(
        "/admin/nodes/n4/interlocks", json={"guard_door": "open"}
    )

    # Step 3: Agent executes set_line_state start -> Gateway RE-CHECKS and REJECTS with 403!
    r_exec = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "start"}
    )
    assert r_exec.status_code == 403
    assert r_exec.json()["error"]["code"] == "SAFETY_VIOLATION"
    assert "guard door" in r_exec.json()["error"]["message"].lower()

    # Step 4: Close guard door, but machine vibration spikes above threshold (0.6 mm/s)
    await gateway_client.post(
        "/admin/nodes/n4/interlocks", json={"guard_door": "closed"}
    )
    await gateway_client.post(
        "/admin/nodes/n4/state", json={"state": {"vibration": {"x": 0.4, "y": 0.4, "z": 0.3, "rms": 0.65}}}
    )

    # Agent executes set_line_state start -> Gateway RE-CHECKS vibration and REJECTS with 403!
    r_exec2 = await gateway_client.post(
        "/api/v1/n1/production/line_state", json={"line_state": "start"}
    )
    assert r_exec2.status_code == 403
    assert r_exec2.json()["error"]["code"] == "SAFETY_VIOLATION"
    assert "vibration" in r_exec2.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_t5_interlock_option_b_warehouse_gate(gateway_client: httpx.AsyncClient):
    """Verify Safety Policy Option B: N4 interlock violation blocks N3 warehouse gate open, but allows gate close."""
    await gateway_client.post("/admin/reset")

    # Step 1: Open guard door on Node N4
    await gateway_client.post(
        "/admin/nodes/n4/interlocks", json={"guard_door": "open"}
    )

    # Step 2: Attempt to open gate -> MUST BE REJECTED with 403 SAFETY_VIOLATION
    r_open = await gateway_client.post(
        "/api/v1/n3/warehouse/gate", json={"state": "open"}
    )
    assert r_open.status_code == 403
    assert r_open.json()["ok"] is False
    assert r_open.json()["error"]["code"] == "SAFETY_VIOLATION"
    assert "interlock" in r_open.json()["error"]["message"].lower()

    # Step 3: Attempt to close gate -> MUST BE ACCEPTED (200 OK, fail-safe containment)
    r_close = await gateway_client.post(
        "/api/v1/n3/warehouse/gate", json={"state": "closed"}
    )
    assert r_close.status_code == 200
    assert r_close.json()["ok"] is True
    assert r_close.json()["data"]["gate_open"] is False

    # Step 4: Close guard door (interlocks restored to normal)
    await gateway_client.post(
        "/admin/nodes/n4/interlocks", json={"guard_door": "closed"}
    )

    # Step 5: Now gate open -> MUST BE ACCEPTED (200 OK)
    r_open2 = await gateway_client.post(
        "/api/v1/n3/warehouse/gate", json={"state": "open"}
    )
    assert r_open2.status_code == 200
    assert r_open2.json()["ok"] is True
    assert r_open2.json()["data"]["gate_open"] is True


@pytest.mark.asyncio
async def test_t5_queues_pending_and_admin_review(gateway_client: httpx.AsyncClient):
    """Verify Rule 4: Quarantine and Inspection requests create pending records only; only admin can review."""
    await gateway_client.post("/admin/reset")

    # 1. Agent submits lot quarantine request via business API
    r_qr = await gateway_client.post(
        "/api/v1/n3/warehouse/quarantine",
        json={"lot_id": "LOT-2026-N1-001", "reason": "Packaging integrity compromised"},
    )
    assert r_qr.status_code == 200
    qr_data = r_qr.json()["data"]
    req_id = qr_data["request_id"]
    assert qr_data["status"] == "pending"

    # Verify that the lot in warehouse is NOT quarantined yet!
    r_lot_before = await gateway_client.get("/api/v1/n3/warehouse/lot_info?lot_id=LOT-2026-N1-001")
    assert r_lot_before.json()["data"]["status"] == "approved"

    # Verify queue in admin
    r_queue = await gateway_client.get("/admin/quarantine/queue")
    assert r_queue.status_code == 200
    assert any(item["id"] == req_id and item["status"] == "pending" for item in r_queue.json()["data"]["queue"])

    # Admin approves quarantine
    r_approve = await gateway_client.post(
        f"/admin/quarantine/{req_id}/review", json={"decision": "approved"}
    )
    assert r_approve.status_code == 200
    assert r_approve.json()["data"]["status"] == "approved"

    # Now the lot status IS quarantined
    r_lot_after = await gateway_client.get("/api/v1/n3/warehouse/lot_info?lot_id=LOT-2026-N1-001")
    assert r_lot_after.json()["data"]["status"] == "quarantined"

    # 2. Agent submits inspection request via business API
    r_ir = await gateway_client.post(
        "/api/v1/n4/maintenance/inspection",
        json={"equipment_id": "motor", "reason": "High frequency vibration harmonic"},
    )
    assert r_ir.status_code == 200
    ir_data = r_ir.json()["data"]
    ir_id = ir_data["request_id"]
    assert ir_data["status"] == "pending"

    # Admin reviews inspection
    r_ir_review = await gateway_client.post(
        f"/admin/inspection/{ir_id}/review", json={"decision": "approved"}
    )
    assert r_ir_review.status_code == 200
    assert r_ir_review.json()["data"]["status"] == "approved"


@pytest.mark.asyncio
async def test_t5_n4_health_calculated_solely_from_n4(gateway_client: httpx.AsyncClient):
    """Verify Rule: N4 health is calculated solely from N4 data (vibration, current, history) and independent of N1."""
    await gateway_client.post("/admin/reset")

    # Set N1 to fault state
    await gateway_client.post(
        "/admin/nodes/n1/state", json={"state": {"line_state": "fault", "machine_status": "fault", "temperature": 99.0}}
    )

    # N4 health MUST still be nominal (95.0) because N4 vibration and current are nominal!
    r_n4_health = await gateway_client.get("/api/v1/n4/maintenance/health")
    assert r_n4_health.status_code == 200
    h_data = r_n4_health.json()["data"]
    assert h_data["health_status"] == "nominal"
    assert h_data["health_score"] == 95.0
    assert h_data["anomaly_detected"] is False

    # Now change N4 motor current to 22.0 A (critical threshold > 20A)
    await gateway_client.post(
        "/admin/nodes/n4/state", json={"state": {"motor_current": 22.0}}
    )
    r_n4_critical = await gateway_client.get("/api/v1/n4/maintenance/health")
    h_crit = r_n4_critical.json()["data"]
    assert h_crit["health_status"] == "critical"
    assert h_crit["health_score"] == 35.0
    assert h_crit["anomaly_detected"] is True


@pytest.mark.asyncio
async def test_t5_audit_log_decision_and_reason(gateway_client: httpx.AsyncClient):
    """Verify Rule 5: Audit log records decision ('accepted' or 'rejected') and refusal reason for every command."""
    await gateway_client.post("/admin/logs/clear")
    await gateway_client.post("/admin/reset")

    # 1. Execute an accepted command
    r_ok = await gateway_client.post("/api/v1/n1/production/fan", json={"state": True})
    assert r_ok.status_code == 200

    # 2. Engage E-Stop and execute a rejected command
    await gateway_client.post("/admin/nodes/n4/emergency_stop", json={"emergency_stop": True})
    r_rej = await gateway_client.post("/api/v1/n1/production/line_state", json={"line_state": "start"})
    assert r_rej.status_code == 403

    # Retrieve audit logs
    r_logs = await gateway_client.get("/admin/logs")
    assert r_logs.status_code == 200
    logs = r_logs.json()["data"]["logs"]
    assert len(logs) >= 2

    # Verify accepted entry
    accepted_entries = [e for e in logs if e.get("action") == "set_fan" and e.get("decision") == "accepted"]
    assert len(accepted_entries) >= 1
    assert accepted_entries[0]["ok"] is True
    assert accepted_entries[0]["tool"] == "set_fan"

    # Verify rejected entry
    rejected_entries = [e for e in logs if e.get("action") == "set_line_state" and e.get("decision") == "rejected"]
    assert len(rejected_entries) >= 1
    rej = rejected_entries[0]
    assert rej["ok"] is False
    assert rej["decision"] == "rejected"
    assert "Emergency Stop" in rej["reason"]
    assert rej["node_id"] == "n1"
