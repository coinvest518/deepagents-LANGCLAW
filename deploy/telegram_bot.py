"""Headless Telegram bot entry point — for Render (or any cloud) deployment.

This script starts the DeepAgents LangGraph server, then runs a Telegram
polling loop.  Every Telegram message becomes an agent task; the agent's
response is sent back to the same chat with typing indicators and HTML
formatting.  No Textual UI is needed — the bot runs entirely headless.

Per-user conversation memory is maintained automatically:
  - Each Telegram chat_id gets its own LangGraph thread_id.
  - Sessions persist across bot restarts via the SQLite checkpointer at
    ~/.deepagents/sessions.db (or the cloud stores if configured).

Quick-start
-----------
1. Set the required environment variables (see below).
2. Run:  python deploy/telegram_bot.py

Required environment variables
-------------------------------
BOT_TOKEN            Telegram bot token from @BotFather

One of:
  ANTHROPIC_API_KEY  For claude-* models  (default)
  OPENAI_API_KEY     For gpt-* / o* models
  GOOGLE_API_KEY     For gemini-* models

Optional environment variables
-------------------------------
DA_MODEL             Model spec (default: anthropic:claude-sonnet-4-6)
DA_AGENT_ID          Agent name / identity (default: "default")
DA_AUTO_APPROVE      "1" auto-approves all tool calls (default: "1")
DA_ENABLE_SHELL      "1" allows shell tool in the container (default: "0")
TELEGRAM_AI_OWNER_CHAT_ID  Restrict bot to this Telegram user ID only
TELEGRAM_ALWAYS_LISTEN_CHAT_IDS  Comma-separated additional allowed IDs
MEM0_API_KEY + MEM0_ENDPOINT     Persistent Mem0 memory (optional)
ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT + ASTRA_DB_KEYSPACE  AstraDB (optional)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: make CLI + SDK importable when running from the repo root
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
for _lib in ("libs/cli", "libs/deepagents"):
    _p = str(_REPO / _lib)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(dotenv_path=_REPO / ".env", override=False)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("deepagents.telegram_bot")

# ---------------------------------------------------------------------------
# Configuration (from env)
# ---------------------------------------------------------------------------

def _pick_model() -> str:
    """Pick the best available model using the smart router.

    If DA_MODEL is explicitly set, honour it (manual override).
    Otherwise use ModelRouter which tracks free-tier budgets and picks
    the provider with the most remaining capacity.
    """
    explicit = os.environ.get("DA_MODEL", "").strip()
    if explicit:
        return explicit
    # Smart router: checks which keys exist + remaining per-minute quota
    from model_router import router as _router
    picked = _router.pick("main")
    if picked:
        return picked
    # Absolute fallback (router unavailable): strong/high-quota models first
    for env_key, spec in [
        ("NVIDIA_API_KEY",           "nvidia:meta/llama-3.3-70b-instruct"),
        ("CEREBRAS_API_KEY",         "cerebras:llama3.1-8b"),
        ("OPENROUTER_API_KEY",       "openrouter:deepseek/deepseek-chat-v3-0324:free"),
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),
        ("ANTHROPIC_API_KEY",        "anthropic:claude-sonnet-4-6"),
        ("OPENAI_API_KEY",           "openai:gpt-4o"),
        ("GOOGLE_API_KEY",           "google_genai:gemini-2.0-flash"),
    ]:
        if os.environ.get(env_key):
            return spec
    return ""


def _pick_subagent_model() -> str:
    """Pick the subagent model — prefers a DIFFERENT provider than the main agent.

    This is called just before server_session starts so that subagents draw
    from a separate provider's token bucket, preventing the main agent and its
    subagents from exhausting the same rate-limit quota simultaneously.
    """
    explicit = os.environ.get("DA_SUBAGENT_MODEL", "").strip()
    if explicit:
        return explicit
    from model_router import router as _router
    # pick_subagents returns [subagent0, subagent1, ...]; we take the first
    subs = _router.pick_subagents(n=2)
    # Use the second option (most likely a different provider than main)
    return subs[1] if len(subs) > 1 else (subs[0] if subs else "")


MODEL: str = _pick_model()


def _pick_chat_model() -> str:
    """Return the fastest available model for casual chat (no tools needed).

    Priority:
      1. Ollama    — free self-hosted AWS endpoint (no API cost, fast)
      2. Cerebras  — fastest cloud inference (600k TPM free, llama3.1-8b)
      3. Mistral Small — cheap fallback
      4. Same as MODEL — no dedicated fast path

    When result equals MODEL the fast path is skipped — no point making a
    separate call to the same model just to skip tools.
    """
    if os.environ.get("OLLAMA_BASE_URL"):
        model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
        return f"ollama:{model}"
    if os.environ.get("CEREBRAS_API_KEY"):
        return "cerebras:llama3.1-8b"
    if os.environ.get("MISTRAL_API_KEY"):
        return "mistralai:mistral-small-latest"
    return MODEL  # no cheaper option available → skip fast path


CHAT_MODEL: str = _pick_chat_model()

# Regex that matches clearly casual/greeting messages.
_CASUAL_RE = re.compile(
    r"^(hi+|hey+|hello+|yo+|sup|what'?s\s*up|how\s*are\s*you|"
    r"good\s+(morning|night|evening|day|afternoon)|"
    r"thanks?(\s+you)?|ok+|okay|sure|cool|nice|great|lol+|haha+|"
    r"test(ing)?|ping|who\s+are\s+you|what\s+can\s+you\s+do)\s*[?!.]*$",
    re.IGNORECASE,
)

# Action verbs that signal the message is a task, not casual chat.
_TASK_WORDS = frozenset({
    "find", "search", "create", "make", "build", "write", "send",
    "get", "show", "list", "check", "update", "delete", "run", "open",
    "fetch", "read", "save", "add", "remove", "set", "deploy", "push",
})


def _is_casual(text: str) -> bool:
    """Return True if *text* is clearly casual chat — no tools or memory needed."""
    stripped = text.strip()
    if not stripped:
        return False
    # Explicit task vocabulary always means full agent
    lower = stripped.lower()
    if any(w in lower.split() for w in _TASK_WORDS):
        return False
    # Short messages: greeting pattern OR under 15 chars with no question mark
    if len(stripped) <= 15:
        return bool(_CASUAL_RE.match(stripped)) or "?" not in stripped
    return bool(_CASUAL_RE.match(stripped))


AGENT_ID: str = os.environ.get("DA_AGENT_ID", "default")
AUTO_APPROVE: bool = os.environ.get("DA_AUTO_APPROVE", "1").lower() in {"1", "true", "yes"}
ENABLE_SHELL: bool = os.environ.get("DA_ENABLE_SHELL", "0").lower() in {"1", "true", "yes"}
DASHBOARD_SECRET: str = os.environ.get("DASHBOARD_SECRET", "")
API_PORT: int = int(os.environ.get("PORT", "10000"))

# ---------------------------------------------------------------------------
# Imports (after path setup)
# ---------------------------------------------------------------------------
from deepagents_cli.server_manager import server_session  # noqa: E402
from deepagents_cli.sessions import generate_thread_id  # noqa: E402
import requests  # noqa: E402

from deepagents_cli.telegram_integration import (  # noqa: E402
    BOT_TOKEN,
    BASE_URL,
    COMMAND_SUBAGENT_MAP,
    TelegramIntegration,
    is_telegram_enabled,
)


def _clear_webhook() -> None:
    """Call deleteWebhook at startup to release any stuck long-poll connection.

    During Render redeploys the old container may still hold an open
    getUpdates request.  deleteWebhook forces Telegram to drop it so the
    new instance can start polling immediately without a 409 Conflict.
    """
    try:
        resp = requests.post(f"{BASE_URL}/deleteWebhook", timeout=10)
        logger.info("deleteWebhook → %s", resp.json().get("description", "ok"))
    except Exception:
        logger.warning("deleteWebhook failed (non-fatal)", exc_info=True)


# ---------------------------------------------------------------------------
# Streaming helper
# ---------------------------------------------------------------------------


def _text_from_message(msg: object) -> str:
    """Extract plain text from a message — handles LangChain objects AND plain
    dicts (aget_state returns raw dicts from the JSON state, not LC objects)."""
    if isinstance(msg, dict):
        # Only AI messages contain the response text
        if msg.get("type") not in ("ai", "AIMessage", "AIMessageChunk"):
            return ""
        if msg.get("tool_calls"):  # intermediate step, not the answer
            return ""
        content = msg.get("content", "")
    else:
        if getattr(msg, "tool_calls", None):
            return ""
        content = getattr(msg, "content", "")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return ""


def _count_tokens_in_state(messages: list) -> int:
    """Sum up token usage from all AI messages in *messages*."""
    total = 0
    for msg in messages:
        if isinstance(msg, dict):
            usage = msg.get("usage_metadata") or msg.get("response_metadata", {})
        else:
            usage = getattr(msg, "usage_metadata", None) or {}
        if isinstance(usage, dict):
            total += usage.get("total_tokens", 0) or (
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            )
    return total


async def _run_agent(agent: object, message: str, thread_id: str) -> str:
    """Run the agent for *message* and return the complete text response.

    Drains astream with default params (no subgraphs=True) so the agent
    runs to completion including all tool calls, then reads the final state.
    Using subgraphs=True caused ClosedResourceError on the server when tools
    ran inside subgraphs — removed it to fix that.
    """
    config: dict = {"configurable": {"thread_id": thread_id}}
    try:
        # Drain the stream — runs agent + tools to completion.
        async for _ in agent.astream(  # type: ignore[union-attr]
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        ):
            pass

        # Read the final state for the response text.
        state = await agent.aget_state(config)  # type: ignore[union-attr]
        if state is None:
            return "No response received."
        messages = getattr(state, "values", {}).get("messages", [])

        # Record token usage so the router can track budget consumption
        try:
            from model_router import router as _router
            tokens_used = _count_tokens_in_state(messages)
            if tokens_used > 0:
                _router.record(MODEL, tokens_used)
                logger.debug("ModelRouter: recorded %d tokens for %s", tokens_used, MODEL)
        except Exception:
            pass  # never let tracking break the response

        for msg in reversed(messages):
            text = _text_from_message(msg)
            if text.strip():
                return text.strip()

        return "No response received."

    except Exception:
        logger.exception("Agent error (thread=%s)", thread_id)
        return "Sorry, I encountered an error — please try again."


async def _quick_chat(message: str) -> str:
    """Fast direct LLM call for casual messages — no tools, no middleware overhead.

    Bypasses the full agent stack entirely: no tool schemas (~13k tokens saved),
    no memory middleware, no summarization.  Falls back to empty string on any
    error so the caller can retry via the full agent.
    """
    try:
        from langchain.chat_models import init_chat_model
        from langchain_core.messages import HumanMessage
        from langchain_core.messages import SystemMessage as SM

        parts = CHAT_MODEL.split(":", 1)
        llm = init_chat_model(parts[1], model_provider=parts[0]) if len(parts) == 2 else init_chat_model(CHAT_MODEL)
        resp = await llm.ainvoke([
            SM(content="You are a helpful AI assistant. Be friendly, concise, and natural."),
            HumanMessage(content=message),
        ])
        return str(resp.content).strip() or ""
    except Exception:
        logger.warning("Quick chat failed, falling back to full agent", exc_info=True)
        return ""


# ---------------------------------------------------------------------------
# HeadlessApp — the minimal "app" stub that TelegramIntegration expects
# ---------------------------------------------------------------------------

class HeadlessApp:
    """Minimal app shim so TelegramIntegration can forward messages without a UI.

    TelegramIntegration.handle_telegram_update checks for ``app._handle_external_message``
    and ``app.call_after_refresh``.  This class provides both, routing messages
    directly to the LangGraph agent.
    """

    def __init__(self, agent: object, tg: TelegramIntegration) -> None:
        self._agent = agent
        self._tg = tg
        # Map Telegram chat_id → LangGraph thread_id for conversation continuity.
        self._threads: dict[int, str] = {}
        # Per-chat lock — prevents concurrent streams to the same thread which
        # causes ClosedResourceError on the langgraph server.
        self._locks: dict[int, asyncio.Lock] = {}

    def _get_thread_id(self, chat_id: int) -> str:
        if chat_id not in self._threads:
            self._threads[chat_id] = generate_thread_id()
        return self._threads[chat_id]

    def reset_thread(self, chat_id: int) -> None:
        """Start a fresh conversation for *chat_id* on the next message."""
        self._threads.pop(chat_id, None)

    def call_after_refresh(self, fn: object) -> None:  # type: ignore[override]
        """Immediately invoke *fn* — no UI refresh needed in headless mode."""
        if callable(fn):
            fn()

    async def _handle_external_message(
        self,
        message: str,
        source: str = "telegram",  # noqa: ARG002
        telegram_chat_id: int | None = None,
    ) -> None:
        """Process one Telegram message through the agent and reply.

        Uses a per-chat lock so that if two messages arrive quickly, the second
        waits rather than starting a concurrent stream to the same thread — which
        causes ClosedResourceError on the langgraph server.
        """
        if telegram_chat_id is None:
            return

        if telegram_chat_id not in self._locks:
            self._locks[telegram_chat_id] = asyncio.Lock()

        async with self._locks[telegram_chat_id]:
            thread_id = self._get_thread_id(telegram_chat_id)
            logger.info("chat_id=%d thread=%s: %.80s", telegram_chat_id, thread_id, message)

            # Show typing + placeholder immediately.
            await self._tg._start_thinking(telegram_chat_id)

            # Fast path: casual messages skip the full agent stack.
            # Saves ~13k tokens (tool schemas) and responds much faster.
            # Only activates when a cheaper model is actually available.
            if _is_casual(message) and CHAT_MODEL != MODEL:
                logger.info("Fast path (casual chat, model=%s)", CHAT_MODEL)
                response = await _quick_chat(message)
                if response:
                    self._tg.deliver_reply(telegram_chat_id, response)
                    return

            # Full agent path: tasks, tool calls, anything non-trivial.
            response = await _run_agent(self._agent, message, thread_id)

        # Deliver outside the lock so the next message can start processing
        # while we're waiting for Telegram's API to accept the reply.
        self._tg.deliver_reply(telegram_chat_id, response)


# ---------------------------------------------------------------------------
# Bot runner
# ---------------------------------------------------------------------------

_INGEST_SCRIPT = _REPO / "libs/cli/deepagents_cli/built_in_skills/knowledge-base/scripts/ingest_docs.py"
_UPLOAD_DIR = Path(os.environ.get("TMPDIR", "/tmp")) / "da_uploads"


def _run_ingest_sync(local_path: str) -> str:
    """Run the ingest script in a subprocess and return a summary."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(_INGEST_SCRIPT), local_path],
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ},
    )
    output = (result.stdout + result.stderr).strip()
    lines = [l for l in output.splitlines() if l.strip()]
    return "\n".join(lines[-4:]) if lines else "Done"


