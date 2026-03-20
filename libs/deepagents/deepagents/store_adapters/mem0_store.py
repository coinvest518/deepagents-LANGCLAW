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
    """Minimal adapter for mem0 store.

    This adapter expects an installed mem0 client package named `mem0_client`.
    Install as instructed by your mem0 provider. If the package isn't present
    the adapter raises an ImportError with installation instructions.
    """

    def __init__(self, client: Any):
        self.client = client

    @classmethod
    def from_env(cls) -> Mem0Store:
        try:
            import mem0_client as mem0  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ImportError("mem0_client is required for Mem0Store. Install it per mem0 provider docs.") from exc

        api_key = os.environ.get("MEM0_API_KEY")
        endpoint = os.environ.get("MEM0_ENDPOINT")
        if not api_key:
            raise ValueError("MEM0_API_KEY must be set")

        client = mem0.Client(api_key=api_key, base_url=endpoint) if endpoint else mem0.Client(api_key=api_key)
        return cls(client=client)

    def get(self, namespace: tuple[str, ...], key: str) -> StoreItem | None:
        try:
            doc = self.client.get(namespace="/".join(namespace), key=key)
        except Exception:
            return None
        if doc is None:
            return None
        return StoreItem(key=key, value=doc)

    def put(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        self.client.put(namespace="/".join(namespace), key=key, value=value)

    async def aget(self, namespace: tuple[str, ...], key: str) -> StoreItem | None:
        return await asyncio.to_thread(self.get, namespace, key)

    async def aput(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        return await asyncio.to_thread(self.put, namespace, key, value)

    def search(self, namespace: tuple[str, ...], *_, **__) -> list:
        results = self.client.list(namespace="/".join(namespace))
        items = []
        for r in results:
            items.append(StoreItem(key=r.get("key"), value=r.get("value")))
        return items
