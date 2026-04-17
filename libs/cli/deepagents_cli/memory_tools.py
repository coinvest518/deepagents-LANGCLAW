"""LangChain tools for agent memory, database, and document storage.

Three separated concerns:
- **Memory** (Mem0 + AstraDB ``agent_memory``): Semantic long-term memory — facts,
  preferences, context the agent should recall across conversations.
- **Database** (AstraDB ``agent_data``): Structured key-value data — records, configs,
  extracted data, analysis results.
- **Documents** (AstraDB ``agent_documents``): Document storage — PDFs, notes,
  web content, any text content with titles and tags.

Tools:
- ``search_memory``     — search long-term memory (Mem0 semantic + AstraDB filter)
- ``save_memory``       — store a new memory/fact with category metadata
- ``update_memory``     — update/correct an existing memory by ID
- ``delete_memory``     — delete/forget a memory by ID
- ``list_memories``     — list all stored memories with metadata
- ``search_database``   — search structured data records
- ``save_to_database``  — store structured key-value data
- ``search_documents``  — search stored documents by type/tags
- ``save_document``     — store a document (notes, PDFs, web content)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton stores — initialised on first tool call, not at import time.
# ---------------------------------------------------------------------------
_mem0_store: Any = None
_astra_store: Any = None
_stores_initialised = False


def _ensure_stores() -> None:
    """Lazily initialise Mem0 and AstraDB stores from env vars."""
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

    if os.environ.get("ASTRA_DB_API_KEY") and os.environ.get("ASTRA_DB_ENDPOINT"):
        try:
            from deepagents.store_adapters.astra_store import AstraStore
            _astra_store = AstraStore.from_env()
            logger.info("memory_tools: AstraStore ready")
        except Exception:
            logger.warning("memory_tools: AstraStore init failed", exc_info=True)


# ---------------------------------------------------------------------------
# 1. MEMORY tools — semantic long-term memory
# ---------------------------------------------------------------------------

@tool
def search_memory(query: str, user_id: str = "default", category: str = "") -> dict[str, Any]:
    """Search the agent's long-term memory for facts, preferences, or past context.

    Use when the user asks to recall, remember, or look up something from
    past conversations. Mem0 does semantic search; AstraDB does filter search.

    Args:
        query: Natural language search query.
        user_id: User namespace for isolation (default: "default").
        category: Optional category filter (e.g. "preference", "fact", "context").

    Returns:
        Dict with "memories" list and "count", or "error" on failure.
    """
    _ensure_stores()
    if _mem0_store is None and _astra_store is None:
        return {"error": "No memory backend configured. Set MEM0_API_KEY or ASTRA_DB_API_KEY.", "memories": []}

    memories: list[dict] = []
    errors: list[str] = []

    # Mem0: semantic search (primary)
    if _mem0_store is not None:
        try:
            # Mem0 v2 API requires filters dict; returns {"results": [...]}
            raw = _mem0_store.client.search(
                query,
                filters={"AND": [{"user_id": user_id}]},
                limit=10,
            )
            # v2 wraps in {"results": [...]}, v1 returns list directly
            hits = raw.get("results", raw) if isinstance(raw, dict) else (raw or [])
            for r in hits:
                if not isinstance(r, dict):
                    continue
                meta = r.get("metadata", {}) or {}
                memories.append({
                    "id": r.get("id", ""),
                    "memory": r.get("memory", ""),
                    "score": r.get("score", None),
                    "category": meta.get("category", ""),
                    "created_at": r.get("created_at", ""),
                    "source": "mem0",
                })
        except Exception as exc:
            errors.append(f"Mem0: {exc}")
            logger.warning("search_memory Mem0 failed", exc_info=True)

    # AstraDB: filter search (supplement)
    if _astra_store is not None:
        try:
            items = _astra_store.search_memory(
                user_id=user_id,
                category=category or None,
                limit=10,
            )
            for item in items:
                memories.append({
                    "id": item.key,
                    "memory": item.value.get("content", ""),
                    "category": item.value.get("category", ""),
                    "created_at": item.value.get("created_at", ""),
                    "source": "astradb",
                })
        except Exception as exc:
            errors.append(f"AstraDB: {exc}")
            logger.warning("search_memory AstraDB failed", exc_info=True)

    result: dict[str, Any] = {"memories": memories, "count": len(memories), "query": query}
    if errors:
        result["warnings"] = errors
    return result


@tool
def save_memory(content: str, user_id: str = "default", category: str = "general") -> dict[str, Any]:
    """Save a fact, preference, or piece of information to long-term memory.

    Use when the user says "remember this", "save this for later",
    "note that I prefer X", or when you learn an important fact worth
    persisting across conversations.

    Args:
        content: The information to remember (plain text).
        user_id: User namespace for isolation (default: "default").
        category: Category tag — "preference", "fact", "context", "general".

    Returns:
        Dict with "saved": True on success, or "error" on failure.
    """
    _ensure_stores()
    if _mem0_store is None and _astra_store is None:
        return {"error": "No memory backend configured. Set MEM0_API_KEY or ASTRA_DB_API_KEY."}

    errors: list[str] = []
    saved_to: list[str] = []

    # Write to Mem0 (semantic)
    if _mem0_store is not None:
        try:
            _mem0_store.client.add(
                [{"role": "user", "content": content}],
                user_id=user_id,
                agent_id="deepagent",
                metadata={"category": category},
            )
            saved_to.append("mem0")
        except Exception as exc:
            errors.append(f"Mem0: {exc}")
            logger.warning("save_memory Mem0 failed", exc_info=True)

    # Write to AstraDB (structured)
    if _astra_store is not None:
        try:
            doc_id = _astra_store.save_memory(
                content=content,
                user_id=user_id,
                category=category,
            )
            saved_to.append("astradb")
        except Exception as exc:
            errors.append(f"AstraDB: {exc}")
            logger.warning("save_memory AstraDB failed", exc_info=True)

    if not saved_to:
        return {"error": "; ".join(errors), "saved": False}

    return {"saved": True, "saved_to": saved_to, "content_preview": content[:100]}


@tool
def update_memory(memory_id: str, text: str, category: str = "") -> dict[str, Any]:
    """Update an existing memory by its ID.

    Use when a fact has changed, the user corrects information, or a memory
    needs to be refined. First use `search_memory` to find the memory ID,
    then call this tool to update it.

    Args:
        memory_id: The unique memory identifier (from search_memory results).
        text: The new/corrected content for this memory.
        category: Updated category (optional). Leave empty to keep current.

    Returns:
        Dict with "updated": True on success, or "error" on failure.
    """
    _ensure_stores()
    if _mem0_store is None:
        return {"error": "Mem0 not configured. Set MEM0_API_KEY.", "updated": False}

    try:
        meta = {"category": category} if category else None
        ok = _mem0_store.update(memory_id, text, metadata=meta)
        if ok:
            return {"updated": True, "memory_id": memory_id, "text_preview": text[:100]}
        return {"error": "Update failed — check the memory ID is correct.", "updated": False}
    except Exception as exc:
        logger.warning("update_memory failed", exc_info=True)
        return {"error": str(exc), "updated": False}


@tool
def delete_memory(memory_id: str) -> dict[str, Any]:
    """Delete a memory by its ID.

    Use when the user says "forget this", "delete that memory", or wants
    to remove incorrect information. First use `search_memory` to find the
    memory ID, then call this tool to delete it.

    Args:
        memory_id: The unique memory identifier (from search_memory results).

    Returns:
        Dict with "deleted": True on success, or "error" on failure.
    """
    _ensure_stores()
    if _mem0_store is None:
        return {"error": "Mem0 not configured. Set MEM0_API_KEY.", "deleted": False}

    try:
        ok = _mem0_store.delete(memory_id)
        if ok:
            return {"deleted": True, "memory_id": memory_id}
        return {"error": "Delete failed — check the memory ID is correct.", "deleted": False}
    except Exception as exc:
        logger.warning("delete_memory failed", exc_info=True)
        return {"error": str(exc), "deleted": False}


@tool
def list_memories(user_id: str = "default", limit: int = 30) -> dict[str, Any]:
    """List all stored memories with categories and metadata.

    Use when the user asks "what do you remember", "show all memories",
    "what have you learned", or wants an overview of stored knowledge.

    Args:
        user_id: User namespace for isolation (default: "default").
        limit: Maximum memories to return (default 30).

    Returns:
        Dict with "memories" list, "count", or "error" on failure.
    """
    _ensure_stores()
    if _mem0_store is None:
        return {"error": "Mem0 not configured. Set MEM0_API_KEY.", "memories": []}

    try:
        items = _mem0_store.get_all(user_id=user_id, limit=limit)
        memories = []
        for item in items:
            meta = item.value.get("metadata", {}) or {}
            memories.append({
                "id": item.key,
                "memory": item.value.get("memory", ""),
                "category": meta.get("category", ""),
                "created_at": item.value.get("created_at", ""),
                "updated_at": item.value.get("updated_at", ""),
            })
        return {"memories": memories, "count": len(memories)}
    except Exception as exc:
        logger.warning("list_memories failed", exc_info=True)
        return {"error": str(exc), "memories": []}


# ---------------------------------------------------------------------------
# 2. DATABASE tools — structured key-value storage
# ---------------------------------------------------------------------------

@tool
def search_database(
    query_filter: dict[str, Any] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search structured data records in the AstraDB database.

    Use when the user asks to look up stored data, check records, or
    retrieve structured information saved with save_to_database.

    **Important**: Data saved with `save_to_database` is stored with the
    provided key as the document `_id`. The data dictionary values are
    merged directly into the document — no automatic `type` field is added.
    To filter by type, include a `type` field in the data when saving.

    If a filter returns no results, try searching without a filter to see
    what keys are available, or search by the exact key you used when saving.

    Args:
        query_filter: Optional MongoDB-style filter (e.g. {"type": "config"}).
                      Pass None or {} to list all records.
        limit: Maximum results (default 20).

    Returns:
        Dict with "documents" list and "count", or "error" on failure.
        When no documents match, a "hint" field suggests available keys.
    """
    _ensure_stores()
    if _astra_store is None:
        return {"error": "AstraDB not configured. Set ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT.", "documents": []}

    try:
        items = _astra_store.search(
            query_filter=query_filter,
            limit=limit,
        )
        docs = [{"key": item.key, "value": item.value} for item in items]
        result: dict[str, Any] = {"documents": docs, "count": len(docs)}

        # If no results found with a filter, provide a helpful hint
        if not docs and query_filter:
            try:
                all_items = _astra_store.search(query_filter=None, limit=10)
                if all_items:
                    available_keys = [item.key for item in all_items[:5]]
                    result["hint"] = (
                        f"No documents match filter {query_filter}. "
                        f"Available keys: {available_keys}. "
                        "Try searching without a filter or by exact key."
                    )
            except Exception:
                pass  # Best effort hint, don't fail on hint generation

        return result
    except Exception as exc:
        logger.warning("search_database failed", exc_info=True)
        return {"error": str(exc), "documents": []}


