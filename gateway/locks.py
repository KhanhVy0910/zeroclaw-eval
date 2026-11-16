"""Per-node sequential lock manager for Hardware Gateway."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict


class NodeLockManager:
    """Manages sequential execution locks per hardware node.

    Guarantees that actions destined for the same node (e.g. 'n1') are executed
    strictly sequentially, preventing hardware race conditions and corrupted
    states, while allowing distinct nodes to run in parallel.
    """

    def __init__(self) -> None:
        self._locks: Dict[str, asyncio.Lock] = {}
        self._master_lock = asyncio.Lock()

    def get_lock(self, node_id: str) -> asyncio.Lock:
        """Get or create the asyncio.Lock bound to a specific node_id."""
        normalized = node_id.strip().lower()
        # N4 sequential lock is shared by both maintenance and safety subsystems
        if normalized in ("maintenance", "safety"):
            normalized = "n4"
        if normalized not in self._locks:
            self._locks[normalized] = asyncio.Lock()
        return self._locks[normalized]

    @asynccontextmanager
    async def acquire(self, node_id: str) -> AsyncGenerator[None, None]:
        """Context manager helper to acquire the per-node lock."""
        lock = self.get_lock(node_id)
        async with lock:
            yield
