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


class GenericActionRequest(BaseModel):
    action: str = Field(..., description="Action name to execute")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Action arguments")


class NodeStateUpdateRequest(BaseModel):
    state: Dict[str, Any] = Field(..., description="State fields to update")


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
        description="FastAPI Gateway interfacing ZeroClaw WASM plugins to industrial nodes",
        version="0.2.0",
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
    # ADMIN ENDPOINTS (Restricted to evaluator / grader)
    # -------------------------------------------------------------

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
