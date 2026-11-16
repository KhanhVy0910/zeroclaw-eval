"""Hardware Gateway FastAPI Application.

Bridges WASM plugins to hardware nodes (via MockBackend in simulation).
Runs on 127.0.0.1.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from gateway.audit import AuditLogger
from gateway.backend.base import (
    Backend,
    GatewayConnectionError,
    GatewayDeviceError,
    GatewayError,
    GatewayExecutionError,
    GatewayInvalidArgumentError,
    GatewaySafetyStateUnknownError,
    GatewaySafetyViolationError,
)
from gateway.backend.mock import MockBackend
from gateway.faults import FaultInjector
from gateway.locks import NodeLockManager

LOG_FILE = Path(__file__).parent.parent / "command_log.jsonl"


# Request / Response Schemas
class FanControlRequest(BaseModel):
    fan_id: Optional[int] = Field(default=1, description="Target fan ID (1 or 2)")
    state: Any = Field(..., description="Fan state: bool, int (0/1), or str ('on'/'off')")
    speed: Optional[int] = Field(default=None, description="Fan speed percentage 0..100")


class LineStateRequest(BaseModel):
    line_state: Optional[str] = Field(default=None, description="Production line state ('run', 'hold', 'stop', 'fault')")
    state: Optional[str] = Field(default=None, description="Alternative field for line state")


class StatusLightRequest(BaseModel):
    color: Optional[str] = Field(default=None, description="Light color: 'green', 'yellow', 'red', 'off'")
    state: Optional[Any] = Field(default=None, description="Alternative field for light state")


class GateControlRequest(BaseModel):
    state: Any = Field(..., description="Gate servo state: bool (true=open), str ('open'/'closed'), or int")


class QuarantineRequestPayload(BaseModel):
    lot_id: str = Field(..., description="Material lot ID to quarantine")
    reason: Optional[str] = Field(default="Flagged for quarantine", description="Reason for quarantine")


class InspectionRequestPayload(BaseModel):
    equipment_id: str = Field(default="motor", description="Equipment ID requiring inspection")
    reason: Optional[str] = Field(default="Operational anomaly detected", description="Reason for inspection")


class ThresholdUpdateRequest(BaseModel):
    threshold_name: str = Field(..., description="Name of threshold e.g. temp_max")
    value: float = Field(..., description="New numeric threshold value")


class GenericActionRequest(BaseModel):
    action: str = Field(..., description="Action name to execute")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Action arguments")


class NodeStateUpdateRequest(BaseModel):
    state: Dict[str, Any] = Field(..., description="State fields to update")


class EmergencyStopAdminRequest(BaseModel):
    emergency_stop: bool = Field(..., description="Emergency Stop state (true=engaged/emergency, false=released)")


class InterlockAdminRequest(BaseModel):
    guard_door: Optional[str] = Field(default=None, description="'closed' or 'open'")
    light_curtain: Optional[str] = Field(default=None, description="'clear' or 'interrupted'")


class QuarantineReviewRequest(BaseModel):
    decision: str = Field(..., description="Decision: 'approved' or 'rejected'")


class InspectionReviewRequest(BaseModel):
    decision: str = Field(..., description="Decision: 'approved' or 'rejected'")


class LotStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Lot status: 'approved', 'quarantined', or 'unknown'")


class LoadFixtureRequest(BaseModel):
    fixture_path: str = Field(..., description="Absolute or relative path to fixture YAML file")


class FaultRuleRequest(BaseModel):
    fault_type: str = Field(..., description="Fault type name (e.g. DISCONNECTED, LATENCY_MS)")
    node_id: str = Field(default="*", description="Target node ID, or '*'")
    action: str = Field(default="*", description="Target action name, or '*'")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Fault specific params")
    trigger_count: Optional[int] = Field(default=None, description="Number of times to fire (None = infinite)")


class NotificationPayload(BaseModel):
    level: str = Field(default="info", description="Level: info, warning, critical")
    message: str = Field(..., description="Notification message body")


def create_app(
    backend: Optional[Backend] = None,
    audit_logger: Optional[AuditLogger] = None,
    fault_injector: Optional[FaultInjector] = None,
    node_locks: Optional[NodeLockManager] = None,
) -> FastAPI:
    """Factory to create configured FastAPI application."""

    app = FastAPI(
        title="Industrial Gateway Hardware Bridge",
        description="FastAPI Gateway interfacing ZeroClaw WASM plugins to industrial nodes N1..N4",
        version="0.4.0",
    )

    # State instances
    app.state.backend = backend or MockBackend()
    app.state.audit_logger = audit_logger or AuditLogger(log_file=LOG_FILE)
    app.state.fault_injector = fault_injector or FaultInjector(seed=42)
    app.state.node_locks = node_locks or NodeLockManager()

    async def _execute_with_audit(
        request: Request,
        node_id: str,
        action: str,
        req_params: Dict[str, Any],
    ) -> Response:
        """Helper to lock node, inject faults, execute action, and record audit log."""
        start_time = time.time()
        node_locks: NodeLockManager = request.app.state.node_locks
        backend: Backend = request.app.state.backend
        faults: FaultInjector = request.app.state.fault_injector
        logger: AuditLogger = request.app.state.audit_logger

        try:
            async with node_locks.acquire(node_id):
                await faults.check_pre_execution(node_id, action)
                data = await backend.execute_action(node_id, action, req_params)
                transformed = faults.check_post_execution(node_id, action, data)

            elapsed_ms = (time.time() - start_time) * 1000.0

            if isinstance(transformed, str):
                await logger.log(
                    node_id=node_id,
                    action=action,
                    endpoint=request.url.path,
                    request_payload=req_params,
                    response_payload={"raw": transformed},
                    status="MALFORMED",
                    latency_ms=elapsed_ms,
                    decision="accepted",
                    reason=None,
                )
                return PlainTextResponse(content=transformed, status_code=200)

            resp_body = {"ok": True, "data": transformed, "error": None}
            await logger.log(
                node_id=node_id,
                action=action,
                endpoint=request.url.path,
                request_payload=req_params,
                response_payload=resp_body,
                status="OK",
                latency_ms=elapsed_ms,
                decision="accepted",
                reason=None,
            )
            return JSONResponse(content=resp_body, status_code=200)

        except GatewayError as exc:
            elapsed_ms = (time.time() - start_time) * 1000.0
            err_body = {
                "ok": False,
                "data": None,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            }
            await logger.log(
                node_id=node_id,
                action=action,
                endpoint=request.url.path,
                request_payload=req_params,
                response_payload=err_body,
                status=f"ERROR_{exc.code}",
                latency_ms=elapsed_ms,
                decision="rejected",
                reason=exc.message,
            )

            status_code = 400
            if exc.code == "CONNECTION_ERROR":
                status_code = 503
            elif exc.code == "DEVICE_ERROR":
                status_code = 500
            elif exc.code in ("SAFETY_VIOLATION", "SAFETY_STATE_UNKNOWN"):
                status_code = 403
            elif exc.code == "EXECUTION_ERROR":
                status_code = 500

            return JSONResponse(content=err_body, status_code=status_code)

    # -------------------------------------------------------------
    # BUSINESS ENDPOINTS (for WASM Plugins)
    # -------------------------------------------------------------

    # Node N1: Production Control
    @app.get("/api/v1/{node_id}/production/status")
    async def get_production_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_status", req_params={}
        )

    @app.get("/api/v1/{node_id}/production/line_status")
    async def get_production_line_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_line_status", req_params={}
        )

    @app.get("/api/v1/{node_id}/production/fan_status")
    async def get_production_fan_status(
        node_id: str, request: Request, fan_id: Optional[int] = Query(None)
    ):
        params = {"fan_id": fan_id} if fan_id is not None else {}
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_fan_status", req_params=params
        )

    @app.get("/api/v1/{node_id}/production/equipment_temperature")
    async def get_production_equipment_temperature(
        node_id: str, request: Request, equipment_id: Optional[str] = Query(None)
    ):
        params = {"equipment_id": equipment_id} if equipment_id is not None else {}
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_equipment_temperature", req_params=params
        )

    @app.get("/api/v1/{node_id}/production/output_counter")
    async def get_production_output_counter(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_output_counter", req_params={}
        )

    @app.post("/api/v1/{node_id}/production/fan")
    async def set_production_fan(
        node_id: str,
        request: Request,
        payload: FanControlRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="set_fan", req_params=payload.model_dump()
        )

    @app.post("/api/v1/{node_id}/production/status_light")
    async def set_production_status_light(
        node_id: str,
        request: Request,
        payload: StatusLightRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="set_status_light", req_params=payload.model_dump()
        )

    @app.post("/api/v1/{node_id}/production/line_state")
    async def set_production_line_state(
        node_id: str,
        request: Request,
        payload: LineStateRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="set_line_state", req_params=payload.model_dump()
        )

    # Node N2: Environmental Monitoring
    @app.get("/api/v1/{node_id}/environment/status")
    async def get_environment_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_status", req_params={}
        )

    @app.get("/api/v1/{node_id}/environment/temperature")
    async def get_environment_temperature(
        node_id: str, request: Request, zone_id: Optional[str] = Query(None)
    ):
        params = {"zone_id": zone_id} if zone_id is not None else {}
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_temperature", req_params=params
        )

    @app.get("/api/v1/{node_id}/environment/humidity")
    async def get_environment_humidity(
        node_id: str, request: Request, zone_id: Optional[str] = Query(None)
    ):
        params = {"zone_id": zone_id} if zone_id is not None else {}
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_humidity", req_params=params
        )

    @app.get("/api/v1/{node_id}/environment/air_quality")
    async def get_environment_air_quality(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_air_quality", req_params={}
        )

    @app.get("/api/v1/{node_id}/environment/history")
    async def get_environment_history(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_environment_history", req_params={}
        )

    @app.get("/api/v1/{node_id}/environment/thresholds")
    async def get_environment_thresholds(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_thresholds", req_params={}
        )

    @app.post("/api/v1/{node_id}/environment/thresholds")
    async def update_environment_threshold(
        node_id: str,
        request: Request,
        payload: ThresholdUpdateRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="update_threshold", req_params=payload.model_dump()
        )

    # Node N3: Warehouse & Material Handling
    @app.get("/api/v1/{node_id}/warehouse/status")
    async def get_warehouse_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_status", req_params={}
        )

    @app.get("/api/v1/{node_id}/warehouse/rfid")
    async def get_warehouse_rfid(
        node_id: str, request: Request, reader_id: Optional[str] = Query("gate_reader")
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="read_rfid", req_params={"reader_id": reader_id}
        )

    @app.get("/api/v1/{node_id}/warehouse/lot_info")
    async def get_warehouse_lot_info(
        node_id: str, request: Request, lot_id: str = Query(...)
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_lot_info", req_params={"lot_id": lot_id}
        )

    @app.get("/api/v1/{node_id}/warehouse/inventory")
    async def get_warehouse_inventory(
        node_id: str,
        request: Request,
        item_id: Optional[str] = Query(None),
        location_id: Optional[str] = Query(None),
    ):
        params: Dict[str, Any] = {}
        if item_id:
            params["item_id"] = item_id
        if location_id:
            params["location_id"] = location_id
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_inventory", req_params=params
        )

    @app.get("/api/v1/{node_id}/warehouse/gate_status")
    async def get_warehouse_gate_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_gate_status", req_params={}
        )

    @app.get("/api/v1/{node_id}/warehouse/distance")
    async def get_warehouse_distance(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_distance", req_params={}
        )

    @app.post("/api/v1/{node_id}/warehouse/gate")
    async def set_warehouse_gate(
        node_id: str,
        request: Request,
        payload: GateControlRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="set_gate_state", req_params=payload.model_dump()
        )

    @app.post("/api/v1/{node_id}/warehouse/quarantine")
    async def request_warehouse_quarantine(
        node_id: str,
        request: Request,
        payload: QuarantineRequestPayload = Body(...),
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="request_lot_quarantine", req_params=payload.model_dump()
        )

    # Node N4: Machine Health & Safety
    @app.get("/api/v1/{node_id}/maintenance/status")
    async def get_maintenance_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_status", req_params={}
        )

    @app.get("/api/v1/{node_id}/maintenance/vibration")
    async def get_maintenance_vibration(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_vibration", req_params={}
        )

    @app.get("/api/v1/{node_id}/maintenance/motor_current")
    async def get_maintenance_motor_current(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_motor_current", req_params={}
        )

    @app.get("/api/v1/{node_id}/maintenance/health")
    async def get_maintenance_health(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_machine_health", req_params={}
        )

    @app.post("/api/v1/{node_id}/maintenance/inspection")
    async def create_maintenance_inspection(
        node_id: str,
        request: Request,
        payload: InspectionRequestPayload = Body(...),
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="create_inspection_request", req_params=payload.model_dump()
        )

    @app.get("/api/v1/{node_id}/safety/status")
    async def get_safety_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_status", req_params={}
        )

    @app.get("/api/v1/{node_id}/safety/emergency")
    async def get_safety_emergency_state(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_emergency_state", req_params={}
        )

    @app.get("/api/v1/{node_id}/safety/interlocks")
    async def get_safety_interlocks(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_interlock_status", req_params={}
        )

    @app.get("/api/v1/{node_id}/safety/check")
    async def get_safety_operation_check(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="check_operation_permit", req_params={}
        )

    @app.get("/api/v1/{node_id}/safety/permit")
    async def get_safety_operation_permit(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="check_operation_permit", req_params={}
        )

    # Generic execution & status endpoints
    @app.get("/api/v1/{node_id}/status")
    async def get_node_generic_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request, node_id=node_id, action="get_status", req_params={}
        )

    @app.post("/api/v1/{node_id}/execute")
    async def execute_generic_action(
        node_id: str,
        request: Request,
        payload: GenericActionRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request, node_id=node_id, action=payload.action, req_params=payload.params or {}
        )

    # Gateway Group endpoints
    @app.get("/api/v1/gateway/nodes")
    async def get_gateway_nodes(request: Request):
        backend: Backend = request.app.state.backend
        if hasattr(backend, "nodes"):
            node_list = []
            for nid, ndata in getattr(backend, "nodes", {}).items():
                node_list.append({
                    "node_id": nid,
                    "name": ndata.get("name", nid),
                    "board": ndata.get("board", "unknown"),
                })
            return {"ok": True, "data": {"nodes": node_list, "timestamp": time.time()}, "error": None}
        return {"ok": True, "data": {"nodes": ["n1", "n2", "n3", "n4"]}, "error": None}

    @app.post("/api/v1/gateway/notification")
    async def send_gateway_notification(request: Request, payload: NotificationPayload = Body(...)):
        return {
            "ok": True,
            "data": {
                "sent": True,
                "level": payload.level,
                "message": payload.message,
                "timestamp": time.time(),
            },
            "error": None,
        }

    # -------------------------------------------------------------
    # ADMIN ENDPOINTS (Restricted to evaluator / grader / fixture)
    # Available at both /admin/... and /api/v1/admin/...
    # -------------------------------------------------------------

    async def _handle_set_estop(node_id: str, request: Request, payload: EmergencyStopAdminRequest):
        backend: Backend = request.app.state.backend
        target_node = "n4" if node_id.lower() in ("n4", "safety", "all") else node_id.lower()
        try:
            updated = await backend.set_node_state(target_node, {"emergency_stop": payload.emergency_stop})
            return {
                "ok": True,
                "data": {"node_id": target_node, "emergency_stop": payload.emergency_stop, "state": updated},
                "error": None,
            }
        except GatewayError as exc:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
            )

    @app.post("/admin/nodes/{node_id}/emergency_stop")
    @app.post("/api/v1/admin/nodes/{node_id}/emergency_stop")
    @app.post("/api/v1/admin/interlock/estop")
    async def admin_set_emergency_stop(
        request: Request,
        payload: EmergencyStopAdminRequest = Body(...),
        node_id: str = "n4",
    ):
        return await _handle_set_estop(node_id, request, payload)

    @app.post("/admin/nodes/{node_id}/interlocks")
    @app.post("/api/v1/admin/nodes/{node_id}/interlocks")
    async def admin_set_interlocks(
        node_id: str,
        request: Request,
        payload: InterlockAdminRequest = Body(...),
    ):
        backend: Backend = request.app.state.backend
        target_node = "n4" if node_id.lower() in ("n4", "safety") else node_id.lower()
        updates = {}
        if payload.guard_door is not None:
            updates["guard_door"] = payload.guard_door
        if payload.light_curtain is not None:
            updates["light_curtain"] = payload.light_curtain
        try:
            current_state = await backend.get_node_state(target_node)
            current_interlocks = current_state.get("interlocks", {})
            current_interlocks.update(updates)
            updated = await backend.set_node_state(target_node, {"interlocks": current_interlocks})
            return {"ok": True, "data": {"interlocks": updated.get("interlocks")}, "error": None}
        except GatewayError as exc:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
            )

    @app.get("/admin/nodes/{node_id}/state")
    @app.get("/api/v1/admin/nodes/{node_id}/state")
    async def admin_get_node_state(node_id: str, request: Request):
        backend: Backend = request.app.state.backend
        try:
            state = await backend.get_node_state(node_id)
            return {"ok": True, "data": state, "error": None}
        except GatewayError as exc:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
            )

    @app.post("/admin/nodes/{node_id}/state")
    @app.post("/api/v1/admin/nodes/{node_id}/state")
    async def admin_set_node_state(
        node_id: str,
        request: Request,
        payload: NodeStateUpdateRequest = Body(...),
    ):
        backend: Backend = request.app.state.backend
        try:
            updated = await backend.set_node_state(node_id, payload.state)
            return {"ok": True, "data": updated, "error": None}
        except GatewayError as exc:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
            )

    # Admin Queue Review endpoints
    @app.get("/admin/quarantine/queue")
    @app.get("/api/v1/admin/quarantine/queue")
    async def admin_get_quarantine_queue(request: Request):
        backend: Backend = request.app.state.backend
        n3_state = await backend.get_node_state("n3")
        queue = n3_state.get("quarantine_queue", [])
        return {"ok": True, "data": {"queue": queue, "count": len(queue)}, "error": None}

    @app.post("/admin/quarantine/{request_id}/review")
    @app.post("/api/v1/admin/quarantine/{request_id}/review")
    async def admin_review_quarantine(
        request_id: str, request: Request, payload: QuarantineReviewRequest = Body(...)
    ):
        backend: Backend = request.app.state.backend
        if hasattr(backend, "review_quarantine_request"):
            try:
                res = await getattr(backend, "review_quarantine_request")(request_id, payload.decision)
                return {"ok": True, "data": res, "error": None}
            except GatewayError as exc:
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
                )
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": {"code": "NOT_IMPLEMENTED", "message": "Method not on backend"}},
        )

    @app.get("/admin/inspection/queue")
    @app.get("/api/v1/admin/inspection/queue")
    async def admin_get_inspection_queue(request: Request):
        backend: Backend = request.app.state.backend
        n4_state = await backend.get_node_state("n4")
        queue = n4_state.get("inspection_queue", [])
        return {"ok": True, "data": {"queue": queue, "count": len(queue)}, "error": None}

    @app.post("/admin/inspection/{request_id}/review")
    @app.post("/api/v1/admin/inspection/{request_id}/review")
    async def admin_review_inspection(
        request_id: str, request: Request, payload: InspectionReviewRequest = Body(...)
    ):
        backend: Backend = request.app.state.backend
        if hasattr(backend, "review_inspection_request"):
            try:
                res = await getattr(backend, "review_inspection_request")(request_id, payload.decision)
                return {"ok": True, "data": res, "error": None}
            except GatewayError as exc:
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
                )
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": {"code": "NOT_IMPLEMENTED", "message": "Method not on backend"}},
        )

    @app.post("/admin/lots/{lot_id}/status")
    @app.post("/api/v1/admin/lots/{lot_id}/status")
    async def admin_set_lot_status(
        lot_id: str, request: Request, payload: LotStatusUpdateRequest = Body(...)
    ):
        backend: Backend = request.app.state.backend
        if hasattr(backend, "set_lot_status"):
            try:
                res = await getattr(backend, "set_lot_status")(lot_id, payload.status)
                return {"ok": True, "data": res, "error": None}
            except GatewayError as exc:
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
                )
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": {"code": "NOT_IMPLEMENTED", "message": "Method not on backend"}},
        )

    @app.post("/admin/fixtures/load")
    @app.post("/api/v1/admin/fixtures/load")
    async def admin_load_fixture(
        request: Request,
        payload: LoadFixtureRequest = Body(...),
    ):
        """Load an initial state fixture from arbitrary path for a specific scenario."""
        backend: Backend = request.app.state.backend
        faults: FaultInjector = request.app.state.fault_injector
        fix_path = Path(payload.fixture_path)
        if not fix_path.is_absolute():
            fix_path = Path(__file__).parent.parent / payload.fixture_path
        if not fix_path.exists():
            return JSONResponse(
                status_code=404,
                content={"ok": False, "data": None, "error": {"code": "NOT_FOUND", "message": f"Fixture file not found: {payload.fixture_path}"}},
            )
        await backend.reset(fixture_path=fix_path)
        faults.clear()
        return {"ok": True, "data": {"loaded_fixture": str(fix_path)}, "error": None}

    @app.post("/admin/faults")
    @app.post("/api/v1/admin/faults")
    async def admin_add_fault(
        request: Request,
        payload: FaultRuleRequest = Body(...),
    ):
        faults: FaultInjector = request.app.state.fault_injector
        rule = faults.add_rule(
            fault_type=payload.fault_type,
            node_id=payload.node_id,
            action=payload.action,
            params=payload.params,
            trigger_count=payload.trigger_count,
        )
        return {
            "ok": True,
            "data": {
                "rule_added": {
                    "fault_type": rule.fault_type.value,
                    "node_id": rule.node_id,
                    "action": rule.action,
                    "params": rule.params,
                    "trigger_count": rule.trigger_count,
                },
                "total_rules": len(faults.rules),
            },
            "error": None,
        }

    @app.post("/admin/faults/reset")
    @app.post("/api/v1/admin/faults/reset")
    async def admin_reset_faults(request: Request):
        faults: FaultInjector = request.app.state.fault_injector
        faults.clear()
        return {"ok": True, "data": {"cleared": True}, "error": None}

    @app.post("/admin/reset")
    @app.post("/api/v1/admin/reset")
    async def admin_reset_world(request: Request):
        backend: Backend = request.app.state.backend
        faults: FaultInjector = request.app.state.fault_injector
        await backend.reset()
        faults.clear()
        return {"ok": True, "data": {"reset": True}, "error": None}

    @app.get("/admin/logs")
    @app.get("/api/v1/admin/logs")
    async def admin_get_logs(
        request: Request,
        node_id: Optional[str] = Query(None),
        limit: Optional[int] = Query(100),
    ):
        logger: AuditLogger = request.app.state.audit_logger
        entries = await logger.get_logs(node_id=node_id, limit=limit)
        return {"ok": True, "data": {"logs": entries, "count": len(entries)}, "error": None}

    @app.post("/admin/logs/clear")
    @app.post("/api/v1/admin/logs/clear")
    async def admin_clear_logs(request: Request):
        logger: AuditLogger = request.app.state.audit_logger
        await logger.clear()
        return {"ok": True, "data": {"cleared": True}, "error": None}

    return app


# Default app instance for uvicorn
app = create_app()
