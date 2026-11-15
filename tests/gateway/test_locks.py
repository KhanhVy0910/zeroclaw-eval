"""Tests for per-node sequential locking in Hardware Gateway."""

import asyncio
import time
import pytest
import httpx


@pytest.mark.asyncio
async def test_sequential_locking_same_node(gateway_client: httpx.AsyncClient):
    """Verify that concurrent requests to the SAME node execute sequentially."""
    # Inject latency to n1
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "LATENCY_MS",
            "node_id": "n1",
            "action": "*",
            "params": {"latency_ms": 200},
            "trigger_count": 2,
        },
    )

    t0 = time.time()
    # Launch two requests concurrently to node n1
    task1 = asyncio.create_task(gateway_client.get("/api/v1/n1/production/status"))
    task2 = asyncio.create_task(gateway_client.get("/api/v1/n1/production/status"))

    resp1, resp2 = await asyncio.gather(task1, task2)
    elapsed = time.time() - t0

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Because of sequential lock on n1:
    # 200ms + 200ms = 400ms minimum total time
    assert elapsed >= 0.35, f"Expected sequential delay >= 350ms, got {elapsed*1000:.1f}ms"


@pytest.mark.asyncio
async def test_parallel_execution_different_nodes(gateway_client: httpx.AsyncClient):
    """Verify that requests to DIFFERENT nodes (n1, n2) can execute concurrently."""
    # Inject 200ms latency to both n1 and n2
    await gateway_client.post(
        "/admin/faults",
        json={
            "fault_type": "LATENCY_MS",
            "node_id": "*",
            "action": "*",
            "params": {"latency_ms": 200},
            "trigger_count": 2,
        },
    )

    t0 = time.time()
    task_n1 = asyncio.create_task(gateway_client.get("/api/v1/n1/production/status"))
    task_n2 = asyncio.create_task(
        gateway_client.post(
            "/api/v1/n2/execute", json={"action": "get_status", "params": {}}
        )
    )

    resp1, resp2 = await asyncio.gather(task_n1, task_n2)
    elapsed = time.time() - t0

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Because n1 and n2 have independent locks:
    # They run concurrently in ~200ms (definitely well under 380ms)
    assert elapsed < 0.38, f"Expected concurrent execution < 380ms, got {elapsed*1000:.1f}ms"
