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
import sys
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
    """Return DA_MODEL if set, otherwise pick the best available model
    based on which API keys are present in the environment.

    Priority order is tuned for tool-calling ability and instruction-following
    with large system prompts (15k+ tokens of tools + prompt):
      1. Mistral — mistral-large is purpose-built for function calling and
                   follows complex tool instructions reliably even in large contexts
      2. NVIDIA  — llama-3.3-70b is capable but can misfire compact_conversation
                   preemptively when the system prompt is large
      3. OpenRouter — free DeepSeek models, good tool calling
      4. HuggingFace — Qwen2.5-72B, reliable tool calling
      5. OpenAI   — gpt-4o (if key present)
      6. Anthropic — claude-sonnet (if key present)
      7. Google   — gemini-2.0-flash (if key present)
    """
    explicit = os.environ.get("DA_MODEL", "").strip()
    if explicit:
        return explicit
    if os.environ.get("MISTRAL_API_KEY"):
        return "mistralai:mistral-large-latest"
    if os.environ.get("NVIDIA_API_KEY"):
        return "nvidia:meta/llama-3.3-70b-instruct"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter:deepseek/deepseek-chat-v3-0324:free"
    if os.environ.get("HUGGINGFACEHUB_API_TOKEN"):
        return "huggingface:Qwen/Qwen2.5-72B-Instruct"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai:gpt-4o"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic:claude-sonnet-4-6"
    if os.environ.get("GOOGLE_API_KEY"):
        return "google_genai:gemini-2.0-flash"
    # Pass empty string — let the server-side auto-detection handle it
    return ""


MODEL: str = _pick_model()
AGENT_ID: str = os.environ.get("DA_AGENT_ID", "default")
AUTO_APPROVE: bool = os.environ.get("DA_AUTO_APPROVE", "1").lower() in {"1", "true", "yes"}
ENABLE_SHELL: bool = os.environ.get("DA_ENABLE_SHELL", "0").lower() in {"1", "true", "yes"}

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
        for msg in reversed(messages):
            text = _text_from_message(msg)
            if text.strip():
                return text.strip()

        return "No response received."

    except Exception:
        logger.exception("Agent error (thread=%s)", thread_id)
        return "Sorry, I encountered an error — please try again."


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

            # Run the agent.
            response = await _run_agent(self._agent, message, thread_id)

        # Deliver outside the lock so the next message can start processing
        # while we're waiting for Telegram's API to accept the reply.
        self._tg.deliver_reply(telegram_chat_id, response)


# ---------------------------------------------------------------------------
# Bot runner
# ---------------------------------------------------------------------------

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
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    if not is_telegram_enabled():
        logger.error(
            "BOT_TOKEN is not set.  "
            "Add it to your Render environment variables (or .env file) and restart."
        )
        sys.exit(1)

    logger.info("Starting DeepAgents headless Telegram bot...")
    logger.info("  model       = %s", MODEL)
    logger.info("  agent_id    = %s", AGENT_ID)
    logger.info("  auto_approve= %s", AUTO_APPROVE)
    logger.info("  enable_shell= %s", ENABLE_SHELL)

    async with server_session(
        assistant_id=AGENT_ID,
        model_name=MODEL,
        auto_approve=AUTO_APPROVE,
        enable_shell=ENABLE_SHELL,
        interactive=True,
        enable_memory=False,
        enable_skills=False,
        no_mcp=True,
    ) as (agent, _server):
        bot = HeadlessBot(agent=agent)
        await bot.run()


if __name__ == "__main__":
    asyncio.run(main())