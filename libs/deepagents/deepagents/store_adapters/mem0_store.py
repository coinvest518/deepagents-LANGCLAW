from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class StoreItem:
    key: str
    value: dict


class Mem0Store:
    """Adapter for mem0 cloud memory using the `mem0ai` package.

    Install: pip install mem0ai
    Required env: MEM0_API_KEY
    Optional env: MEM0_ENDPOINT (custom base URL)
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> Mem0Store:
        try:
            from mem0 import MemoryClient  # mem0ai exposes itself as `mem0`
        except ImportError as exc:
            raise ImportError(
                "mem0ai is required for Mem0Store. Install with: pip install mem0ai"
            ) from exc

        api_key = os.environ.get("MEM0_API_KEY")
        if not api_key:
            raise ValueError("MEM0_API_KEY must be set")

        client = MemoryClient(api_key=api_key)
        return cls(client=client)

    # Mem0 uses user_id for namespace isolation and memory_id for individual items.
    # We map (namespace, key) → user_id=namespace_str, and store key in metadata.

    def _user_id(self, namespace: tuple[str, ...]) -> str:
        return "/".join(namespace)

    def get(self, namespace: tuple[str, ...], key: str) -> StoreItem | None:
        try:
            results = self.client.search(key, user_id=self._user_id(namespace), limit=1)
            if results:
                r = results[0]
                return StoreItem(key=key, value={"memory": r.get("memory", ""), "id": r.get("id", "")})
        except Exception:
            return None
        return None

    def put(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        content = value.get("memory") or value.get("content") or str(value)
        try:
            self.client.add(
                [{"role": "user", "content": content}],
                user_id=self._user_id(namespace),
                metadata={"key": key},
            )
        except Exception:
            pass

    async def aget(self, namespace: tuple[str, ...], key: str) -> StoreItem | None:
        return await asyncio.to_thread(self.get, namespace, key)

    async def aput(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        return await asyncio.to_thread(self.put, namespace, key, value)

    def search(self, namespace: tuple[str, ...], query: str = "", *_, **__) -> list:
        try:
            results = self.client.get_all(user_id=self._user_id(namespace))
            items = []
            for r in (results or []):
                items.append(StoreItem(
                    key=r.get("id", ""),
                    value={"memory": r.get("memory", ""), "id": r.get("id", "")},
                ))
            return items
        except Exception:
            return []