"""Hardware Gateway FastAPI Application.

Bridges WASM plugins to hardware nodes (via MockBackend in simulation).
Runs on 127.0.0.1.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

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
    GatewaySafetyViolationError,
)
from gateway.backend.mock import MockBackend
from gateway.faults import FaultInjector
from gateway.locks import NodeLockManager

LOG_FILE = Path(__file__).parent.parent / "command_log.jsonl"


# Request / Response Schemas at module level
class FanControlRequest(BaseModel):
    state: Any = Field(..., description="Fan state: bool, int (0/1), or str ('on'/'off')")


class LineStateRequest(BaseModel):
    line_state: str = Field(..., description="Production line state ('running', 'holding', 'stopped')")


class GateControlRequest(BaseModel):
    state: Any = Field(..., description="Gate servo state: bool (true=open), str ('open'/'closed'), or int")


class GenericActionRequest(BaseModel):
    action: str = Field(..., description="Action name to execute")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Action arguments")


class NodeStateUpdateRequest(BaseModel):
    state: Dict[str, Any] = Field(..., description="State fields to update")


class EmergencyStopAdminRequest(BaseModel):
    emergency_stop: bool = Field(..., description="Emergency Stop state (true=engaged/emergency, false=released)")


class LoadFixtureRequest(BaseModel):
    fixture_path: str = Field(..., description="Absolute or relative path to fixture YAML file")


class FaultRuleRequest(BaseModel):
    fault_type: str = Field(..., description="Fault type name (e.g. DISCONNECTED, LATENCY_MS)")
    node_id: str = Field(default="*", description="Target node ID, or '*'")
    action: str = Field(default="*", description="Target action name, or '*'")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Fault specific params")
    trigger_count: Optional[int] = Field(default=None, description="Number of times to fire (None = infinite)")


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
        version="0.3.0",
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
            )

            status_code = 400
            if exc.code == "CONNECTION_ERROR":
                status_code = 503
            elif exc.code == "DEVICE_ERROR":
                status_code = 500
            elif exc.code == "SAFETY_VIOLATION":
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
            request=request,
            node_id=node_id,
            action="get_status",
            req_params={},
        )

    @app.post("/api/v1/{node_id}/production/fan")
    async def set_production_fan(
        node_id: str,
        request: Request,
        payload: FanControlRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="set_fan",
            req_params=payload.model_dump(),
        )

    @app.post("/api/v1/{node_id}/production/line_state")
    async def set_production_line_state(
        node_id: str,
        request: Request,
        payload: LineStateRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="set_line_state",
            req_params=payload.model_dump(),
        )

    # Node N2: Environmental Monitoring
    @app.get("/api/v1/{node_id}/environment/status")
    async def get_environment_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_status",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/environment/temperature")
    async def get_environment_temperature(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_temperature",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/environment/humidity")
    async def get_environment_humidity(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_humidity",
            req_params={},
        )

    # Node N3: Warehouse & Material Handling
    @app.get("/api/v1/{node_id}/warehouse/status")
    async def get_warehouse_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_status",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/warehouse/rfid")
    async def get_warehouse_rfid(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="read_rfid",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/warehouse/inventory")
    async def get_warehouse_inventory(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_inventory",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/warehouse/distance")
    async def get_warehouse_distance(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_distance",
            req_params={},
        )

    @app.post("/api/v1/{node_id}/warehouse/gate")
    async def set_warehouse_gate(
        node_id: str,
        request: Request,
        payload: GateControlRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="set_gate",
            req_params=payload.model_dump(),
        )

    # Node N4: Machine Health & Safety
    @app.get("/api/v1/{node_id}/maintenance/status")
    async def get_maintenance_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_status",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/maintenance/vibration")
    async def get_maintenance_vibration(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_vibration",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/maintenance/health")
    async def get_maintenance_health(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_machine_health",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/safety/status")
    async def get_safety_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_status",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/safety/emergency")
    async def get_safety_emergency_state(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_emergency_state",
            req_params={},
        )

    @app.get("/api/v1/{node_id}/safety/check")
    async def get_safety_operation_check(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="check_operation",
            req_params={},
        )

    # Generic execution & status endpoints
    @app.get("/api/v1/{node_id}/status")
    async def get_node_generic_status(node_id: str, request: Request):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action="get_status",
            req_params={},
        )

    @app.post("/api/v1/{node_id}/execute")
    async def execute_generic_action(
        node_id: str,
        request: Request,
        payload: GenericActionRequest = Body(...),
    ):
        return await _execute_with_audit(
            request=request,
            node_id=node_id,
            action=payload.action,
            req_params=payload.params or {},
        )

    # -------------------------------------------------------------
    # ADMIN ENDPOINTS (Restricted to evaluator / grader / fixture)
    # -------------------------------------------------------------

    @app.post("/admin/nodes/{node_id}/emergency_stop")
    async def admin_set_emergency_stop(
        node_id: str,
        request: Request,
        payload: EmergencyStopAdminRequest = Body(...),
    ):
        """Admin physical interlock control: ONLY place where Emergency Stop can be changed."""
        backend: Backend = request.app.state.backend
        target_node = "n4" if node_id.lower() in ("n4", "safety", "all") else node_id.lower()
        try:
            updated = await backend.set_node_state(target_node, {"emergency_stop": payload.emergency_stop})
            return {"ok": True, "data": {"node_id": target_node, "emergency_stop": payload.emergency_stop, "state": updated}, "error": None}
        except GatewayError as exc:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "data": None, "error": {"code": exc.code, "message": exc.message}},
            )

    @app.get("/admin/nodes/{node_id}/state")
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

    @app.post("/admin/fixtures/load")
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
    async def admin_reset_faults(request: Request):
        faults: FaultInjector = request.app.state.fault_injector
        faults.clear()
        return {"ok": True, "data": {"cleared": True}, "error": None}

    @app.post("/admin/reset")
    async def admin_reset_world(request: Request):
        backend: Backend = request.app.state.backend
        faults: FaultInjector = request.app.state.fault_injector
        await backend.reset()
        faults.clear()
        return {"ok": True, "data": {"reset": True}, "error": None}

    @app.get("/admin/logs")
    async def admin_get_logs(
        request: Request,
        node_id: Optional[str] = Query(None),
        limit: Optional[int] = Query(100),
    ):
        logger: AuditLogger = request.app.state.audit_logger
        entries = await logger.get_logs(node_id=node_id, limit=limit)
        return {"ok": True, "data": {"logs": entries, "count": len(entries)}, "error": None}

    @app.post("/admin/logs/clear")
    async def admin_clear_logs(request: Request):
        logger: AuditLogger = request.app.state.audit_logger
        await logger.clear()
        return {"ok": True, "data": {"cleared": True}, "error": None}

    return app


# Default app instance for uvicorn
app = create_app()
