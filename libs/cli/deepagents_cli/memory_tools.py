"""LangChain tools that give the agent direct access to Mem0 and AstraDB.

These tools let the agent search, save, and retrieve memories and structured
data without relying on shell scripts or external commands.

Tools:
- ``search_memory``   — semantic search across Mem0 (natural language queries)
- ``save_memory``     — store a new memory/fact in Mem0 (+ AstraDB backup)
- ``search_database`` — list/browse documents stored in AstraDB
- ``save_to_database``— store structured data in AstraDB (+ Mem0 backup)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton stores — initialised on first tool call, not at import time.
# This avoids import errors when mem0ai / astrapy aren't installed.
# ---------------------------------------------------------------------------
_mem0_store: Any = None
_astra_store: Any = None
_stores_initialised = False


def _ensure_stores() -> None:
    """Lazily initialise Mem0Store and AstraStore from env vars."""
    global _mem0_store, _astra_store, _stores_initialised
    if _stores_initialised:
        return
    _stores_initialised = True

    if os.environ.get("MEM0_API_KEY"):
        try:
            from deepagents.store_adapters.mem0_store import Mem0Store
            _mem0_store = Mem0Store.from_env()
            logger.info("memory_tools: Mem0Store ready")
        except Exception:
            logger.warning("memory_tools: Mem0Store init failed", exc_info=True)

    if os.environ.get("ASTRA_DB_API_KEY"):
        try:
            from deepagents.store_adapters.astra_store import AstraStore
            _astra_store = AstraStore.from_env()
            logger.info("memory_tools: AstraStore ready")
        except Exception:
            logger.warning("memory_tools: AstraStore init failed", exc_info=True)


# Default namespace used for agent memories
_DEFAULT_NS = ("agent", "memories")
_DEFAULT_DB_NS = ("agent", "data")


# ---------------------------------------------------------------------------
# Memory tools (Mem0-backed semantic memory)
# ---------------------------------------------------------------------------

@tool
def search_memory(query: str, user_id: str = "default") -> dict[str, Any]:
    """Search the agent's long-term memory using natural language.

    Use this when the user asks you to recall, remember, or look up something
    from past conversations or stored knowledge. Mem0 performs semantic search
    so the query can be conversational (e.g. "what did we discuss about pricing").

    Args:
        query: Natural language search query.
        user_id: User namespace for memory isolation (default: "default").

    Returns:
        Dict with "memories" list and "count", or "error" on failure.
    """
    _ensure_stores()
    if _mem0_store is None:
        return {"error": "Mem0 is not configured. Set MEM0_API_KEY.", "memories": []}

    namespace = ("user", user_id)
    try:
        # Use the mem0 client's native search for semantic matching
        results = _mem0_store.client.search(query, user_id=user_id, limit=10)
        memories = []
        for r in results or []:
            memories.append({
                "id": r.get("id", ""),
                "memory": r.get("memory", ""),
                "score": r.get("score", None),
            })
        return {"memories": memories, "count": len(memories), "query": query}
    except Exception as exc:
        logger.warning("search_memory failed", exc_info=True)
        return {"error": str(exc), "memories": []}


@tool
def save_memory(content: str, user_id: str = "default") -> dict[str, Any]:
    """Save a fact, preference, or piece of information to long-term memory.

    Use this when the user says "remember this", "save this for later",
    "note that I prefer X", or when you learn an important fact worth
    persisting across conversations.

    The content is stored in Mem0 (semantic search) and backed up to AstraDB
    if configured.

    Args:
        content: The information to remember (plain text).
        user_id: User namespace for memory isolation (default: "default").

    Returns:
        Dict with "saved": True on success, or "error" on failure.
    """
    _ensure_stores()
    if _mem0_store is None and _astra_store is None:
        return {"error": "No memory backend configured. Set MEM0_API_KEY or ASTRA_DB_API_KEY."}

    errors: list[str] = []

    # Write to Mem0 (primary — semantic)
    if _mem0_store is not None:
        try:
            _mem0_store.client.add(
                [{"role": "user", "content": content}],
                user_id=user_id,
            )
        except Exception as exc:
            errors.append(f"Mem0: {exc}")
            logger.warning("save_memory Mem0 failed", exc_info=True)

    # Write-through to AstraDB (backup)
    if _astra_store is not None:
        try:
            import hashlib
            key = hashlib.md5(content.encode()).hexdigest()[:16]
            _astra_store.put(
                _DEFAULT_DB_NS,
                key,
                {"content": content, "user_id": user_id, "type": "memory"},
            )
        except Exception as exc:
            errors.append(f"AstraDB: {exc}")
            logger.warning("save_memory AstraDB failed", exc_info=True)

    if errors and _mem0_store is None:
        return {"error": "; ".join(errors), "saved": False}

    return {"saved": True, "content_preview": content[:100]}


# ---------------------------------------------------------------------------
# Database tools (AstraDB-backed structured storage)
# ---------------------------------------------------------------------------

@tool
def search_database(
    collection: str = "agent__data",
    query: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Browse or search documents stored in the AstraDB database.

    Use this when the user asks to look up stored data, check the database,
    list saved records, or retrieve structured information that was
    previously saved with save_to_database.

    Args:
        collection: AstraDB collection name (default: "agent__data").
        query: Optional filter query (currently lists all docs in collection).
        limit: Maximum number of results to return (default 20).

    Returns:
        Dict with "documents" list and "count", or "error" on failure.
    """
    _ensure_stores()
    if _astra_store is None:
        return {"error": "AstraDB is not configured. Set ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT + ASTRA_DB_KEYSPACE.", "documents": []}

    try:
        namespace = tuple(collection.split("__")) if "__" in collection else ("agent", collection)
        items = _astra_store.search(namespace)
        docs = []
        for item in (items or [])[:limit]:
            docs.append({"key": item.key, "value": item.value})
        return {"documents": docs, "count": len(docs), "collection": collection}
    except Exception as exc:
        logger.warning("search_database failed", exc_info=True)
        return {"error": str(exc), "documents": []}