class HeadlessBot:
    """Telegram long-poll loop backed by a HeadlessApp + TelegramIntegration."""

    def __init__(self, agent: object) -> None:
        # Build TelegramIntegration WITHOUT calling __init__ so we can inject app later.
        tg = object.__new__(TelegramIntegration)
        tg.app = None           # temporary; patched below
        tg.running = True
        tg.offset = None
        tg.chat_history = {}
        tg._pending_placeholders = {}
        tg._typing_tasks = {}

        app = HeadlessApp(agent=agent, tg=tg)
        tg.app = app  # wire up so handle_telegram_update forwards correctly

        self._tg = tg
        self._app = app

    async def _handle_voice(self, msg: dict, chat_id: int) -> None:
        """Transcribe a Telegram voice message and run it through the agent.

        Flow:
          1. Download the .ogg from Telegram
          2. Transcribe with faster-whisper (local, free, unlimited)
          3. Run transcription through the agent
          4. If ElevenLabs quota available, synthesize reply → sendAudio
          5. Always also send the text reply so nothing is lost
        """
        from voice_handler import transcribe, synthesize, tts_available, stt_available

        file_id = msg["voice"]["file_id"]
        duration = msg["voice"].get("duration", 0)

        if not stt_available():
            self._tg.send_message(
                chat_id,
                "🎤 Voice received but <code>faster-whisper</code> is not installed.\n"
                "Add it to requirements and redeploy.",
            )
            return

        await self._tg._start_thinking(chat_id)

        # Download the .ogg file
        try:
            resp = requests.get(f"{BASE_URL}/getFile", params={"file_id": file_id}, timeout=15)
            resp.raise_for_status()
            tg_path = resp.json()["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{tg_path}"
            _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            ogg_path = _UPLOAD_DIR / f"voice_{file_id}.ogg"
            dl = requests.get(file_url, timeout=60)
            dl.raise_for_status()
            ogg_path.write_bytes(dl.content)
        except Exception as exc:
            self._tg.send_message(chat_id, f"❌ Could not download voice message: {exc}")
            return

        # Transcribe
        text = await asyncio.to_thread(transcribe, ogg_path)
        try:
            ogg_path.unlink(missing_ok=True)
        except Exception:
            pass

        if not text:
            self._tg.send_message(chat_id, "🎤 Sorry, I couldn't understand the audio.")
            return

        logger.info("Voice transcribed (chat_id=%d, %ds): %s", chat_id, duration, text[:80])
        self._tg.send_message(chat_id, f"🎤 <i>{text}</i>")

        # Run through agent (same path as text messages)
        thread_id = self._app._get_thread_id(chat_id)
        if chat_id not in self._app._locks:
            self._app._locks[chat_id] = asyncio.Lock()

        async with self._app._locks[chat_id]:
            response = await _run_agent(self._app._agent, text, thread_id)

        # Reply with voice if quota allows, otherwise text only
        if tts_available() and len(response) <= int(os.environ.get("DA_TTS_MAX_CHARS", "400")):
            audio = await asyncio.to_thread(synthesize, response)
            if audio:
                try:
                    requests.post(
                        f"{BASE_URL}/sendAudio",
                        data={"chat_id": chat_id, "title": "Agent reply"},
                        files={"audio": ("reply.mp3", audio, "audio/mpeg")},
                        timeout=30,
                    )
                    return  # audio sent — done
                except Exception as exc:
                    logger.warning("sendAudio failed: %s", exc)

        # Fallback: text reply
        self._tg.deliver_reply(chat_id, response)

    async def _handle_document(self, msg: dict, chat_id: int) -> None:
        """Download a file sent to the bot and ingest it into the knowledge base."""
        doc = msg.get("document", {})
        file_id = doc.get("file_id", "")
        filename = doc.get("file_name", "upload")
        mime = doc.get("mime_type", "")

        allowed_ext = {".pdf", ".txt", ".md", ".rst", ".csv", ".json"}
        ext = Path(filename).suffix.lower()
        if ext not in allowed_ext:
            self._tg.send_message(
                chat_id,
                f"⚠️ Unsupported file: <code>{filename}</code>\n"
                "Supported: PDF, TXT, MD, RST, CSV, JSON",
            )
            return

        self._tg.send_message(chat_id, f"📄 Receiving <code>{filename}</code>…")
        try:
            # Resolve download URL
            resp = requests.get(
                f"{BASE_URL}/getFile",
                params={"file_id": file_id},
                timeout=30,
            )
            resp.raise_for_status()
            tg_path = resp.json()["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{tg_path}"

            # Download
            _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            local_path = _UPLOAD_DIR / filename
            dl = requests.get(file_url, timeout=120)
            dl.raise_for_status()
            local_path.write_bytes(dl.content)

            # Ingest in thread so we don't block the event loop
            summary = await asyncio.to_thread(_run_ingest_sync, str(local_path))
            self._tg.send_message(
                chat_id,
                f"✅ Ingested <code>{filename}</code>\n<pre>{summary}</pre>",
            )
        except Exception as exc:
            logger.exception("Document ingest failed for %s", filename)
            self._tg.send_message(chat_id, f"❌ Failed to ingest {filename}: {exc}")

    async def run(self) -> None:
        """Long-poll Telegram forever, dispatching each message to the agent."""
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN not set — bot cannot start.")
            return

        # Clear any stuck webhook / lingering getUpdates from a previous
        # instance (common during Render redeploys → 409 Conflict).
        _clear_webhook()

        logger.info(
            "Headless bot ready (model=%s, agent=%s, auto_approve=%s)",
            MODEL, AGENT_ID, AUTO_APPROVE,
        )

        while True:
            try:
                params: dict = {"timeout": 55, "allowed_updates": ["message"]}
                if self._tg.offset is not None:
                    params["offset"] = self._tg.offset

                data = await asyncio.to_thread(self._tg._fetch_updates, params)

                for update in data.get("result", []):
                    self._tg.offset = update["update_id"] + 1
                    try:
                        # Intercept /reset before forwarding to handle_telegram_update
                        # so we can clear the thread_id in HeadlessApp.
                        msg = update.get("message", {})
                        raw_text: str = msg.get("text", "").strip()
                        chat_id: int | None = msg.get("chat", {}).get("id")

                        if chat_id and raw_text == "/reset":
                            self._app.reset_thread(chat_id)
                            self._tg.chat_history.pop(chat_id, None)
                            self._tg.send_message(chat_id, "Conversation reset.")
                            continue

                        # Handle voice messages → transcribe + agent + optional TTS reply
                        if chat_id and msg.get("voice"):
                            await self._handle_voice(msg, chat_id)
                            continue

                        # Handle document uploads → ingest into knowledge base
                        if chat_id and msg.get("document"):
                            await self._handle_document(msg, chat_id)
                            continue

                        # Let TelegramIntegration handle all other routing
                        # (commands, media, allowed-list checks, etc.)
                        self._tg.handle_telegram_update(update)

                    except Exception:
                        logger.exception("Error handling Telegram update")

            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 409:
                    # Another instance is still polling — wait for it to shut
                    # down (Render grace period is ~30 s) then retry.
                    logger.warning("409 Conflict: another bot instance is polling. Waiting 35 s...")
                    await asyncio.sleep(35)
                else:
                    logger.exception("Telegram HTTP error — retrying in 5 s")
                    await asyncio.sleep(5)
            except Exception:
                logger.exception("Telegram polling error — retrying in 5 s")
                await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# HTTP API server (dashboard ↔ agent bridge)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# UUID helper — LangGraph requires valid UUIDs as thread IDs
# ---------------------------------------------------------------------------

def _to_uuid(thread_id: str) -> str:
    """Convert any string to a valid UUID.

    If *thread_id* is already a valid UUID it is returned unchanged.
    Otherwise a deterministic UUID-v5 is derived from the string so the
    same dashboard session always maps to the same LangGraph thread.
    """
    try:
        uuid.UUID(thread_id)
        return thread_id
    except (ValueError, AttributeError):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, thread_id))


