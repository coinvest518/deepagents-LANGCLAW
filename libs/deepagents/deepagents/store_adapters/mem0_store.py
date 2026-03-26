"""Mem0 cloud memory adapter using the mem0ai v2 API.

Install: ``pip install mem0ai``
Required env: ``MEM0_API_KEY``
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StoreItem:
    key: str
    value: dict


class Mem0Store:
    """Adapter for Mem0 cloud memory using mem0ai v2 MemoryClient.

    v2 changes:
    - ``search()`` requires ``filters={"AND": [{"user_id": "..."}]}``
    - ``search()`` returns ``{"results": [...]}`` not a bare list
    - ``get_all()`` requires ``filters=`` instead of ``user_id=``
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> Mem0Store:
        try:
            from mem0 import MemoryClient
        except ImportError as exc:
            raise ImportError(
                "mem0ai is required for Mem0Store. Install with: pip install mem0ai"
            ) from exc

        api_key = os.environ.get("MEM0_API_KEY")
        if not api_key:
            raise ValueError("MEM0_API_KEY must be set")

        client = MemoryClient(api_key=api_key)
        return cls(client=client)

    def _user_filter(self, user_id: str) -> dict:
        """Build v2 filter dict for a user_id."""
        return {"AND": [{"user_id": user_id}]}

    def get(self, user_id: str, key: str) -> StoreItem | None:
        """Search for a specific memory by key text."""
        try:
            raw = self.client.search(
                key,
                filters=self._user_filter(user_id),
                limit=1,
            )
            hits = raw.get("results", raw) if isinstance(raw, dict) else (raw or [])
            if hits and isinstance(hits[0], dict):
                r = hits[0]
                return StoreItem(
                    key=r.get("id", ""),
                    value={"memory": r.get("memory", ""), "id": r.get("id", "")},
                )
        except Exception:
            logger.debug("Mem0Store.get failed", exc_info=True)
        return None

    def put(self, user_id: str, content: str, metadata: dict | None = None) -> None:
        """Add a memory for the given user."""
        try:
            self.client.add(
                [{"role": "user", "content": content}],
                user_id=user_id,
                metadata=metadata,
            )
        except Exception:
            logger.warning("Mem0Store.put failed", exc_info=True)

    def search(self, query: str, user_id: str = "default", limit: int = 10) -> list[StoreItem]:
        """Semantic search across memories for a user."""
        try:
            raw = self.client.search(
                query,
                filters=self._user_filter(user_id),
                limit=limit,
            )
            hits = raw.get("results", raw) if isinstance(raw, dict) else (raw or [])
            items = []
            for r in hits:
                if not isinstance(r, dict):
                    continue
                items.append(StoreItem(
                    key=r.get("id", ""),
                    value={
                        "memory": r.get("memory", ""),
                        "id": r.get("id", ""),
                        "score": r.get("score"),
                        "created_at": r.get("created_at", ""),
                    },
                ))
            return items
        except Exception:
            logger.warning("Mem0Store.search failed", exc_info=True)
            return []

    def get_all(self, user_id: str = "default", limit: int = 50) -> list[StoreItem]:
        """List all memories for a user."""
        try:
            raw = self.client.get_all(
                filters=self._user_filter(user_id),
                limit=limit,
            )
            hits = raw.get("results", raw) if isinstance(raw, dict) else (raw or [])
            items = []
            for r in hits:
                if not isinstance(r, dict):
                    continue
                items.append(StoreItem(
                    key=r.get("id", ""),
                    value={"memory": r.get("memory", ""), "id": r.get("id", "")},
                ))
            return items
        except Exception:
            logger.warning("Mem0Store.get_all failed", exc_info=True)
            return []

    # Async wrappers
    async def aget(self, user_id: str, key: str) -> StoreItem | None:
        return await asyncio.to_thread(self.get, user_id, key)

    async def aput(self, user_id: str, content: str, metadata: dict | None = None) -> None:
        await asyncio.to_thread(self.put, user_id, content, metadata)

    async def asearch(self, query: str, user_id: str = "default", limit: int = 10) -> list[StoreItem]:
        return await asyncio.to_thread(self.search, query, user_id, limit)