@tool
def save_to_database(
    key: str,
    data: dict[str, Any],
    collection: str = "agent__data",
) -> dict[str, Any]:
    """Store structured data in the AstraDB database.

    Use this when the user wants to persist structured information — JSON data,
    records, analysis results, extracted data from documents, etc. This is for
    structured/tabular data; use save_memory for natural-language facts.

    The data is also backed up to Mem0 if configured.

    Args:
        key: Unique identifier for this document.
        data: Dictionary of data to store.
        collection: AstraDB collection name (default: "agent__data").

    Returns:
        Dict with "saved": True on success, or "error" on failure.
    """
    _ensure_stores()
    if _astra_store is None:
        return {"error": "AstraDB is not configured. Set ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT + ASTRA_DB_KEYSPACE."}

    namespace = tuple(collection.split("__")) if "__" in collection else ("agent", collection)
    errors: list[str] = []

    try:
        _astra_store.put(namespace, key, data)
    except Exception as exc:
        errors.append(f"AstraDB: {exc}")
        logger.warning("save_to_database AstraDB failed", exc_info=True)

    # Write-through to Mem0 as a summary
    if _mem0_store is not None:
        try:
            summary = f"Saved to database [{collection}] key={key}: {str(data)[:500]}"
            _mem0_store.client.add(
                [{"role": "user", "content": summary}],
                user_id="database_records",
            )
        except Exception:
            logger.debug("save_to_database Mem0 backup failed", exc_info=True)

    if errors:
        return {"error": "; ".join(errors), "saved": False}
    return {"saved": True, "key": key, "collection": collection}


# ---------------------------------------------------------------------------
# Convenience list for importing into the agent tool list
# ---------------------------------------------------------------------------
MEMORY_TOOLS = [search_memory, save_memory, search_database, save_to_database]