# ---------------------------------------------------------------------------
# Task store + conversation store — AstraDB-backed persistence
# ---------------------------------------------------------------------------

try:
    from astra_store import task_store, conversation_store  # type: ignore
    _ASTRA_STORES = True
except Exception:
    # Fallback: plain in-memory stores (no AstraDB configured / package absent)
    from collections import deque as _deque

    class _TaskStore:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self._tasks: _deque[dict] = _deque(maxlen=200)

        def start(self, task_id: str, thread_id: str, message: str, source: str = "dashboard") -> None:
            self._tasks.append({"id": task_id, "thread_id": thread_id,
                                 "message": message[:300], "source": source,
                                 "status": "running", "response": "", "error": "",
                                 "ts_start": time.time(), "ts_end": None})

        def _find(self, task_id: str) -> dict | None:
            return next((t for t in self._tasks if t["id"] == task_id), None)

        def done(self, task_id: str, response: str) -> None:
            t = self._find(task_id)
            if t:
                t["status"] = "done"; t["response"] = response[:600]; t["ts_end"] = time.time()

        def fail(self, task_id: str, error: str) -> None:
            t = self._find(task_id)
            if t:
                t["status"] = "incomplete"; t["error"] = str(error)[:300]; t["ts_end"] = time.time()

        def recent(self, n: int = 50) -> list[dict]:
            return list(reversed(list(self._tasks)))[:n]

        def incomplete(self) -> list[dict]:
            return [t for t in self._tasks if t["status"] == "incomplete"]

        def load_from_astra(self) -> None:
            pass  # no-op in fallback mode

    class _ConvStore:  # type: ignore[no-redef]
        def append(self, thread_id: str, role: str, text: str) -> None:
            pass

        def get_history(self, thread_id: str, limit: int = 100) -> list[dict]:
            return []

    task_store = _TaskStore()
    conversation_store = _ConvStore()
    _ASTRA_STORES = False


