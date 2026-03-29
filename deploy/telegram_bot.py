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
    # Absolute fallback (router unavailable): direct-API providers first
    for env_key, spec in [
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),
        ("NVIDIA_API_KEY",           "nvidia:meta/llama-3.3-70b-instruct"),
        ("OPENROUTER_API_KEY",       "openrouter:mistralai/mistral-small-3.1-24b-instruct:free"),
        ("CEREBRAS_API_KEY",         "cerebras:llama-3.3-70b"),
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),
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
        return "cerebras:llama-3.3-70b"
    if os.environ.get("MISTRAL_API_KEY"):
        return "mistralai:mistral-small-latest"
    return MODEL  # no cheaper option available → skip fast path


CHAT_MODEL: str = _pick_chat_model()

# Phrases that mean "I'm handing this off" — Musa says these when escalating.
# Detecting them: (a) returns (text, True) so user sees Musa's reply, AND
# (b) triggers real code-level handoff to run the full agent in background.
# Include Musa's natural handoff phrases from agent_soul.md.
_HANDOFF_PHRASES = (
    # Natural Musa handoff language (from soul)
    "on it 🔄",
    "on it.",
    "let me check that",
    "running that now",
    "let me pull it up",
    "i'll hand that off",
    "hand that off",
    "i'll pass this",
    # Escalation signals
    "main agent",
    "escalat",
    "can't do that directly",
    "i don't have access to",
    "i cannot access",
    "need to use the",
)

# ---------------------------------------------------------------------------
# Musa soul — loaded once, injected into every quick-chat call
# ---------------------------------------------------------------------------
_SOUL_CACHE: str | None = None


def _load_soul() -> str:
    global _SOUL_CACHE
    if _SOUL_CACHE is None:
        soul_path = Path(__file__).parent / "agent_soul.md"
        _SOUL_CACHE = (
            soul_path.read_text(encoding="utf-8")
            if soul_path.exists()
            else "You are Musa, Daniel's personal AI assistant for FDWA (Futuristic Digital Wealth Agency)."
        )
    return _SOUL_CACHE




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

