"""
astra_store.py — AstraDB-backed persistence for task records and conversation history.

Replaces the in-memory _TaskStore so data survives Render restarts.
All writes are async and fire-and-forget — no latency added to responses.

Collections created automatically on first use:
  agent_tasks           — task lifecycle records (running/done/incomplete)
  conversation_history  — raw message log per thread_id

Falls back silently to the in-memory _TaskStore if ASTRA_DB_API_KEY /
ASTRA_DB_ENDPOINT are not set.
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


def _get_db():
    """Return an astrapy Database instance or raise if not configured."""
    api_key  = os.environ.get("ASTRA_DB_API_KEY")
    endpoint = os.environ.get("ASTRA_DB_ENDPOINT")
    if not api_key or not endpoint:
        raise RuntimeError("ASTRA_DB_API_KEY / ASTRA_DB_ENDPOINT not set")
    from astrapy import DataAPIClient
    client = DataAPIClient(token=api_key)
    return client.get_database(endpoint, keyspace=_KEYSPACE)


def _get_collection(name: str):
    """Return (or create) a collection, raising on any error."""
    db = _get_db()
    try:
        return db.create_collection(name)
    except Exception:
        return db.get_collection(name)


# ---------------------------------------------------------------------------
# Task store
# ---------------------------------------------------------------------------

class AstraTaskStore:
    """Persists every agent task to AstraDB collection `agent_tasks`.

    Writes are always synchronous-in-a-thread so the async event loop
    never blocks waiting for AstraDB network I/O.  A small in-memory
    deque mirrors the last 200 entries for fast reads (the /tasks
    endpoint returns from RAM; AstraDB is the durable backup).
    """

    COLLECTION = "agent_tasks"
    _MIRROR_MAX = 200

    def __init__(self) -> None:
        self._mirror: deque[dict] = deque(maxlen=self._MIRROR_MAX)
        self._ready = False   # becomes True on first successful write

    # ── internal ──────────────────────────────────────────────────────────

    def _write(self, op: str, doc: dict | None = None, filter_: dict | None = None,
               update: dict | None = None) -> None:
        """Execute one Astra write synchronously (called from a thread pool)."""
        try:
            col = _get_collection(self.COLLECTION)
            if op == "insert":
                col.insert_one(doc)
            elif op == "update":
                col.update_one(filter_, update)
            self._ready = True
        except Exception as exc:
            logger.warning("AstraDB task write failed (%s): %s", op, exc)

    def _async_write(self, *args, **kwargs) -> None:
        """Schedule _write on the default thread-pool executor (fire-and-forget)."""
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._write, *args, **kwargs)

    # ── public API (mirrors _TaskStore interface) ─────────────────────────

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
        self._mirror.append(doc.copy())
        self._async_write("insert", doc=doc)

    def done(self, task_id: str, response: str) -> None:
        for t in self._mirror:
            if t["id"] if "id" in t else t.get("_id") == task_id:
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
            tid = t.get("_id") or t.get("id", "")
            if tid == task_id:
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
        """Fast read from in-memory mirror — no Astra round-trip."""
        items = list(reversed(list(self._mirror)))[:n]
        # normalise _id → id for JSON responses
        return [
            {**t, "id": t.get("_id") or t.get("id", "")}
            for t in items
        ]

    def incomplete(self) -> list[dict]:
        return [t for t in self._mirror if t.get("status") == "incomplete"]

    def load_from_astra(self, limit: int = 200) -> None:
        """Called at startup to pre-populate the mirror from AstraDB."""
        try:
            col = _get_collection(self.COLLECTION)
            cursor = col.find({}, sort={"ts_start": -1}, limit=limit)
            for doc in cursor:
                self._mirror.appendleft(doc)
            logger.info("AstraTaskStore: loaded %d tasks from AstraDB", len(self._mirror))
        except Exception as exc:
            logger.info("AstraTaskStore: could not load from AstraDB (%s) — starting fresh", exc)


# ---------------------------------------------------------------------------
# Conversation history store
# ---------------------------------------------------------------------------

class AstraConversationStore:
    """Persists raw message logs to AstraDB collection `conversation_history`.

    Writes are fire-and-forget.  Reads are direct Astra queries.
    Used as fallback when the LangGraph SQLite checkpointer is empty
    (e.g. after a Render restart).
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
            "role":      role,          # "user" or "agent"
            "text":      text[:1500],
            "ts":        time.time(),
        }
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._write, doc)

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
# Singletons — import these in telegram_bot.py
# ---------------------------------------------------------------------------

task_store         = AstraTaskStore()
conversation_store = AstraConversationStore()