def _check_secret(request: object) -> bool:
    """Return True if the request carries the correct DASHBOARD_SECRET header."""
    if not DASHBOARD_SECRET:
        return True  # no secret configured → open (trust your network / Vercel IP)
    try:
        return request.headers.get("X-Dashboard-Secret", "") == DASHBOARD_SECRET  # type: ignore[attr-defined]
    except Exception:
        return False


async def start_api_server(agent: object) -> None:
    """Run a lightweight aiohttp HTTP server exposing /health and /chat."""
    try:
        from aiohttp import web
    except ImportError:
        logger.warning("aiohttp not installed — HTTP API server disabled. pip install aiohttp to enable.")
        return

    # Keep a simple per-thread-id lock store to prevent concurrent streams
    _api_locks: dict[str, asyncio.Lock] = {}

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "model": MODEL, "agent": AGENT_ID})

    async def chat(request: web.Request) -> web.Response:
        if not _check_secret(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message: str = (data.get("message") or "").strip()
        raw_thread: str = (data.get("thread_id") or "dashboard-default").strip()
        # LangGraph requires valid UUIDs — convert deterministically
        thread_id = _to_uuid(raw_thread)

        if not message:
            return web.json_response({"error": "message is required"}, status=400)

        if thread_id not in _api_locks:
            _api_locks[thread_id] = asyncio.Lock()

        task_id = str(uuid.uuid4())
        task_store.start(task_id, thread_id, message, source="dashboard")
        conversation_store.append(thread_id, "user", message)

        async with _api_locks[thread_id]:
            try:
                if _is_casual(message) and CHAT_MODEL != MODEL:
                    response = await _quick_chat(message)
                    if response:
                        task_store.done(task_id, response)
                        conversation_store.append(thread_id, "agent", response)
                        return web.json_response({
                            "response":  response,
                            "thread_id": thread_id,
                            "task_id":   task_id,
                            "fast_path": True,
                        })
                response = await _run_agent(agent, message, thread_id)
                task_store.done(task_id, response)
                conversation_store.append(thread_id, "agent", response)
                return web.json_response({
                    "response":  response,
                    "thread_id": thread_id,
                    "task_id":   task_id,
                })
            except Exception as exc:
                logger.exception("HTTP /chat error")
                task_store.fail(task_id, str(exc))
                return web.json_response({
                    "error":     str(exc),
                    "thread_id": thread_id,
                    "task_id":   task_id,
                    "status":    "incomplete",
                }, status=500)

    async def tasks_handler(request: web.Request) -> web.Response:
        """Return recent task history with status (done / running / incomplete)."""
        if not _check_secret(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        limit = int(request.rel_url.query.get("limit", "50"))
        # Lazy-load from AstraDB on first request after a restart (zero startup cost)
        try:
            if not task_store.recent(1):
                task_store.load_from_astra()
        except Exception:
            pass
        return web.json_response({
            "tasks":      task_store.recent(limit),
            "incomplete": len(task_store.incomplete()),
        })

    async def history_handler(request: web.Request) -> web.Response:
        """Return conversation history for a thread (for dashboard replay)."""
        if not _check_secret(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        raw_thread = request.match_info.get("thread_id", "")
        thread_id = _to_uuid(raw_thread) if raw_thread else ""
        if not thread_id:
            return web.json_response({"error": "thread_id required"}, status=400)
        try:
            state = await agent.aget_state({"configurable": {"thread_id": thread_id}})  # type: ignore
            raw_msgs = [] if state is None else (getattr(state, "values", {}).get("messages", []) or [])
            messages = []
            for msg in raw_msgs:
                if isinstance(msg, dict):
                    role    = msg.get("type") or msg.get("role", "")
                    content = msg.get("content", "")
                    tools   = msg.get("tool_calls")
                else:
                    role    = getattr(msg, "type", "")
                    content = getattr(msg, "content", "")
                    tools   = getattr(msg, "tool_calls", None)
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in content
                    )
                if role in ("human", "HumanMessage"):
                    messages.append({"role": "user",  "text": str(content)})
                elif role in ("ai", "AIMessage") and not tools:
                    messages.append({"role": "agent", "text": str(content)})

            # If LangGraph state is empty (e.g. after Render restart), fall back
            # to the AstraDB conversation store which persists across restarts.
            if not messages:
                messages = conversation_store.get_history(thread_id)

            return web.json_response({"messages": messages, "thread_id": thread_id})
        except Exception as exc:
            logger.exception("HTTP /history error")
            # Best-effort: return whatever AstraDB has
            fallback = conversation_store.get_history(thread_id)
            return web.json_response({"messages": fallback, "thread_id": thread_id})

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/chat", chat)
    app.router.add_get("/tasks", tasks_handler)
    app.router.add_get("/history/{thread_id}", history_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", API_PORT)
    await site.start()
    logger.info("HTTP API server listening on port %d", API_PORT)

    # Keep alive — this coroutine runs alongside bot.run() via asyncio.gather
    while True:
        await asyncio.sleep(3600)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    if not is_telegram_enabled():
        logger.error(
            "BOT_TOKEN is not set.  "
            "Add it to your Render environment variables (or .env file) and restart."
        )
        sys.exit(1)

    # Pick subagent model — different provider than main to avoid shared rate limits.
    # Sets DA_SUBAGENT_MODEL in env so graph.py picks it up when building subagents.
    subagent_model = _pick_subagent_model()
    if subagent_model and subagent_model != MODEL:
        os.environ["DA_SUBAGENT_MODEL"] = subagent_model
        logger.info("  subagent_model = %s", subagent_model)

    logger.info("Starting DeepAgents headless Telegram bot...")
    logger.info("  model       = %s", MODEL)
    logger.info("  chat_model  = %s", CHAT_MODEL if CHAT_MODEL != MODEL else f"{MODEL} (no fast path)")
    logger.info("  agent_id    = %s", AGENT_ID)
    logger.info("  auto_approve= %s", AUTO_APPROVE)
    logger.info("  enable_shell= %s", ENABLE_SHELL)

    # Log model router status at startup
    try:
        from model_router import router as _router
        status = _router.status()
        logger.info("  model_router = %d providers configured", len(status))
        for name, info in status.items():
            logger.info("    %-25s %s", name, info["spec"])
    except Exception:
        pass

    async with server_session(
        assistant_id=AGENT_ID,
        model_name=MODEL,
        auto_approve=AUTO_APPROVE,
        enable_shell=ENABLE_SHELL,
        interactive=True,
        enable_memory=True,
        enable_skills=False,
        no_mcp=True,
    ) as (agent, _server):
        bot = HeadlessBot(agent=agent)
        await asyncio.gather(
            bot.run(),
            start_api_server(agent),
        )


if __name__ == "__main__":
    asyncio.run(main())