# Import Quick Chat module for standalone functionality
from quick_chat import handle_quick_chat, should_use_quick_chat


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
    dicts (aget_state returns raw dicts from the JSON state, not LC objects).

    Must handle all message formats: LangChain BaseMessage subclasses,
    raw dicts from JSON state, and edge cases from fallback models.
    """
    if isinstance(msg, dict):
        # Only AI messages contain the response text
        msg_type = msg.get("type", "")
        # Accept: "ai", "AIMessage", "AIMessageChunk", or missing type with content
        if msg_type and msg_type not in ("ai", "AIMessage", "AIMessageChunk"):
            return ""
        if msg.get("tool_calls"):  # intermediate step, not the answer
            return ""
        content = msg.get("content", "")
    else:
        # LangChain message objects — check type name
        type_name = getattr(msg, "type", "") or type(msg).__name__
        if type_name not in ("ai", "AIMessage", "AIMessageChunk") and "AI" not in type(msg).__name__:
            return ""
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


# Map raw tool names to human-readable status labels shown in Telegram.
_TOOL_LABELS: dict[str, str] = {
    # Search / web
    "web_search": "🔍 Searching web",
    "tavily_search_results_json": "🔍 Searching web",
    "tavily_search": "🔍 Searching web",
    "fetch_url": "🌐 Fetching URL",
    "http_request": "🌐 HTTP request",
    # Files
    "read_file": "📄 Reading file",
    "write_file": "✏️ Writing file",
    "edit_file": "✏️ Editing file",
    "glob_search": "🗂️ Scanning files",
    "list_directory": "🗂️ Listing directory",
    # Shell / code
    "run_command": "⚙️ Running command",
    "run_python": "🐍 Running Python",
    "execute": "⚙️ Executing",
    "execute_python": "🐍 Running Python",
    # Planning
    "ask_user": "❓ Waiting for input",
    "task": "🤖 Spawning subagent",
    "create_task": "📋 Creating task",
    "write_todos": "📋 Planning tasks",
    "create_cron_job": "⏰ Scheduling cron",
    # Browser
    "browser_navigate": "🌐 Opening page",
    "browser_screenshot": "📸 Screenshot",
    # Gmail
    "GMAIL_SEND_EMAIL": "📧 Sending email",
    "GMAIL_FETCH_EMAILS": "📧 Reading email",
    "send_email": "📧 Sending email",
    # GitHub
    "GITHUB_CREATE_AN_ISSUE": "🐙 Creating issue",
    "GITHUB_LIST_REPOSITORY_ISSUES": "🐙 Listing issues",
    "github_api": "🐙 GitHub",
    # Sheets
    "GOOGLESHEETS_BATCH_UPDATE": "📊 Updating Sheets",
    "GOOGLESHEETS_BATCH_GET": "📊 Reading Sheets",
    "GOOGLESHEETS_CREATE_SPREADSHEET": "📊 Creating Sheet",
    # Drive / Docs
    "GOOGLEDRIVE_LIST_FILES": "📁 Google Drive",
    "GOOGLEDRIVE_UPLOAD_FILE": "📁 Uploading to Drive",
    # Slack
    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL": "💬 Slack message",
    # Notion
    "NOTION_ADD_PAGE_CONTENT": "📓 Writing Notion",
    "NOTION_SEARCH_NOTION_PAGE": "📓 Searching Notion",
    "NOTION_CREATE_NOTION_PAGE": "📓 Creating Notion page",
    # Social
    "TWITTER_CREATION_OF_A_POST": "🐦 Tweeting",
    "LINKEDIN_CREATE_LINKED_IN_POST": "💼 LinkedIn post",
    "INSTAGRAM_CREATE_POST": "📸 Instagram post",
    "INSTAGRAM_CREATE_MEDIA_CONTAINER": "📸 Instagram media",
    "FACEBOOK_CREATE_POST": "📘 Facebook post",
    # Telegram
    "TELEGRAM_SEND_MESSAGE": "✈️ Telegram message",
    # Composio single dispatcher
    "composio_action": "🔗 Composio",
    "composio": "🔗 Composio action",
    "composio_get_schema": "📋 Discovering tool schema",
    # Memory tools
    "search_memory": "🧠 Searching memory",
    "save_memory": "🧠 Saving to memory",
    "search_database": "🗄️ Querying database",
    "save_to_database": "🗄️ Saving to database",
    # Calendar / Events
    "GOOGLECALENDAR_CREATE_EVENT": "📅 Creating event",
    "GOOGLECALENDAR_FIND_EVENT": "📅 Finding events",
    "GOOGLECALENDAR_LIST_CALENDARS": "📅 Listing calendars",
    # YouTube
    "YOUTUBE_SEARCH_YOU_TUBE": "▶️ Searching YouTube",
    "YOUTUBE_VIDEO_DETAILS": "▶️ Getting video details",
    "YOUTUBE_LIST_CHANNEL_VIDEOS": "▶️ Listing videos",
    # Dropbox
    "DROPBOX_LIST_FILES_IN_FOLDER": "📦 Listing Dropbox",
    "DROPBOX_EXPORT_FILE": "📦 Downloading from Dropbox",
    "DROPBOX_UPLOAD_FILE_TO_DROPBOX": "📦 Uploading to Dropbox",
    # Google Docs
    "GOOGLEDOCS_GET_DOCUMENT_BY_ID": "📝 Reading Google Doc",
    "GOOGLEDOCS_CREATE_NEW_GOOGLE_DOC": "📝 Creating Google Doc",
    # Google Analytics
    "GOOGLE_ANALYTICS_RUN_REPORT": "📈 Running analytics report",
    # Notion extras
    "NOTION_RETRIEVE_PAGE": "📓 Fetching Notion page",
    "NOTION_FETCH_DATABASE": "📓 Fetching Notion DB",
    "NOTION_INSERT_ROW_DATABASE": "📓 Adding Notion row",
    "NOTION_APPEND_TEXT_BLOCKS": "📓 Writing Notion block",
}


def _tool_name_to_label(name: str) -> str:
    """Map a raw tool name to an emoji label, falling back to the name itself.

    For Composio SCREAMING_SNAKE_CASE actions not in _TOOL_LABELS, auto-generate
    a readable label: GMAIL_SEND_EMAIL → "📧 Gmail: Send Email"
    """
    if name in _TOOL_LABELS:
        return _TOOL_LABELS[name]
    # Auto-label COMPOSIO_STYLE_ACTIONS → "🔗 Service: Action Words"
    if "_" in name and name == name.upper():
        parts = name.split("_", 1)
        if len(parts) == 2:
            service = parts[0].capitalize()
            action = parts[1].replace("_", " ").title()
            # Pick an emoji based on service
            svc_icons = {
                "GMAIL": "📧", "GITHUB": "🐙", "SLACK": "💬",
                "NOTION": "📓", "YOUTUBE": "▶️", "TWITTER": "🐦",
                "LINKEDIN": "💼", "INSTAGRAM": "📸", "FACEBOOK": "📘",
                "DROPBOX": "📦", "TELEGRAM": "✈️",
                "GOOGLESHEETS": "📊", "GOOGLEDRIVE": "📁",
                "GOOGLEDOCS": "📝", "GOOGLECALENDAR": "📅",
            }
            icon = svc_icons.get(parts[0], "🔗")
            return f"{icon} {service}: {action}"
    return f"🔧 {name}"


def _extract_tool_detail(tc: object) -> str:
    """Build a human-readable label from a tool call INCLUDING its key argument.

    Instead of just "📧 Sending email", shows "📧 Sending email → danny@example.com"
    so the user sees WHAT the agent is actually doing.
    """
    name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
    args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
    if isinstance(args, str):
        try:
            import json as _j
            args = _j.loads(args)
        except Exception:
            args = {}

    label = _tool_name_to_label(name)

    # Extract the most meaningful argument to show context
    detail = ""
    if isinstance(args, dict):
        # Priority order: show the most informative arg
        for key in ("query", "text", "url", "action", "command", "owner",
                     "question", "title", "to", "channel", "path", "content",
                     "repo", "database_id", "spreadsheet_id", "parent_id"):
            val = args.get(key)
            if val and isinstance(val, str):
                detail = val[:60]
                break
        if not detail:
            # Composio action: show the action slug
            if name in ("composio_action", "composio") and args.get("action"):
                action_slug = args["action"]
                inner_args = args.get("arguments", {})
                detail = action_slug
                # Try to get a meaningful arg from the inner arguments too
                if isinstance(inner_args, dict):
                    for key in ("query", "text", "url", "to", "title", "path", "max_results"):
                        val = inner_args.get(key)
                        if val and isinstance(val, str):
                            detail = f"{action_slug} → {val[:40]}"
                            break

    if detail:
        return f"{label} → {detail}"
    return label


def _extract_msgs(node: object) -> list:
    """Safely extract messages list from a graph node value."""
    if isinstance(node, dict):
        return node.get("messages", [])
    return []


def _status_from_update(data: dict) -> str:
    """Extract status from an 'updates' mode chunk (dict with node names as keys).

    Handles ANY node name (model, agent, chatbot, tools, worker, etc.) — not
    just hardcoded "model"/"tools". Extracts tool call details including
    arguments so the user sees WHAT the agent is doing, not just "Thinking…".
    """
    # Skip interrupt-only updates
    if "__interrupt__" in data:
        return ""

    for node_name, node_value in data.items():
        if node_name.startswith("__"):
            continue  # skip __interrupt__, __metadata__, etc.

        msgs = _extract_msgs(node_value)
        if not msgs:
            continue

        for msg in msgs:
            # Check for tool calls (LLM decided to invoke tools)
            tcs = (
                getattr(msg, "tool_calls", None)
                or (msg.get("tool_calls") if isinstance(msg, dict) else None)
                or []
            )
            if tcs:
                labels = [_extract_tool_detail(tc) for tc in tcs]
                return "\n".join(labels)

            # Check for tool results (tool finished executing)
            msg_type = getattr(msg, "type", "") or (msg.get("type", "") if isinstance(msg, dict) else "")
            tool_name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
            if tool_name and msg_type in ("tool", "ToolMessage"):
                status_str = getattr(msg, "status", "success") if hasattr(msg, "status") else (msg.get("status", "success") if isinstance(msg, dict) else "success")
                icon = "✓" if status_str == "success" else "✗"
                return f"{_tool_name_to_label(tool_name)} {icon}"

            # AI message with content but no tool calls = thinking/reasoning
            content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
            if content and msg_type in ("ai", "AIMessage", "AIMessageChunk"):
                # Show a snippet of what the AI is actually writing
                text = content if isinstance(content, str) else str(content)
                text = text.strip()
                if len(text) > 60:
                    text = text[:57] + "…"
                if text:
                    return f"✍️ {text}"

    return ""


def _status_from_message_chunk(msg: object) -> str:
    """Extract status from a streaming 'messages' mode message chunk.

    Shows REAL details — tool names with arguments, content snippets — not
    generic "Thinking…".
    """
    # Streaming tool call — name appears in the first chunk
    tcc = getattr(msg, "tool_call_chunks", None) or []
    if tcc:
        labels = []
        for tc in tcc:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name") or ""
            if name:
                labels.append(_tool_name_to_label(name))
        if labels:
            return "\n".join(labels)

    # Fully resolved tool calls (non-streaming path) — show with args
    tc_list = getattr(msg, "tool_calls", None) or []
    if tc_list:
        labels = [_extract_tool_detail(tc) for tc in tc_list]
        if labels:
            return "\n".join(labels)

    # Tool result — show what just finished
    tool_name = getattr(msg, "name", None)
    msg_type = getattr(msg, "type", "") or (msg.get("type", "") if isinstance(msg, dict) else "")
    if tool_name and msg_type in ("tool", "ToolMessage"):
        return _tool_name_to_label(tool_name) + " ✓"

    # Model streaming content — show a snippet, not just "Thinking…"
    content = getattr(msg, "content", None)
    if content and isinstance(content, str):
        text = content.strip()
        if text:
            snippet = text[:60] + ("…" if len(text) > 60 else "")
            return f"✍️ {snippet}"

    return ""


async def _run_agent(
    agent: object,
    agent_input: object,
    thread_id: str,
    progress_cb: object = None,
) -> tuple[str, list]:
    """Run the agent for *agent_input* and return ``(response_text, interrupts)``.

    *agent_input* is either:
    - ``{"messages": [{"role": "user", "content": "..."}]}`` for a new turn
    - A ``Command(resume={interrupt_id: answer})`` to continue after a pause

    *interrupts* is ``[]`` on normal completion, or a list of LangGraph
    ``Interrupt`` objects if the agent paused waiting for user input (ask_user).

    progress_cb: optional async callable(status: str) — called each time a
    meaningful step is detected, rate-limited to once per second.
    Heartbeat fires "🤔 Thinking…" every 4 seconds if nothing else fires.
    """
    import time as _time
    config: dict = {"configurable": {"thread_id": thread_id}}
    try:
        _last_progress = 0.0
        _last_heartbeat = _time.monotonic()
        _MIN_INTERVAL = 1.0    # minimum seconds between any two progress edits
        _HEARTBEAT_EVERY = 4.0

        async def _maybe_update(status: str) -> None:
            nonlocal _last_progress, _last_heartbeat
            if progress_cb is None or not status:
                return
            now = _time.monotonic()
            if now - _last_progress < _MIN_INTERVAL:
                return
            _last_progress = now
            _last_heartbeat = now
            try:
                await progress_cb(status)  # type: ignore[misc]
            except Exception:
                pass

        detected_interrupts: list = []

        # Drain the stream — runs agent + tools to completion.
        # RemoteAgent.astream yields 3-tuples: (namespace, mode, data)
        async for chunk in agent.astream(agent_input, config=config):  # type: ignore[union-attr]
            # Unpack the 3-tuple that RemoteAgent yields
            if isinstance(chunk, tuple) and len(chunk) == 3:
                _ns, mode, data = chunk
                if mode == "updates" and isinstance(data, dict):
                    # Detect LangGraph ask_user interrupt
                    if "__interrupt__" in data:
                        intr_list = data["__interrupt__"]
                        if intr_list:
                            detected_interrupts.extend(intr_list)
                            break
                    if progress_cb is not None:
                        status = _status_from_update(data)
                        await _maybe_update(status)
                elif mode == "messages" and progress_cb is not None:
                    msg = data[0] if isinstance(data, tuple) else data
                    status = _status_from_message_chunk(msg)
                    await _maybe_update(status)
            else:
                # Fallback: legacy dict chunk
                if isinstance(chunk, dict):
                    if "__interrupt__" in chunk:
                        intr_list = chunk["__interrupt__"]
                        if intr_list:
                            detected_interrupts.extend(intr_list)
                            break
                    if progress_cb is not None:
                        status = _status_from_update(chunk)
                        await _maybe_update(status)

            # Heartbeat: if silent too long, show the AI is still processing
            if progress_cb is not None:
                now = _time.monotonic()
                if now - _last_heartbeat >= _HEARTBEAT_EVERY:
                    _last_heartbeat = now
                    try:
                        await progress_cb("🧠 Reasoning…")  # type: ignore[misc]
                    except Exception:
                        pass

        if detected_interrupts:
            return "", detected_interrupts

        # Read the final state for the response text.
        state = await agent.aget_state(config)  # type: ignore[union-attr]
        if state is None:
            return "No response received.", []
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
                return text.strip(), []

        return "No response received.", []

    except asyncio.CancelledError:
        raise  # let /stop propagate
    except Exception:
        logger.exception("Agent error (thread=%s)", thread_id)
        raise  # bubble up so _handle_external_message shows the real error


# ---------------------------------------------------------------------------
# Musa lightweight tool set (Cerebras tool loop — no LangGraph needed)
# ---------------------------------------------------------------------------

# Musa tools — lightweight versions for quick tasks so we don't need the
# full LangGraph agent for simple lookups. Musa is the brain/soul and can
# handle: web search, memory, chat history, time, URL fetch.
# Only hands off to the full agent for multi-step tasks (email, posting, etc.)
_MUSA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information. Use for: weather, news, "
                "stock prices, scores, facts, anything needing real-time data. "
                "Returns top 3 results with titles, URLs, and snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": (
                "Search the agent's long-term memory for past conversations, saved facts, "
                "user preferences, and previous task results. Use when the user asks: "
                "'what did we discuss', 'remember when', 'what did the agent do', "
                "'check memory', or references past work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for in memory"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save information to long-term memory. Use when user says 'remember this', "
                "'save this', 'note that', or when you learn something important."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "What to remember"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and read the content of a web page URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "handoff_to_agent",
            "description": (
                "Pass to the full AI agent for HEAVY tasks only. Use ONLY for: "
                "sending emails, posting to social media, creating spreadsheets, "
                "GitHub operations, multi-step workflows, code execution, file operations, "
                "or anything needing Composio integrations (Gmail, Sheets, etc.). "
                "Do NOT use for: web search, memory lookup, simple questions — handle those yourself."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


_MUSA_HANDOFF_SENTINEL = "__HANDOFF__"


async def _execute_musa_tool(name: str, args: dict) -> str:
    """Execute one Musa tool and return a result string."""
    try:
        if name == "handoff_to_agent":
            return _MUSA_HANDOFF_SENTINEL

        if name == "get_time":
            import datetime
            return datetime.datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S")

        if name == "web_search":
            tavily_key = os.environ.get("TAVILY_API_KEY", "")
            if not tavily_key:
                return "Web search unavailable (no TAVILY_API_KEY)."
            import json as _json
            body = _json.dumps({
                "api_key": tavily_key,
                "query": args.get("query", ""),
                "max_results": 3,
            })
            resp = await asyncio.to_thread(
                requests.post,
                "https://api.tavily.com/search",
                data=body,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code != 200:
                return f"Search failed (status {resp.status_code})."
            results = resp.json().get("results", [])
            if not results:
                return "No results found."
            return "\n\n".join(
                f"{r.get('title','')}\n{r.get('url','')}\n{r.get('content','')[:300]}"
                for r in results
            )

        if name == "fetch_url":
            url = args.get("url", "")
            if not url:
                return "No URL provided."
            resp = await asyncio.to_thread(
                requests.get, url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code != 200:
                return f"Fetch failed (status {resp.status_code})."
            # Strip HTML tags simply
            import re as _re
            text = _re.sub(r"<[^>]+>", " ", resp.text)
            text = _re.sub(r"\s+", " ", text).strip()
            return text[:1500]

        if name == "search_memory":
            query = args.get("query", "")
            if not query:
                return "No query provided."
            # Try Mem0 first (semantic), then AstraDB (structured)
            results_text = []
            mem0_key = os.environ.get("MEM0_API_KEY", "")
            if mem0_key:
                try:
                    import json as _json
                    body = _json.dumps({
                        "query": query,
                        "filters": {"AND": [{"user_id": "default"}]},
                        "limit": 5,
                    })
                    resp = await asyncio.to_thread(
                        requests.post,
                        "https://api.mem0.ai/v2/memories/search/",
                        data=body,
                        headers={
                            "Authorization": f"Token {mem0_key}",
                            "Content-Type": "application/json",
                        },
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        hits = resp.json().get("results", [])
                        for h in hits:
                            mem = h.get("memory", "")
                            score = h.get("score", "")
                            created = h.get("created_at", "")[:10]
                            if mem:
                                results_text.append(f"[{created}] {mem} (relevance: {score})")
                except Exception as exc:
                    results_text.append(f"(Mem0 error: {exc})")

            astra_key = os.environ.get("ASTRA_DB_API_KEY", "")
            astra_endpoint = os.environ.get("ASTRA_DB_ENDPOINT", "")
            if astra_key and astra_endpoint:
                try:
                    from astrapy import DataAPIClient
                    client = DataAPIClient()
                    db = client.get_database(astra_endpoint, token=astra_key)
                    coll = db.get_collection("agent_memory")
                    docs = list(coll.find({"user_id": "default"}, limit=5))
                    for d in docs:
                        content = d.get("content", "")
                        cat = d.get("category", "")
                        created = d.get("created_at", "")[:10]
                        if content:
                            results_text.append(f"[{created}] [{cat}] {content}")
                except Exception as exc:
                    results_text.append(f"(AstraDB error: {exc})")

            if not results_text:
                return "No memories found for that query."
            return f"Found {len(results_text)} memories:\n\n" + "\n".join(results_text)

        if name == "save_memory":
            content = args.get("content", "")
            if not content:
                return "No content provided."
            saved_to = []
            mem0_key = os.environ.get("MEM0_API_KEY", "")
            if mem0_key:
                try:
                    import json as _json
                    body = _json.dumps({
                        "messages": [{"role": "user", "content": content}],
                        "user_id": "default",
                    })
                    resp = await asyncio.to_thread(
                        requests.post,
                        "https://api.mem0.ai/v2/memories/",
                        data=body,
                        headers={
                            "Authorization": f"Token {mem0_key}",
                            "Content-Type": "application/json",
                        },
                        timeout=10,
                    )
                    if resp.status_code in (200, 201):
                        saved_to.append("Mem0")
                except Exception:
                    pass

            astra_key = os.environ.get("ASTRA_DB_API_KEY", "")
            astra_endpoint = os.environ.get("ASTRA_DB_ENDPOINT", "")
            if astra_key and astra_endpoint:
                try:
                    from astrapy import DataAPIClient
                    from datetime import datetime, timezone
                    client = DataAPIClient()
                    db = client.get_database(astra_endpoint, token=astra_key)
                    coll = db.get_collection("agent_memory")
                    coll.insert_one({
                        "content": content,
                        "user_id": "default",
                        "category": "general",
                        "type": "memory",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    saved_to.append("AstraDB")
                except Exception:
                    pass

            if saved_to:
                return f"Saved to {', '.join(saved_to)}: {content[:100]}"
            return "Could not save — no memory backend configured."

    except Exception as exc:
        return f"Tool error: {exc}"

    return "Unknown tool."


async def _cerebras_chat(message: str, soul: str) -> str | None:
    """Cerebras cloud fallback for Musa — with a lightweight tool loop.

    Supports: web_search (Tavily), get_time, fetch_url.
    Uses Cerebras's OpenAI-compatible API (no langchain-cerebras needed).
    Returns reply text, or None on failure.
    """
    key = os.environ.get("CEREBRAS_API_KEY", "")
    if not key:
        return None
    try:
        import json as _json
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, ToolMessage
        from langchain_core.messages import SystemMessage as SM

        llm = ChatOpenAI(
            model="llama3.1-8b",
            api_key=key,
            base_url="https://api.cerebras.ai/v1",
        )
        llm_with_tools = llm.bind_tools(_MUSA_TOOLS)

        msgs: list = [SM(content=soul), HumanMessage(content=message)]

        for _iteration in range(3):  # max 3 tool calls then final answer
            resp = await llm_with_tools.ainvoke(msgs)
            tool_calls = getattr(resp, "tool_calls", None) or []

            if not tool_calls:
                # No tool call — this is the final answer
                text = str(resp.content).strip()
                if text:
                    logger.info("Cerebras reply (iter=%d): %.80s", _iteration, text)
                return text or None

            # Execute all tool calls in this turn
            msgs.append(resp)
            for tc in tool_calls:
                tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                tc_id = tc.get("id", tc_name) if isinstance(tc, dict) else getattr(tc, "id", tc_name)
                if isinstance(tc_args, str):
                    try:
                        tc_args = _json.loads(tc_args)
                    except Exception:
                        tc_args = {}
                logger.info("Musa tool call: %s(%s)", tc_name, tc_args)
                result = await _execute_musa_tool(tc_name, tc_args)
                if result == _MUSA_HANDOFF_SENTINEL:
                    logger.info("Musa handoff_to_agent called — escalating to full agent")
                    return None  # triggers handoff=True in _quick_chat
                msgs.append(ToolMessage(content=result, tool_call_id=tc_id))

        # Exhausted iterations — ask for final answer without tools
        resp = await llm.ainvoke(msgs)
        text = str(resp.content).strip()
        return text or None

    except Exception as exc:
        logger.warning("Cerebras fallback failed: %s", exc)
        return None


async def _quick_chat(message: str) -> tuple[str, bool]:
    """Ask Musa (Ollama) with soul context. Returns (reply, handoff).

    Routing is handled by should_use_quick_chat() before this is called.
    Musa just answers with personality and FDWA context.
    Falls back to handoff=True on any error so nothing is dropped.
    """
    soul = _load_soul()
    try:
        if CHAT_MODEL.startswith("ollama:"):
            import json as _json
            model_name = CHAT_MODEL.replace("ollama:", "")
            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://13.222.51.51:11434")
            body = _json.dumps({
                "model": model_name,
                "messages": [
                    {"role": "system", "content": soul},
                    {"role": "user", "content": message},
                ],
                "stream": False,
            })
            resp = await asyncio.to_thread(
                requests.post,
                f"{ollama_url}/api/chat",
                data=body,
                headers={"Content-Type": "application/json"},
                timeout=int(os.environ.get("OLLAMA_TIMEOUT", "20")),
            )
            if resp.status_code == 200:
                text = resp.json().get("message", {}).get("content", "").strip()
            else:
                logger.warning("Ollama returned %d — trying Cerebras fallback", resp.status_code)
                text = await _cerebras_chat(message, soul)
                if text is None:
                    return ("", True)
        else:
            # Non-Ollama: use Cerebras tool loop (has web_search, memory, etc.)
            # This gives Musa full tool capabilities regardless of chat model.
            text = await _cerebras_chat(message, soul)
            if text is None:
                return ("", True)  # fallback failed → hand off

        if not text:
            return ("", True)
        # If Musa's reply contains a handoff phrase, escalate but keep the text
        # so the user sees Musa's "On it 🔄" before the full agent starts.
        if any(phrase in text.lower() for phrase in _HANDOFF_PHRASES):
            logger.info("Musa handoff phrase detected — escalating to full agent")
            return (text, True)
        return (text, False)

    except Exception:
        logger.warning("Musa quick-chat (Ollama) failed — trying Cerebras fallback")
        try:
            text = await _cerebras_chat(message, soul)
            if text:
                return (text, False)
        except Exception:
            pass
        return ("", True)


# ---------------------------------------------------------------------------
# HeadlessApp — the minimal "app" stub that TelegramIntegration expects
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Agent mode system — per-chat persona switching via /mode command
# ---------------------------------------------------------------------------

_MODES_DIR = _REPO / ".deepagents" / "modes"

# Registry: name → (emoji, one-line description)
_MODE_REGISTRY: dict[str, tuple[str, str]] = {
    "default":    ("🤖", "FDWA AI assistant — full capabilities"),
    "content":    ("✍️", "Content writer — blogs, articles, how-to guides"),
    "researcher": ("🔬", "Deep researcher — exhaustive sourced research"),
    "social":     ("📱", "Social media manager — LinkedIn, Twitter, Instagram"),
    "ralph":      ("🔁", "Autonomous builder — loops until task is done"),
    "coder":      ("💻", "Coding specialist — write, debug, review code"),
}

_mode_content_cache: dict[str, str] = {}


def _load_mode_content(mode: str) -> str:
    """Load the markdown content for *mode* from .deepagents/modes/, cached."""
    if mode in _mode_content_cache:
        return _mode_content_cache[mode]
    if mode == "default":
        return ""
    path = _MODES_DIR / f"{mode}.md"
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        _mode_content_cache[mode] = content
        return content
    return ""


def _build_mode_list_message(current: str) -> str:
    lines = ["<b>🎭 Agent Modes</b>\n"]
    for name, (emoji, desc) in _MODE_REGISTRY.items():
        active = " ← <i>active</i>" if name == current else ""
        lines.append(f"{emoji} <code>/mode {name}</code> — {desc}{active}")
    lines.append("\nType <code>/mode &lt;name&gt;</code> to switch.")
    lines.append("Type <code>/mode default</code> to reset.")
    return "\n".join(lines)


def _inject_mode_context(message: str, mode: str) -> str:
    """Prepend the mode's instructions to *message* if a non-default mode is active."""
    if mode == "default":
        return message
    content = _load_mode_content(mode)
    if not content:
        return message
    emoji, desc = _MODE_REGISTRY.get(mode, ("🎭", mode))
    return (
        f"[ACTIVE MODE: {desc}]\n\n"
        f"{content}\n\n"
        f"---\n\n"
        f"{message}"
    )


