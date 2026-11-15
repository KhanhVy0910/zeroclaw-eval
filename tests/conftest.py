"""Pytest fixtures and configuration for zeroclaw-eval."""

import sys
from pathlib import Path
from typing import AsyncGenerator

# Ensure repo root is in python path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import httpx
import pytest
import pytest_asyncio

from gateway.app import create_app
from gateway.audit import AuditLogger
from gateway.backend.mock import MockBackend
from gateway.faults import FaultInjector
from gateway.locks import NodeLockManager
from mock_node.node import MockNode
from mock_node.state import NodeState


@pytest.fixture
def default_fixture_path() -> Path:
    """Path to the default ESP32 fixture file."""
    path = Path(__file__).parent.parent / "mock_node" / "fixtures" / "default_esp32.yaml"
    assert path.is_file(), f"Fixture not found at {path}"
    return path


@pytest.fixture
def esp32_node(default_fixture_path: Path) -> MockNode:
    """Instantiate a fresh MockNode with default ESP32 smartroom state."""
    return MockNode.from_fixture(default_fixture_path)


@pytest.fixture
def gateway_test_app(tmp_path: Path):
    """Create an isolated test FastAPI instance with dedicated tmp log file."""
    test_log = tmp_path / "test_command_log.jsonl"
    logger = AuditLogger(log_path=test_log)
    backend = MockBackend()
    faults = FaultInjector(seed=42)
    locks = NodeLockManager()
    app = create_app(
        backend=backend,
        audit_logger=logger,
        fault_injector=faults,
        node_locks=locks,
    )
    return app


@pytest_asyncio.fixture
async def gateway_client(gateway_test_app) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client for testing FastAPI gateway."""
    transport = httpx.ASGITransport(app=gateway_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        yield client
