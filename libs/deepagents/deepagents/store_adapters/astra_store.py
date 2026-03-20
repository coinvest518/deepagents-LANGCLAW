from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class StoreItem:
    key: str
    value: dict


class AstraStore:
    """Minimal adapter that exposes the subset of BaseStore used by StoreBackend.

    NOTE: This adapter requires the `astrapy` package (Astra Data API client).
    Install with: `pip install astrapy`.
    """

    def __init__(self, client: Any, keyspace: str):
        self.client = client
        self.keyspace = keyspace

    @classmethod
    def from_env(cls) -> AstraStore:
        try:
            import astrapy
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ImportError("astrapy is required for AstraStore. Install with: pip install astrapy") from exc

        api_key = os.environ.get("ASTRA_DB_API_KEY")
        endpoint = os.environ.get("ASTRA_DB_ENDPOINT")
        keyspace = os.environ.get("ASTRA_DB_KEYSPACE")
        if not api_key or not endpoint or not keyspace:
            raise ValueError("ASTRA_DB_API_KEY, ASTRA_DB_ENDPOINT and ASTRA_DB_KEYSPACE must be set")

        # Create astrapy client. The exact client API may vary by version; the
        # runtime environment must install and configure astrapy accordingly.
        client = astrapy.Client(token=api_key, base_url=endpoint)
        return cls(client=client, keyspace=keyspace)

    def _ns_to_collection(self, namespace: tuple[str, ...]) -> str:
        # Join namespace into a simple collection name (best-effort).
        return "__".join(namespace)

    def get(self, namespace: tuple[str, ...], key: str) -> StoreItem | None:
        collection = self._ns_to_collection(namespace)
        # Use synchronous wrapper around client call
        try:
            # astrapy client: client.get_doc(collection, id) - adjust if needed
            res = self.client.get_doc(keyspace=self.keyspace, collection=collection, doc_id=key)
        except Exception:
            return None
        if res is None:
            return None
        return StoreItem(key=key, value=res)

    def put(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        collection = self._ns_to_collection(namespace)
        # astrapy client: create or replace document
        self.client.put_doc(keyspace=self.keyspace, collection=collection, doc_id=key, doc=value)

    async def aget(self, namespace: tuple[str, ...], key: str) -> StoreItem | None:
        return await asyncio.to_thread(self.get, namespace, key)

    async def aput(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        return await asyncio.to_thread(self.put, namespace, key, value)

    def search(self, namespace: tuple[str, ...], *_, **__) -> list:
        # Basic scan/list of docs in collection - avoid heavy queries in production.
        collection = self._ns_to_collection(namespace)
        docs = self.client.list_docs(keyspace=self.keyspace, collection=collection)
        items = []
        for d in docs:
            items.append(StoreItem(key=d.get("id") or d.get("_id"), value=d))
        return items