class HeadlessApp:
    """Minimal app shim so TelegramIntegration can forward messages without a UI.

    TelegramIntegration.handle_telegram_update checks for ``app._handle_external_message``
    and ``app.call_after_refresh``.  This class provides both, routing messages
    directly to the LangGraph agent.

    Mode switching: /mode <name> changes the agent's active persona for the
    session by prepending mode-specific instructions to every message.
    """

    def __init__(self, agent: object, tg: TelegramIntegration) -> None:
        self._agent = agent
        self._tg = tg
        # Map Telegram chat_id → LangGraph thread_id for conversation continuity.
        self._threads: dict[int, str] = {}
        # Per-chat lock — prevents concurrent streams to the same thread which
        # causes ClosedResourceError on the langgraph server.
        self._locks: dict[int, asyncio.Lock] = {}
        # Per-chat active mode. "default" = normal FDWA agent.
        self._modes: dict[int, str] = {}
        # Per-chat pending mode confirmation: chat_id → mode name awaiting /yes
        self._pending_mode: dict[int, str] = {}
        # Per-chat pending interrupt: chat_id → Future resolved when user answers
        # an ask_user question from the agent.
        self._pending_interrupts: dict[int, asyncio.Future] = {}
        # Per-chat cancellation flag — set by /stop, checked in _run_agent loop.
        self._stop_flags: dict[int, bool] = {}
        # Per-chat running asyncio.Task — cancel()able on /stop.
        self._running_tasks: dict[int, asyncio.Task] = {}

    def _get_thread_id(self, chat_id: int) -> str:
        if chat_id not in self._threads:
            self._threads[chat_id] = generate_thread_id()
        return self._threads[chat_id]

    def _get_mode(self, chat_id: int) -> str:
        return self._modes.get(chat_id, "default")

    def reset_thread(self, chat_id: int) -> None:
        """Start a fresh conversation for *chat_id* on the next message."""
        self._threads.pop(chat_id, None)

    def call_after_refresh(self, fn: object) -> None:  # type: ignore[override]
        """Immediately invoke *fn* — no UI refresh needed in headless mode."""
        if callable(fn):
            fn()

    def _handle_mode_command(self, text: str, chat_id: int) -> str | None:
        """Handle /mode command. Returns a reply string, or None if not a mode command."""
        stripped = text.strip()

        # /yes or /confirm — confirm a pending mode switch
        if stripped in ("/yes", "/confirm", "yes", "confirm"):
            pending = self._pending_mode.pop(chat_id, None)
            if pending:
                self._modes[chat_id] = pending
                emoji, desc = _MODE_REGISTRY.get(pending, ("🎭", pending))
                return (
                    f"✅ Switched to <b>{emoji} {desc}</b> mode.\n\n"
                    f"This session will now use the {pending} persona. "
                    f"Type <code>/mode default</code> to reset."
                )
            return None  # no pending switch, treat as regular message

        # /no or /cancel — cancel pending mode switch
        if stripped in ("/no", "/cancel", "no", "cancel"):
            if self._pending_mode.pop(chat_id, None):
                return "❌ Mode switch cancelled. Staying in current mode."
            return None

        if not stripped.lower().startswith("/mode"):
            return None

        parts = stripped.split(maxsplit=1)
        arg = parts[1].strip().lower() if len(parts) > 1 else ""

        # /mode (no arg) — list modes
        if not arg:
            current = self._get_mode(chat_id)
            return _build_mode_list_message(current)

        # /mode default — reset immediately (no confirmation needed)
        if arg == "default":
            self._modes.pop(chat_id, None)
            self._pending_mode.pop(chat_id, None)
            return "✅ Reset to default FDWA agent mode."

        # /mode <unknown>
        if arg not in _MODE_REGISTRY:
            known = ", ".join(f"<code>{k}</code>" for k in _MODE_REGISTRY)
            return f"❓ Unknown mode <code>{arg}</code>.\nAvailable: {known}"

        # Valid mode — ask for confirmation (human in the loop)
        emoji, desc = _MODE_REGISTRY[arg]
        self._pending_mode[chat_id] = arg
        current = self._get_mode(chat_id)
        cur_emoji, cur_desc = _MODE_REGISTRY.get(current, ("🤖", current))
        return (
            f"⚠️ Switch agent mode?\n\n"
            f"From: {cur_emoji} <b>{cur_desc}</b>\n"
            f"To:   {emoji} <b>{desc}</b>\n\n"
            f"This will add <b>{arg}</b> mode instructions to your messages for this session.\n\n"
            f"Reply <code>/yes</code> to confirm or <code>/no</code> to cancel."
        )

    async def _ask_user_in_telegram(
        self,
        ask_request: dict,
        chat_id: int,
    ) -> dict:
        """Send an ask_user question to Telegram and wait for the user's answer.

        Sends an inline keyboard for multiple_choice questions, plain text for
        free-form.  Resolves when the user replies or clicks a button (or times
        out after 5 minutes).

        Returns a resume payload dict: ``{"status": "answered", "answers": [...]}``.
        """
        questions: list = ask_request.get("questions", [])
        if not questions:
            return {"status": "cancelled"}

        q = questions[0]
        question_text = q.get("question", "?")
        q_type = q.get("type", "text")
        raw_choices = q.get("choices", [])

        html = f"❓ <b>Agent needs your input:</b>\n\n<i>{question_text}</i>"
        if len(questions) > 1:
            html += f"\n\n<i>({len(questions) - 1} follow-up question(s) after this)</i>"

        if q_type == "multiple_choice" and raw_choices:
            choice_labels = [
                c.get("value", str(c)) if isinstance(c, dict) else str(c)
                for c in raw_choices
            ]
            html += "\n\n<i>Tap a button or type your own answer:</i>"
            await asyncio.to_thread(
                self._tg.send_question_with_keyboard, chat_id, html, choice_labels
            )
        else:
            html += "\n\n<i>Type your answer and send it:</i>"
            await asyncio.to_thread(self._tg.send_message_html, chat_id, html)

        # Register future — resolved by next message or callback_query from this chat
        loop = asyncio.get_running_loop()
        answer_future: asyncio.Future = loop.create_future()
        self._pending_interrupts[chat_id] = answer_future

        try:
            answer_text = await asyncio.wait_for(asyncio.shield(answer_future), timeout=300.0)
        except asyncio.TimeoutError:
            self._pending_interrupts.pop(chat_id, None)
            await asyncio.to_thread(
                self._tg.send_message_html,
                chat_id,
                "⏱️ <i>No answer received — continuing without input.</i>",
            )
            return {"status": "cancelled"}

        # Build answers list: first answer covers Q1, rest "(not answered)"
        answers = [answer_text] + ["(not answered)" for _ in questions[1:]]
        return {"status": "answered", "answers": answers}

    async def _handle_external_message(
        self,
        message: str,
        source: str = "telegram",  # noqa: ARG002
        telegram_chat_id: int | None = None,
    ) -> None:
        """Process one Telegram message through the agent and reply.

        Interrupt-aware: if the agent pauses with an ask_user question, the
        question is sent to Telegram and the agent resumes once the user replies.
        The per-chat lock is held across the full turn (including any interrupt
        round-trips) but the pending-interrupt check runs *before* the lock so
        incoming answers can resolve the waiting future without deadlocking.
        """
        if telegram_chat_id is None:
            return

        # ── Answer to a pending ask_user interrupt ──────────────────────────
        # Must run BEFORE acquiring the lock — the lock is held while waiting
        # for this future, so checking here avoids a deadlock.
        if telegram_chat_id in self._pending_interrupts:
            future = self._pending_interrupts.pop(telegram_chat_id)
            if not future.done():
                future.set_result(message)
            return

        # ── /stop / /cancel — kill running task ─────────────────────────────
        if message.strip().lower() in ("/stop", "/cancel", "stop", "cancel"):
            self._stop_flags[telegram_chat_id] = True
            task = self._running_tasks.pop(telegram_chat_id, None)
            if task and not task.done():
                task.cancel()
                self._tg.send_message_html(
                    telegram_chat_id,
                    "🛑 <b>Stopped.</b> Task cancelled. Send a new message to start fresh.",
                )
            else:
                self._tg.send_message_html(
                    telegram_chat_id, "Nothing running right now."
                )
            return

        # ── /mode commands ───────────────────────────────────────────────────
        mode_reply = self._handle_mode_command(message, telegram_chat_id)
        if mode_reply is not None:
            self._tg.send_message_html(telegram_chat_id, mode_reply)
            return

        if telegram_chat_id not in self._locks:
            self._locks[telegram_chat_id] = asyncio.Lock()

        async with self._locks[telegram_chat_id]:
            thread_id = self._get_thread_id(telegram_chat_id)
            active_mode = self._get_mode(telegram_chat_id)
            logger.info(
                "chat_id=%d thread=%s mode=%s: %.80s",
                telegram_chat_id, thread_id, active_mode, message,
            )

            agent_message = _inject_mode_context(message, active_mode)

            # Show typing indicator + placeholder message immediately
            await self._tg._start_thinking(telegram_chat_id)

            # ── Step-log progress callback ───────────────────────────────────
            # Real-time dashboard: numbered steps with elapsed time, edited
            # into the placeholder message so the user sees EXACTLY what the
            # agent is doing — not "Working…" placeholders.
            import time as _time
            _steps: list[tuple[float, str]] = []  # (elapsed_secs, status)
            _MAX_STEPS = 12
            _last_edit = 0.0
            _last_heartbeat = _time.monotonic()
            _start_time = _time.monotonic()
            _MIN_EDIT_INTERVAL = 1.0   # Telegram rate limit: ~1 edit/s per message
            _HEARTBEAT_EVERY = 4.0
            _step_counter = 0

            async def _progress(status: str) -> None:
                nonlocal _last_edit, _last_heartbeat, _step_counter
                if not status:
                    return
                now = _time.monotonic()
                _last_heartbeat = now
                if now - _last_edit < _MIN_EDIT_INTERVAL:
                    return
                _last_edit = now
                elapsed = now - _start_time
                # Append step only when it differs from the last one
                last_status = _steps[-1][1] if _steps else ""
                if status != last_status:
                    _step_counter += 1
                    _steps.append((elapsed, status))
                    if len(_steps) > _MAX_STEPS:
                        _steps.pop(0)
                mid = self._tg._pending_placeholders.get(telegram_chat_id)
                if not mid:
                    return
                # Build a real dashboard with step numbers and elapsed time
                total_elapsed = int(now - _start_time)
                mins, secs = divmod(total_elapsed, 60)
                time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
                lines = []
                for step_elapsed, step_text in _steps:
                    se = int(step_elapsed)
                    sm, ss = divmod(se, 60)
                    ts = f"{sm}:{ss:02d}" if sm else f"0:{ss:02d}"
                    # Escape HTML in step text
                    safe_text = (step_text
                                 .replace("&", "&amp;")
                                 .replace("<", "&lt;")
                                 .replace(">", "&gt;"))
                    lines.append(f"<code>[{ts}]</code> {safe_text}")
                log_block = "\n".join(lines)
                header = (
                    f"⚡ <b>Agent working</b>  •  "
                    f"Step {_step_counter}  •  {time_str}"
                )
                full_text = f"{header}\n\n{log_block}"
                try:
                    # Prefer sendMessageDraft (Bot API 9.5+) for smooth native
                    # streaming. Falls back to editMessageText automatically.
                    drafted = await asyncio.to_thread(
                        self._tg.send_message_draft,
                        telegram_chat_id,
                        full_text,
                    )
                    if not drafted:
                        await asyncio.to_thread(
                            self._tg.edit_message,
                            telegram_chat_id,
                            mid,
                            full_text,
                        )
                except Exception:
                    pass

            # Seed the log with the active mode badge (if any)
            if active_mode != "default":
                emoji, _ = _MODE_REGISTRY.get(active_mode, ("🎭", active_mode))
                await _progress(f"{emoji} {active_mode.title()} mode active")

            # ── Quick Chat routing ─────────────────────────────────────────
            # Simple two-path decision:
            #   • Quick Chat can handle it → Musa responds instantly
            #     (if Musa decides to hand off, it says so naturally and
            #      the full agent picks up automatically)
            #   • Quick Chat can't handle it → full agent directly
            #
            # No decision prompts, no "how would you like me to handle
            # this?" keyboards. Musa talks or the agent works. Clean.
            _use_quick = (
                active_mode == "default"
                and should_use_quick_chat(message)
            )

            if _use_quick:
                logger.info("Quick Chat routing (model=%s): %.60s", CHAT_MODEL, message)
                await _progress("💬 Quick Chat…")

                quick_reply, handoff = await handle_quick_chat(message)
                if not handoff and quick_reply:
                    logger.info("Quick Chat reply to chat_id=%d: %.80s", telegram_chat_id, quick_reply)
                    self._tg.deliver_reply(telegram_chat_id, quick_reply)
                    return
                # Musa handed off → show its message, then full agent continues
                logger.info("Quick Chat HANDOFF → full agent for chat_id=%d", telegram_chat_id)
                await _progress(quick_reply or "🔄 On it…")
            else:
                await _progress("🤖 Starting…")

            # ── Full agent run with interrupt loop ───────────────────────────
            from langgraph.types import Command as _LGCommand  # noqa: PLC0415

            self._stop_flags.pop(telegram_chat_id, None)  # clear any stale stop flag

            async def _run_full_agent() -> str:
                """Inner coroutine — wrapped in a Task so /stop can cancel it."""
                nonlocal response, interrupts  # type: ignore[misc]
                agent_inp: object = {"messages": [{"role": "user", "content": agent_message}]}
                resp, intrs = await _run_agent(
                    self._agent, agent_inp, thread_id, progress_cb=_progress,
                )

                _MAX_INTERRUPT_ROUNDS = 10
                for _round in range(_MAX_INTERRUPT_ROUNDS):
                    if not intrs or self._stop_flags.get(telegram_chat_id):
                        break
                    resume_data: dict = {}
                    for intr in intrs:
                        intr_value = getattr(intr, "value", None)
                        intr_id = getattr(intr, "id", f"intr_{_round}")
                        if isinstance(intr_value, dict) and intr_value.get("type") == "ask_user":
                            await _progress("❓ Waiting for your answer…")
                            answer = await self._ask_user_in_telegram(intr_value, telegram_chat_id)
                            resume_data[intr_id] = answer
                        else:
                            logger.warning(
                                "Unhandled interrupt type (chat_id=%d): %r",
                                telegram_chat_id, intr_value,
                            )
                            resume_data[intr_id] = {"status": "cancelled"}

                    await _progress("🔄 Resuming…")
                    resp, intrs = await _run_agent(
                        self._agent,
                        _LGCommand(resume=resume_data),
                        thread_id,
                        progress_cb=_progress,
                    )
                return resp

            response = ""
            interrupts = []
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(_run_full_agent())
                self._running_tasks[telegram_chat_id] = task
                response = await task
            except asyncio.CancelledError:
                logger.info("Task cancelled for chat_id=%d", telegram_chat_id)
                response = "🛑 Task stopped."
            except Exception as exc:  # noqa: BLE001
                logger.exception("Agent error (chat_id=%d)", telegram_chat_id)
                # Show the real error so you can diagnose — not a generic "sorry"
                err_short = str(exc)[:300]
                response = f"❌ <b>Error:</b> <code>{err_short}</code>\n\nSend <code>/reset</code> to start fresh."
            finally:
                self._running_tasks.pop(telegram_chat_id, None)

        # Deliver outside the lock
        logger.info("Agent reply to chat_id=%d: %.80s", telegram_chat_id, response)
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

    async def _handle_callback_query(self, query: dict) -> None:
        """Handle an inline keyboard button press (callback_query update).

        If the originating chat has a pending ask_user interrupt, resolves the
        waiting Future with the button's callback_data so the agent can resume.
        Always answers the callback query to dismiss Telegram's loading spinner.
        """
        query_id: str = query.get("id", "")
        data: str = query.get("data", "")
        chat_id: int | None = (
            query.get("message", {}).get("chat", {}).get("id")
        )

        # Dismiss the loading spinner on the button immediately
        await asyncio.to_thread(self._tg.answer_callback_query, query_id)

        if chat_id and chat_id in self._app._pending_interrupts:
            future = self._app._pending_interrupts.pop(chat_id)
            if not future.done():
                future.set_result(data)
                logger.info(
                    "Callback answer for chat_id=%d: %r", chat_id, data[:60]
                )

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
            agent_input = {"messages": [{"role": "user", "content": text}]}
            response, _ = await _run_agent(self._app._agent, agent_input, thread_id)

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
        """Download a file, ingest it, then let the agent handle next steps.

        Flow:
        1. Download file from Telegram
        2. Ingest into knowledge base (Mem0 + AstraDB agent_documents)
        3. Extract a text preview
        4. Pass a rich message to the agent so it can ask the user what
           to do: summarize, convert to Google Doc, upload to Dropbox, etc.
        """
        doc = msg.get("document", {})
        file_id = doc.get("file_id", "")
        filename = doc.get("file_name", "upload")
        mime = doc.get("mime_type", "")
        file_size = doc.get("file_size", 0)

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

            # Ingest into knowledge base in background thread
            summary = await asyncio.to_thread(_run_ingest_sync, str(local_path))

            # Extract a text preview for the agent
            preview = ""
            try:
                if ext == ".pdf":
                    import pypdf
                    with open(str(local_path), "rb") as f:
                        reader = pypdf.PdfReader(f)
                        pages_text = []
                        for i, page in enumerate(reader.pages[:3]):
                            t = (page.extract_text() or "").strip()
                            if t:
                                pages_text.append(t[:500])
                        preview = "\n---\n".join(pages_text)
                        page_count = len(reader.pages)
                else:
                    text = local_path.read_text(encoding="utf-8", errors="ignore")
                    preview = text[:1500]
                    page_count = 1
            except Exception:
                preview = "(could not extract preview)"
                page_count = 0

            # Build a rich agent message with file context
            size_kb = file_size / 1024 if file_size else len(dl.content) / 1024
            agent_msg = (
                f"The user just uploaded a document: **{filename}**\n"
                f"- Type: {ext.upper().lstrip('.')} ({mime})\n"
                f"- Size: {size_kb:.1f} KB, {page_count} page(s)\n"
                f"- Status: Successfully ingested into knowledge base ({summary.splitlines()[-1] if summary.strip() else 'stored'})\n"
                f"- File saved at: {local_path}\n\n"
                f"**Document preview (first ~1500 chars):**\n```\n{preview[:1500]}\n```\n\n"
                f"Ask the user what they'd like to do with this document. Suggest options like:\n"
                f"1. **Summarize** the document\n"
                f"2. **Extract key data** (tables, contacts, dates, etc.)\n"
                f"3. **Upload to Google Docs** (use GOOGLEDOCS_CREATE_NEW_GOOGLE_DOC)\n"
                f"4. **Upload to Google Sheets** (if it's tabular data)\n"
                f"5. **Save to Dropbox** (use DROPBOX_UPLOAD_FILE_TO_DROPBOX)\n"
                f"6. **Search/query** the content\n"
                f"7. **Convert to another format**\n\n"
                f"Present these as options and wait for the user's choice. "
                f"After completing any action, return the link/result to the user."
            )

            # Route through the normal agent flow (not bypass it)
            caption = msg.get("caption", "").strip()
            if caption:
                agent_msg = f"User message: \"{caption}\"\n\n{agent_msg}"

            # Create a synthetic update so handle_telegram_update routes it to agent
            synthetic_update = {
                "message": {
                    "chat": {"id": chat_id},
                    "from": msg.get("from", {}),
                    "text": agent_msg,
                    "message_id": msg.get("message_id", 0),
                }
            }
            self._tg.handle_telegram_update(synthetic_update)

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
                params: dict = {
                    "timeout": 55,
                    "allowed_updates": ["message", "callback_query"],
                }
                if self._tg.offset is not None:
                    params["offset"] = self._tg.offset

                data = await asyncio.to_thread(self._tg._fetch_updates, params)

                for update in data.get("result", []):
                    self._tg.offset = update["update_id"] + 1
                    try:
                        # ── Inline keyboard button press ─────────────────────
                        if "callback_query" in update:
                            await self._handle_callback_query(update["callback_query"])
                            continue

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
                if should_use_quick_chat(message) and CHAT_MODEL != MODEL:
                    response, handoff = await handle_quick_chat(message)
                    if not handoff:
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
        enable_skills=True,
        no_mcp=True,
    ) as (agent, _server):
        bot = HeadlessBot(agent=agent)
        await asyncio.gather(
            bot.run(),
            start_api_server(agent),
        )


if __name__ == "__main__":
    asyncio.run(main())