@tool
def save_to_database(
    key: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Store structured data in the AstraDB database.

    Use for structured/tabular data — JSON records, analysis results,
    extracted data, configs. For natural-language facts use save_memory instead.

    Args:
        key: Unique identifier for this record.
        data: Dictionary of data to store.

    Returns:
        Dict with "saved": True on success, or "error" on failure.
    """
    _ensure_stores()
    if _astra_store is None:
        return {"error": "AstraDB not configured. Set ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT."}

    try:
        _astra_store.put(key=key, value=data)
        return {"saved": True, "key": key}
    except Exception as exc:
        logger.warning("save_to_database failed", exc_info=True)
        return {"error": str(exc), "saved": False}


# ---------------------------------------------------------------------------
# 3. DOCUMENT tools — document/content storage
# ---------------------------------------------------------------------------

@tool
def search_documents(
    doc_type: str = "",
    tags: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search stored documents (notes, PDFs, web content, etc.).

    Use when the user asks to find saved documents, notes, or content
    that was previously stored with save_document.

    Args:
        doc_type: Filter by type — "note", "pdf", "web", "email", etc. Empty for all.
        tags: Filter by tags (matches any). E.g. ["work", "project-x"].
        limit: Maximum results (default 20).

    Returns:
        Dict with "documents" list and "count", or "error" on failure.
    """
    _ensure_stores()
    if _astra_store is None:
        return {"error": "AstraDB not configured. Set ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT.", "documents": []}

    try:
        items = _astra_store.search_documents(
            doc_type=doc_type or None,
            tags=tags,
            limit=limit,
        )
        docs = [{"id": item.key, "title": item.value.get("title", ""), "doc_type": item.value.get("doc_type", ""), "tags": item.value.get("tags", []), "created_at": item.value.get("created_at", "")} for item in items]
        return {"documents": docs, "count": len(docs)}
    except Exception as exc:
        logger.warning("search_documents failed", exc_info=True)
        return {"error": str(exc), "documents": []}


@tool
def save_document(
    title: str,
    content: str,
    doc_type: str = "note",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Save a document (note, PDF text, web content, email, etc.) to storage.

    Use when the user wants to save content for later — notes, extracted
    PDF text, web page content, email archives, etc.

    Args:
        title: Document title.
        content: Full text content.
        doc_type: Type — "note", "pdf", "web", "email", "report", etc.
        tags: Optional tags for categorization.

    Returns:
        Dict with "saved": True and document id, or "error" on failure.
    """
    _ensure_stores()
    if _astra_store is None:
        return {"error": "AstraDB not configured. Set ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT."}

    # Coerce string tags — llama3.1-8b sometimes passes "['a', 'b']" as a string.
    if isinstance(tags, str):
        import ast as _ast
        try:
            parsed = _ast.literal_eval(tags)
            tags = parsed if isinstance(parsed, list) else [tags]
        except Exception:
            tags = [t.strip().strip("'\"") for t in tags.strip("[]").split(",") if t.strip()]

    try:
        doc_id = _astra_store.save_document(
            title=title,
            content=content,
            doc_type=doc_type,
            tags=tags,
        )
        return {"saved": True, "id": doc_id, "title": title}
    except Exception as exc:
        logger.warning("save_document failed", exc_info=True)
        return {"error": str(exc), "saved": False}


@tool
def delete_from_database(key: str) -> dict[str, Any]:
    """Delete a structured data record from the AstraDB database by its key.

    Use when the user says "delete this record", "remove the X entry",
    or wants to clean up stale data from agent_data. First use
    `search_database` to confirm the key exists, then call this tool.

    Args:
        key: The exact key (_id) of the record to delete.

    Returns:
        Dict with "deleted": True on success, or "error" on failure.
    """
    _ensure_stores()
    if _astra_store is None:
        return {"error": "AstraDB not configured. Set ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT.", "deleted": False}

    try:
        from deepagents.store_adapters.astra_store import COLLECTION_DATA
        ok = _astra_store.delete(key, collection=COLLECTION_DATA)
        if ok:
            return {"deleted": True, "key": key}
        return {"error": f"No record found with key {key!r}.", "deleted": False}
    except Exception as exc:
        logger.warning("delete_from_database failed", exc_info=True)
        return {"error": str(exc), "deleted": False}


@tool
def delete_document(document_id: str) -> dict[str, Any]:
    """Delete a stored document from AstraDB by its ID.

    Use when the user says "delete this document", "remove the saved note X",
    or wants to clean up agent_documents. First use `search_documents`
    to find the document ID, then call this tool.

    Args:
        document_id: The unique document ID (from search_documents results).

    Returns:
        Dict with "deleted": True on success, or "error" on failure.
    """
    _ensure_stores()
    if _astra_store is None:
        return {"error": "AstraDB not configured. Set ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT.", "deleted": False}

    try:
        from deepagents.store_adapters.astra_store import COLLECTION_DOCUMENTS
        ok = _astra_store.delete(document_id, collection=COLLECTION_DOCUMENTS)
        if ok:
            return {"deleted": True, "document_id": document_id}
        return {"error": f"No document found with id {document_id!r}.", "deleted": False}
    except Exception as exc:
        logger.warning("delete_document failed", exc_info=True)
        return {"error": str(exc), "deleted": False}


# ---------------------------------------------------------------------------
# Convenience list for importing into the agent tool list
# ---------------------------------------------------------------------------
MEMORY_TOOLS = [
    search_memory,
    save_memory,
    update_memory,
    delete_memory,
    list_memories,
    search_database,
    save_to_database,
    delete_from_database,
    search_documents,
    save_document,
    delete_document,
]
