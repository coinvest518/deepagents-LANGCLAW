"""AstraDB store adapter using astrapy 2.x DataAPIClient.

Provides three purpose-built collections:
- ``agent_memory``    — semantic memory (facts, preferences, learned context)
- ``agent_documents`` — document storage (PDFs, notes, structured content)
- ``agent_data``      — structured key-value data (settings, records, configs)

Install: ``pip install astrapy``
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Collection names — fixed, not dynamically created
# ---------------------------------------------------------------------------
COLLECTION_MEMORY = "agent_memory"
COLLECTION_DOCUMENTS = "agent_documents"
COLLECTION_DATA = "agent_data"

ALL_COLLECTIONS = [COLLECTION_MEMORY, COLLECTION_DOCUMENTS, COLLECTION_DATA]


@dataclass
class StoreItem:
    key: str
    value: dict


class AstraStore:
    """Adapter for AstraDB using astrapy 2.x (DataAPIClient).

    Uses ``get_collection()`` to reference existing collections — does NOT
    call ``create_collection()`` at runtime (avoids index-limit errors).
    Collections must be pre-created once via setup or the admin UI.
    """

    def __init__(self, db: Any):
        self._db = db
        self._collections: dict[str, Any] = {}

    @classmethod
    def from_env(cls) -> AstraStore:
        """Build from ASTRA_DB_API_KEY, ASTRA_DB_ENDPOINT env vars."""
        try:
            from astrapy import DataAPIClient
        except ImportError as exc:
            raise ImportError(
                "astrapy>=2.0 is required for AstraStore. "
                "Install with: pip install astrapy"
            ) from exc

        api_key = os.environ.get("ASTRA_DB_API_KEY")
        endpoint = os.environ.get("ASTRA_DB_ENDPOINT")
        if not api_key or not endpoint:
            raise ValueError(
                "ASTRA_DB_API_KEY and ASTRA_DB_ENDPOINT must be set"
            )

        client = DataAPIClient()
        db = client.get_database(endpoint, token=api_key)
        store = cls(db=db)

        # Ensure our 3 collections exist (creates only if missing)
        store._ensure_collections()
        return store

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def _ensure_collections(self) -> None:
        """Create any missing collections. Safe to call repeatedly."""
        existing = set(self._db.list_collection_names())
        for name in ALL_COLLECTIONS:
            if name not in existing:
                try:
                    self._db.create_collection(name)
                    logger.info("AstraStore: created collection %s", name)
                except Exception:
                    logger.warning(
                        "AstraStore: could not create %s (may hit index limit)",
                        name,
                        exc_info=True,
                    )

    def _get_collection(self, name: str) -> Any:
        """Get a cached collection reference."""
        if name not in self._collections:
            self._collections[name] = self._db.get_collection(name)
        return self._collections[name]

    # ------------------------------------------------------------------
    # Memory operations (agent_memory)
    # ------------------------------------------------------------------

    def save_memory(
        self,
        content: str,
        user_id: str = "default",
        category: str = "general",
        metadata: dict | None = None,
    ) -> str:
        """Save a memory/fact to agent_memory. Returns the inserted _id."""
        coll = self._get_collection(COLLECTION_MEMORY)
        doc: dict[str, Any] = {
            "content": content,
            "user_id": user_id,
            "category": category,
            "type": "memory",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            doc["metadata"] = metadata
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def search_memory(
        self,
        user_id: str = "default",
        category: str | None = None,
        limit: int = 20,
    ) -> list[StoreItem]:
        """Search memories by user_id and optional category."""
        coll = self._get_collection(COLLECTION_MEMORY)
        filt: dict[str, Any] = {"user_id": user_id}
        if category:
            filt["category"] = category
        docs = list(coll.find(filt, limit=limit))
        return [
            StoreItem(key=str(d.get("_id", "")), value=d)
            for d in docs
        ]

    def find_memory(self, query_filter: dict, limit: int = 20) -> list[StoreItem]:
        """Generic filter search on agent_memory."""
        coll = self._get_collection(COLLECTION_MEMORY)
        docs = list(coll.find(query_filter, limit=limit))
        return [
            StoreItem(key=str(d.get("_id", "")), value=d)
            for d in docs
        ]

    # ------------------------------------------------------------------
    # Document operations (agent_documents)
    # ------------------------------------------------------------------

    def save_document(
        self,
        title: str,
        content: str,
        doc_type: str = "note",
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Save a document to agent_documents. Returns the inserted _id."""
        coll = self._get_collection(COLLECTION_DOCUMENTS)
        doc: dict[str, Any] = {
            "title": title,
            "content": content,
            "doc_type": doc_type,
            "tags": tags or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            doc["metadata"] = metadata
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def search_documents(
        self,
        doc_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[StoreItem]:
        """Search documents by type and/or tags."""
        coll = self._get_collection(COLLECTION_DOCUMENTS)
        filt: dict[str, Any] = {}
        if doc_type:
            filt["doc_type"] = doc_type
        if tags:
            filt["tags"] = {"$in": tags}
        docs = list(coll.find(filt, limit=limit))
        return [
            StoreItem(key=str(d.get("_id", "")), value=d)
            for d in docs
        ]

    def find_document(self, query_filter: dict, limit: int = 20) -> list[StoreItem]:
        """Generic filter search on agent_documents."""
        coll = self._get_collection(COLLECTION_DOCUMENTS)
        docs = list(coll.find(query_filter, limit=limit))
        return [
            StoreItem(key=str(d.get("_id", "")), value=d)
            for d in docs
        ]

    # ------------------------------------------------------------------
    # Data operations (agent_data) — structured key-value store
    # ------------------------------------------------------------------

    def put(self, key: str, value: dict, collection: str = COLLECTION_DATA) -> str:
        """Insert or replace a document by key in agent_data."""
        coll = self._get_collection(collection)
        # Use _id as the key for upsert behavior
        doc = {**value, "_id": key, "updated_at": datetime.now(timezone.utc).isoformat()}
        # Try find + replace, else insert
        existing = coll.find_one({"_id": key})
        if existing:
            coll.replace_one({"_id": key}, doc)
        else:
            coll.insert_one(doc)
        return key

    def get(self, key: str, collection: str = COLLECTION_DATA) -> StoreItem | None:
        """Get a document by key from agent_data."""
        coll = self._get_collection(collection)
        doc = coll.find_one({"_id": key})
        if doc is None:
            return None
        return StoreItem(key=key, value=doc)

    def search(self, query_filter: dict | None = None, collection: str = COLLECTION_DATA, limit: int = 20) -> list[StoreItem]:
        """Search/list documents in agent_data."""
        coll = self._get_collection(collection)
        docs = list(coll.find(query_filter or {}, limit=limit))
        return [
            StoreItem(key=str(d.get("_id", "")), value=d)
            for d in docs
        ]

    def delete(self, key: str, collection: str = COLLECTION_DATA) -> bool:
        """Delete a document by key."""
        coll = self._get_collection(collection)
        result = coll.delete_one({"_id": key})
        return result.deleted_count > 0

    # ------------------------------------------------------------------
    # Async wrappers
    # ------------------------------------------------------------------

    async def aget(self, key: str, collection: str = COLLECTION_DATA) -> StoreItem | None:
        return await asyncio.to_thread(self.get, key, collection)

    async def aput(self, key: str, value: dict, collection: str = COLLECTION_DATA) -> None:
        await asyncio.to_thread(self.put, key, value, collection)

    async def asearch(self, query_filter: dict | None = None, collection: str = COLLECTION_DATA, limit: int = 20) -> list[StoreItem]:
        return await asyncio.to_thread(self.search, query_filter, collection, limit)