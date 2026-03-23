"""
astra_store.py — AstraDB-backed persistence for task records and conversation history.

Replaces the in-memory _TaskStore so data survives Render restarts.
All writes are async and fire-and-forget — no latency added to responses.

Collections:
  agent_tasks           — task lifecycle records (running/done/incomplete)
  conversation_history  — raw message log per thread_id
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections import deque

logger = logging.getLogger("deepagents.astra_store")

_KEYSPACE = os.environ.get("ASTRA_DB_KEYSPACE", "default_keyspace")

# Module-level cache — collection objects are created once and reused.
# This prevents calling createCollection on every read/write which was
# hammering AstraDB's 100-index limit and adding 2-3s of latency per call.
_db_cache: object = None
_collection_cache: dict = {}


def _get_db():
    global _db_cache
    if _db_cache is not None:
        return _db_cache
    api_key  = os.environ.get("ASTRA_DB_API_KEY")
    endpoint = os.environ.get("ASTRA_DB_ENDPOINT")
    if not api_key or not endpoint:
        raise RuntimeError("ASTRA_DB_API_KEY / ASTRA_DB_ENDPOINT not set")
    from astrapy import DataAPIClient
    _db_cache = DataAPIClient(token=api_key).get_database(endpoint, keyspace=_KEYSPACE)
    return _db_cache


def _get_collection(name: str):
    """Return a cached collection handle, creating it on first access only."""
    if name in _collection_cache:
        return _collection_cache[name]
    db = _get_db()
    try:
        # create_collection is idempotent when collection already exists — but
        # on AstraDB free tier hitting the 100-index cap makes it raise every time.
        # Fall back to get_collection (no-index-creation) when that happens.
        col = db.create_collection(name)
    except Exception as exc:
        if "100 indexes" in str(exc) or "INVALID_DATABASE_QUERY" in str(exc):
            logger.warning(
                "AstraDB 100-index limit hit for '%s' — switching to get_collection "
                "(collection already exists, this is fine)", name
            )
        else:
            logger.warning("create_collection('%s') failed (%s), using get_collection", name, exc)
        col = db.get_collection(name)
    _collection_cache[name] = col
    logger.info("AstraDB: collection '%s' ready", name)
    return col


# ---------------------------------------------------------------------------
# Task store
# ---------------------------------------------------------------------------

class AstraTaskStore:
    """Persists every agent task to AstraDB `agent_tasks`.

    In-memory deque mirrors the last 200 entries for instant reads.
    AstraDB writes are fire-and-forget (run_in_executor).
    """

    COLLECTION = "agent_tasks"
    _MIRROR_MAX = 200

    def __init__(self) -> None:
        self._mirror: deque[dict] = deque(maxlen=self._MIRROR_MAX)

    # ── internal ──────────────────────────────────────────────────────────

    def _write(self, op: str, doc: dict | None = None, filter_: dict | None = None,
               update: dict | None = None) -> None:
        try:
            col = _get_collection(self.COLLECTION)
            if op == "insert" and doc:
                col.insert_one(doc)
            elif op == "update" and filter_ and update:
                col.update_one(filter_, update)
        except Exception as exc:
            logger.warning("AstraDB task write failed (%s): %s", op, exc)

    def _async_write(self, *args, **kwargs) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._write, *args, **kwargs)
        except RuntimeError:
            pass  # no running event loop — skip fire-and-forget write

    # ── public API ─────────────────────────────────────────────────────────

    def start(self, task_id: str, thread_id: str, message: str,
              source: str = "dashboard") -> None:
        doc = {
            "_id":       task_id,
            "thread_id": thread_id,
            "message":   message[:300],
            "source":    source,
            "status":    "running",
            "response":  "",
            "error":     "",
            "ts_start":  time.time(),
            "ts_end":    None,
        }
        self._mirror.append({**doc, "id": task_id})
        self._async_write("insert", doc=doc)

    def done(self, task_id: str, response: str) -> None:
        for t in self._mirror:
            if (t.get("_id") or t.get("id")) == task_id:
                t["status"]   = "done"
                t["response"] = response[:600]
                t["ts_end"]   = time.time()
                break
        self._async_write(
            "update",
            filter_={"_id": task_id},
            update={"$set": {"status": "done", "response": response[:600],
                             "ts_end": time.time()}},
        )

    def fail(self, task_id: str, error: str) -> None:
        for t in self._mirror:
            if (t.get("_id") or t.get("id")) == task_id:
                t["status"] = "incomplete"
                t["error"]  = str(error)[:300]
                t["ts_end"] = time.time()
                break
        self._async_write(
            "update",
            filter_={"_id": task_id},
            update={"$set": {"status": "incomplete", "error": str(error)[:300],
                             "ts_end": time.time()}},
        )

    def recent(self, n: int = 50) -> list[dict]:
        return [
            {**t, "id": t.get("_id") or t.get("id", "")}
            for t in list(reversed(list(self._mirror)))[:n]
        ]

    def incomplete(self) -> list[dict]:
        return [t for t in self._mirror if t.get("status") == "incomplete"]

    def load_from_astra(self, limit: int = 200) -> None:
        """Lazy-load from AstraDB into mirror (called on first /tasks request)."""
        try:
            col = _get_collection(self.COLLECTION)
            cursor = col.find({}, sort={"ts_start": -1}, limit=limit)
            loaded = 0
            for doc in cursor:
                self._mirror.appendleft({**doc, "id": doc.get("_id", "")})
                loaded += 1
            logger.info("AstraTaskStore: loaded %d tasks from AstraDB", loaded)
        except Exception as exc:
            logger.info("AstraTaskStore: could not load from AstraDB (%s) — starting fresh", exc)


# ---------------------------------------------------------------------------
# Conversation history store
# ---------------------------------------------------------------------------

class AstraConversationStore:
    """Persists raw message logs to AstraDB `conversation_history`.

    Writes are fire-and-forget.  Reads are direct Astra queries.
    Used as fallback when LangGraph SQLite checkpointer is empty after restart.
    """

    COLLECTION = "conversation_history"

    def __init__(self) -> None:
        self._enabled = bool(
            os.environ.get("ASTRA_DB_API_KEY") and os.environ.get("ASTRA_DB_ENDPOINT")
        )

    def _write(self, doc: dict) -> None:
        try:
            col = _get_collection(self.COLLECTION)
            col.insert_one(doc)
        except Exception as exc:
            logger.debug("AstraConversationStore write failed: %s", exc)

    def append(self, thread_id: str, role: str, text: str) -> None:
        """Append one message asynchronously — never blocks the caller."""
        if not self._enabled:
            return
        doc = {
            "_id":       str(uuid.uuid4()),
            "thread_id": thread_id,
            "role":      role,
            "text":      text[:1500],
            "ts":        time.time(),
        }
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._write, doc)
        except RuntimeError:
            pass  # no running event loop — skip

    def get_history(self, thread_id: str, limit: int = 100) -> list[dict]:
        """Return messages for *thread_id* ordered oldest-first."""
        if not self._enabled:
            return []
        try:
            col = _get_collection(self.COLLECTION)
            cursor = col.find(
                {"thread_id": thread_id},
                sort={"ts": 1},
                limit=limit,
            )
            return [
                {"role": d["role"], "text": d["text"], "ts": d.get("ts", 0)}
                for d in cursor
            ]
        except Exception as exc:
            logger.debug("AstraConversationStore read failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

task_store         = AstraTaskStore()
conversation_store = AstraConversationStore()
