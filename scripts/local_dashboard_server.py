"""Local dashboard server — runs the full agent using the local venv + .env.

Usage:
    .venv/Scripts/python scripts/local_dashboard_server.py

This starts the SAME full agent that Render/Telegram use, but locally:
  - Loads .env for all API keys
  - Uses server_session() to spin up the LangGraph agent (all tools, memory, skills)
  - Runs the HTTP API on port 10000 (same /health, /chat, /history endpoints)
  - NO Telegram polling — just the dashboard API

Point dashboard/.env.local at:
    RENDER_AGENT_URL=http://localhost:10000
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
for _lib in ("libs/cli", "libs/deepagents", "deploy"):
    _p = str(_REPO / _lib)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_REPO / ".env", override=False)
except ImportError:
    pass

# Set DA_SERVER_DB_PATH — required by the LangGraph checkpointer
_db_path = Path.home() / ".deepagents" / "sessions.db"
_db_path.parent.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DA_SERVER_DB_PATH", str(_db_path))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("local_dashboard_server")

# ---------------------------------------------------------------------------
# Import after path + env setup
# ---------------------------------------------------------------------------
from deepagents_cli.server_manager import server_session  # noqa: E402

# Quick Chat removed from dashboard — all messages go straight to the main
# agent (same flow as the CLI).  Musa exists as a sub-agent inside the graph;
# the old bypass layer is no longer used here.

# Model selection (same as telegram_bot.py)
try:
    from model_router import router
    _MODEL = router.pick("main")
    logger.info("Model router picked: %s", _MODEL)
except Exception:
    _MODEL = None

if not _MODEL:
    # Fallback: priority order matches model_router.py _MAIN_MODELS
    _FALLBACKS = [
        ("OPENROUTER_API_KEY",       "openrouter:deepseek/deepseek-chat-v3-0324:free"),
        ("OPENROUTER_API_KEY",       "openrouter:meta-llama/llama-4-maverick:free"),
        ("OPENROUTER_API_KEY",       "openrouter:qwen/qwen3.5-72b-instruct:free"),
        ("MOONSHOT_API_KEY",         "moonshot:kimi-k2.5"),
        ("CLOUDFLARE_AI_API_KEY",    "cloudflare:@cf/meta/llama-4-scout-instruct"),
        ("CEREBRAS_API_KEY",         "cerebras:llama-4-scout-17b-16e-instruct"),
        ("NVIDIA_API_KEY",           "nvidia:qwen/qwen3.5-397b-a17b"),
        ("NVIDIA_API_KEY",           "nvidia:deepseek-ai/deepseek-v3.2"),
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),
        ("NEBIUS_API_KEY",           "nebius:Qwen/Qwen2.5-72B-Instruct"),
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),
    ]
    for key, spec in _FALLBACKS:
        if os.environ.get(key):
            _MODEL = spec
            break

if not _MODEL:
    logger.error("No model API keys found in .env — cannot start agent")
    sys.exit(1)


AGENT_ID = os.environ.get("DA_AGENT_ID", "default")
API_PORT = int(os.environ.get("PORT", "10000"))

# Sandbox: "none" runs the agent in this process (shell tools disabled for safety).
# "daytona" runs filesystem/shell tools inside an ephemeral remote sandbox —
# safe to enable shell there because the agent can't touch the host.
_SANDBOX = (os.environ.get("USE_SANDBOX") or "none").strip().lower() or "none"
_ENABLE_SHELL = _SANDBOX != "none"
if _SANDBOX == "daytona" and not os.environ.get("DAYTONA_API_KEY"):
    logger.error("USE_SANDBOX=daytona but DAYTONA_API_KEY is not set")
    sys.exit(1)
logger.info("Sandbox: %s (shell=%s)", _SANDBOX, _ENABLE_SHELL)


def _to_uuid(raw: str) -> str:
    """Convert any string to a stable UUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


async def start_api_server(agent: object) -> None:
    """HTTP server with same endpoints as Render backend."""
    from aiohttp import web

    _api_locks: dict[str, asyncio.Lock] = {}

    # Runtime-configurable flags for the local dashboard server. Kept
    # in-memory so the CLI/server process is not permanently mutated by UI
    # actions during local development. These can be read/updated via the
    # /settings endpoints implemented below.
    runtime_config: dict = {
        "auto_approve": os.environ.get("DA_AUTO_APPROVE", "1").lower() in {"1", "true", "yes"},
    }

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "model": _MODEL, "agent": AGENT_ID, "mode": "local"})

    async def chat(request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = (data.get("message") or "").strip()
        raw_thread = (data.get("thread_id") or "dashboard-default").strip()
        thread_id = _to_uuid(raw_thread)

        if not message:
            return web.json_response({"error": "message is required"}, status=400)

        if thread_id not in _api_locks:
            _api_locks[thread_id] = asyncio.Lock()

        task_id = str(uuid.uuid4())

        async with _api_locks[thread_id]:
            try:
                # Everything goes through the real LangGraph agent.
                config = {"configurable": {"thread_id": thread_id}}
                agent_input = {"messages": [{"role": "user", "content": message}]}

                async for chunk in agent.astream(agent_input, config=config):
                    pass  # drain stream

                state = await agent.aget_state(config)
                if state is None:
                    return web.json_response({
                        "response": "No response received.",
                        "thread_id": thread_id,
                        "task_id": task_id,
                    })

                messages = getattr(state, "values", {}).get("messages", [])
                response_text = "No response received."

                # Pass 1: clean AI reply without tool_calls
                for msg in reversed(messages):
                    if getattr(msg, "tool_calls", None):
                        continue
                    # Detect reasoning content (Nemotron puts it in both places)
                    _ak = getattr(msg, "additional_kwargs", None) or {}
                    _reasoning = _ak.get("reasoning_content") or _ak.get("reasoning") or ""
                    # Prefer content_blocks to filter out thinking tokens
                    blocks = getattr(msg, "content_blocks", None)
                    if blocks:
                        text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text" and b.get("text", "").strip() != _reasoning.strip()]
                        combined = " ".join(t for t in text_parts if t.strip())
                        if combined.strip():
                            response_text = combined.strip()
                            break
                    else:
                        content = getattr(msg, "content", None)
                        if isinstance(content, list):
                            text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip() != _reasoning.strip()]
                            combined = " ".join(t for t in text_parts if t.strip())
                            if combined.strip():
                                response_text = combined.strip()
                                break
                        elif isinstance(content, str) and content.strip():
                            # Skip if content IS the reasoning
                            if _reasoning and content.strip() == _reasoning.strip():
                                continue
                            response_text = content.strip()
                            break

                # Pass 2: synthesize from tool results when agent only called tools without replying
                if response_text == "No response received.":
                    tool_names: list[str] = []
                    tool_results: list[str] = []
                    for msg in messages:
                        if getattr(msg, "type", "") in ("tool", "ToolMessage"):
                            tc_name = getattr(msg, "name", "tool") or "tool"
                            tc_content = str(getattr(msg, "content", "") or "")
                            tool_names.append(tc_name)
                            tool_results.append(f"{tc_name}: {tc_content[:200]}")
                    if tool_results:
                        unique_tools = list(dict.fromkeys(tool_names))
                        response_text = (
                            f"Done. Used {', '.join(unique_tools)}.\n"
                            + "\n".join(tool_results[-3:])
                        )

                # Pass 3: any non-empty content as last resort
                if response_text == "No response received.":
                    for msg in reversed(messages):
                        content = getattr(msg, "content", None)
                        if isinstance(content, str) and content.strip():
                            response_text = content.strip()
                            break

                return web.json_response({
                    "response": response_text,
                    "thread_id": thread_id,
                    "task_id": task_id,
                })

            except Exception as exc:
                logger.exception("HTTP /chat error")
                return web.json_response({
                    "error": str(exc),
                    "thread_id": thread_id,
                    "task_id": task_id,
                    "status": "incomplete",
                }, status=500)

    async def history_handler(request: web.Request) -> web.Response:
        raw_thread = request.match_info.get("thread_id", "")
        thread_id = _to_uuid(raw_thread) if raw_thread else ""
        if not thread_id:
            return web.json_response({"error": "thread_id required"}, status=400)
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = await agent.aget_state(config)
            raw_msgs = [] if state is None else (getattr(state, "values", {}).get("messages", []) or [])
            messages = []
            for msg in raw_msgs:
                role = getattr(msg, "type", "")
                content = getattr(msg, "content", "")
                tools = getattr(msg, "tool_calls", None)
                if isinstance(content, list):
                    # Only include "text" type blocks, skip thinking/reasoning
                    content = " ".join(
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in content
                        if not isinstance(b, dict) or b.get("type", "text") == "text"
                    )
                if role in ("human", "HumanMessage"):
                    messages.append({"role": "user", "text": str(content)})
                elif role in ("ai", "AIMessage") and not tools:
                    messages.append({"role": "agent", "text": str(content)})
            return web.json_response({"messages": messages, "thread_id": thread_id})
        except Exception as exc:
            logger.exception("HTTP /history error")
            return web.json_response({"messages": [], "thread_id": thread_id})

    app = web.Application()
    # Settings endpoints: return current runtime flags, environment-derived
    # configuration, discovered MCP configs, and available skill folders.
    async def settings_get(request: web.Request) -> web.Response:
        try:
            from deepagents_cli.config import settings as cli_settings
            from deepagents_cli.mcp_tools import discover_mcp_configs

            built_in = []
            try:
                bi = cli_settings.get_built_in_skills_dir()
                if bi.exists():
                    built_in = [p.name for p in bi.iterdir() if p.exists()]
            except Exception:
                built_in = []

            project_skills = []
            try:
                ps = cli_settings.get_project_skills_dir()
                if ps and ps.exists():
                    project_skills = [p.name for p in ps.iterdir() if p.exists()]
            except Exception:
                project_skills = []

            user_skills = []
            try:
                us = cli_settings.get_user_skills_dir(AGENT_ID)
                if us.exists():
                    user_skills = [p.name for p in us.iterdir() if p.exists()]
            except Exception:
                user_skills = []

            mcp_paths = []
            try:
                found = discover_mcp_configs()
                mcp_paths = [str(p) for p in found]
            except Exception:
                mcp_paths = []

            payload = {
                "agent_model": _MODEL,
                "auto_approve": runtime_config.get("auto_approve", False),
                "agent_api_url": os.environ.get("AGENT_API_URL"),
                "ollama": {
                    "base_url": os.environ.get("OLLAMA_BASE_URL"),
                    "model": os.environ.get("OLLAMA_MODEL"),
                },
                "langsmith": {
                    "configured": bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")),
                    "project": os.environ.get("LANGSMITH_PROJECT"),
                },
                "mem0": bool(os.environ.get("MEM0_API_KEY")),
                "astra": bool(os.environ.get("ASTRA_DB_API_KEY")),
                "composio": bool(os.environ.get("COMPOSIO_API_KEY")),
                "mcp_configs": mcp_paths,
                "skills": {
                    "built_in": built_in,
                    "project": project_skills,
                    "user": user_skills,
                },
            }
            resp = web.json_response(payload)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp
        except Exception as exc:
            logger.exception("Failed to build settings response")
            resp = web.json_response({"error": str(exc)}, status=500)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp

    async def settings_post(request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        result = {"updated": {}}
        # Update runtime flags
        if "auto_approve" in data:
            runtime_config["auto_approve"] = bool(data["auto_approve"])
            result["updated"]["auto_approve"] = runtime_config["auto_approve"]

        # Optionally reload environment-based settings from .env
        if data.get("reload_env"):
            try:
                from deepagents_cli.config import settings as cli_settings
                changes = cli_settings.reload_from_environment()
                result["env_reload"] = changes
            except Exception as exc:
                result["env_reload_error"] = str(exc)

        resp = web.json_response({"runtime_config": runtime_config, **result})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    # CORS preflight handler for /settings
    async def settings_options(request: web.Request) -> web.Response:
        resp = web.Response(text="ok")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    # ------------------------------------------------------------------
    # SSE streaming endpoint — mirrors what the CLI shows in real time
    # ------------------------------------------------------------------
    async def chat_stream(request: web.Request) -> web.StreamResponse:
        """Server-Sent Events streaming for the dashboard.

        Event types:
          status     — spinner state (thinking, tool:name, null)
          text       — streaming text chunk from the AI
          tool_start — tool call began {id, name, args}
          tool_end   — tool call finished {id, status, output}
          done       — stream complete {response}
          error      — something broke {message}
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = (data.get("message") or "").strip()
        raw_thread = (data.get("thread_id") or "dashboard-default").strip()
        thread_id = _to_uuid(raw_thread)

        if not message:
            return web.json_response({"error": "message is required"}, status=400)

        if thread_id not in _api_locks:
            _api_locks[thread_id] = asyncio.Lock()

        resp = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )
        await resp.prepare(request)

        async def _send(event: str, payload: object) -> None:
            line = f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
            await resp.write(line.encode("utf-8"))

        task_id = str(uuid.uuid4())

        async with _api_locks[thread_id]:
            try:
                # ── Main agent (same flow as CLI — no Quick Chat bypass) ─────
                await _send("status", {"state": "thinking", "model": _MODEL})

                config = {"configurable": {"thread_id": thread_id}}
                agent_input = {"messages": [{"role": "user", "content": message}]}
                pending_tools: dict[str, dict] = {}
                tool_buffers: dict = {}
                full_text = ""
                _seen_content: set = set()  # deduplicate AI message content across stream modes

                # Helper: process messages from update dicts (for updates mode)
                async def _process_updates_messages(msgs: list) -> None:
                    nonlocal full_text
                    for msg in msgs:
                        msg_type = getattr(msg, "type", "") or (msg.get("type", "") if isinstance(msg, dict) else "")

                        # Tool calls from AI message
                        tc_list = getattr(msg, "tool_calls", None) or (msg.get("tool_calls") if isinstance(msg, dict) else None)
                        if tc_list:
                            for tc in tc_list:
                                tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                                tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                                tc_id = tc.get("id", tc_name) if isinstance(tc, dict) else getattr(tc, "id", tc_name)
                                if tc_name and tc_id not in pending_tools:
                                    pending_tools[tc_id] = {"name": tc_name, "args": tc_args}
                                    await _send("tool_start", {"id": tc_id, "name": tc_name, "args": tc_args})
                                    await _send("status", {"state": f"tool:{tc_name}"})

                        # Tool results
                        if msg_type in ("tool", "ToolMessage"):
                            tool_name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
                            tool_id = getattr(msg, "tool_call_id", None) or (msg.get("tool_call_id") if isinstance(msg, dict) else None)
                            content = getattr(msg, "content", "") or (msg.get("content", "") if isinstance(msg, dict) else "")
                            status_val = getattr(msg, "status", "success") or "success"
                            await _send("tool_end", {
                                "id": tool_id or tool_name or "unknown",
                                "name": tool_name or "tool",
                                "status": status_val,
                                "output": str(content)[:500],
                            })
                            pending_tools.pop(tool_id, None)
                            if not pending_tools:
                                await _send("status", {"state": "thinking"})

                        # AI text content (not tool calls) — filter out thinking/reasoning
                        if msg_type in ("ai", "AIMessage") and not tc_list:
                            # NVIDIA Nemotron (and some other models) put reasoning
                            # into both content AND additional_kwargs.reasoning_content.
                            # If content matches the reasoning, skip it entirely.
                            _additional = getattr(msg, "additional_kwargs", None) or (msg.get("additional_kwargs") if isinstance(msg, dict) else None) or {}
                            _reasoning = _additional.get("reasoning_content") or _additional.get("reasoning") or ""

                            # Prefer structured content_blocks (like the CLI does)
                            blocks = getattr(msg, "content_blocks", None)
                            if blocks:
                                for block in blocks:
                                    if block.get("type") == "text":
                                        text = block.get("text", "")
                                        if text.strip() and text.strip() != _reasoning.strip():
                                            _h = hash(text.strip())
                                            if _h not in _seen_content:
                                                _seen_content.add(_h)
                                                await _send("text", {"content": text})
                                                full_text += text
                            else:
                                content = getattr(msg, "content", "") or (msg.get("content", "") if isinstance(msg, dict) else "")
                                # content can be a list of content block dicts
                                if isinstance(content, list):
                                    for block in content:
                                        if isinstance(block, dict) and block.get("type") == "text":
                                            text = block.get("text", "")
                                            if text.strip() and text.strip() != _reasoning.strip():
                                                _h = hash(text.strip())
                                                if _h not in _seen_content:
                                                    _seen_content.add(_h)
                                                    await _send("text", {"content": text})
                                                    full_text += text
                                elif isinstance(content, str) and content.strip():
                                    # Skip if content IS the reasoning (Nemotron leak)
                                    if _reasoning and content.strip() == _reasoning.strip():
                                        logger.debug("Skipping reasoning-as-content: %.100s", content.strip())
                                        continue
                                    import re as _re
                                    if _re.fullmatch(r'[a-zA-Z_]\w*\([^)]*\)', content.strip()):
                                        logger.warning("Skipping function-call-as-text: %.100s", content.strip())
                                        continue
                                    _h = hash(content.strip())
                                    if _h not in _seen_content:
                                        _seen_content.add(_h)
                                        await _send("text", {"content": content})
                                        full_text += content

                # Stream with both modes for 3-tuple format (like CLI).
                # If agent doesn't support stream_mode, fall back to default.
                try:
                    stream = agent.astream(
                        agent_input,
                        config=config,
                        stream_mode=["messages", "updates"],
                        subgraphs=True,
                    )
                    use_3tuple = True
                except TypeError:
                    # Older agent versions don't accept stream_mode
                    stream = agent.astream(agent_input, config=config)
                    use_3tuple = False

                async for chunk in stream:
                    # ── 3-tuple format: (namespace, mode, data) ──
                    if isinstance(chunk, tuple) and len(chunk) == 3:
                        namespace, mode, chunk_data = chunk

                        # Convert namespace to hashable tuple for filtering
                        ns_key = tuple(namespace) if namespace else ()
                        # CRITICAL: Only show main agent output (filter subagents)
                        is_main_agent = ns_key == ()

                        if mode == "updates" and isinstance(chunk_data, dict):
                            if "__interrupt__" in chunk_data:
                                await _send("status", {"state": "interrupted"})
                                break
                            # Only process main agent updates
                            if is_main_agent:
                                for node_name, node_data in chunk_data.items():
                                    if node_name.startswith("__") or not isinstance(node_data, dict):
                                        continue
                                    await _process_updates_messages(node_data.get("messages", []))

                        elif mode == "messages":
                            # Skip subagent outputs - only render main agent
                            if not is_main_agent:
                                continue

                            # Properly unpack (message, metadata) tuple
                            if not isinstance(chunk_data, tuple) or len(chunk_data) != 2:
                                logger.debug("Skipping non-2-tuple chunk_data: %s", type(chunk_data))
                                continue
                            message, metadata = chunk_data

                            msg_type = getattr(message, "type", "") or ""
                            logger.debug(
                                "Main agent message: type=%s has_content_blocks=%s",
                                msg_type,
                                hasattr(message, "content_blocks"),
                            )

                            # Text content is handled by "updates" mode via
                            # _process_updates_messages() — do NOT emit text
                            # here too or the response will be doubled.
                            #
                            # Only use "messages" mode for tool_call chunks that
                            # arrive before the updates-mode batch.
                            if hasattr(message, "content_blocks"):
                                for block in message.content_blocks:
                                    block_type = block.get("type")
                                    if block_type in {"tool_call_chunk", "tool_call"}:
                                        tc_name = block.get("name")
                                        tc_args = block.get("args")
                                        tc_id = block.get("id") or block.get("index")
                                        if tc_name and tc_id and tc_id not in pending_tools:
                                            if isinstance(tc_args, str):
                                                try:
                                                    tc_args = json.loads(tc_args)
                                                except json.JSONDecodeError:
                                                    continue
                                            if isinstance(tc_args, dict):
                                                pending_tools[tc_id] = {"name": tc_name, "args": tc_args}
                                                await _send("tool_start", {"id": tc_id, "name": tc_name, "args": tc_args})
                                                await _send("status", {"state": f"tool:{tc_name}"})
                            # else: text captured by updates mode

                            # Get message type for tool result detection
                            msg_type = getattr(message, "type", "") or ""

                            # Fully resolved tool calls (non-streaming, for backwards compat)
                            tc_list = getattr(message, "tool_calls", None) or []
                            for tc in tc_list:
                                tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                                tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                                tc_id = tc.get("id", tc_name) if isinstance(tc, dict) else getattr(tc, "id", tc_name)
                                if tc_name and tc_id not in pending_tools:
                                    pending_tools[tc_id] = {"name": tc_name, "args": tc_args}
                                    await _send("tool_start", {"id": tc_id, "name": tc_name, "args": tc_args})
                                    await _send("status", {"state": f"tool:{tc_name}"})

                            # Tool result in message stream
                            if msg_type in ("tool", "ToolMessage"):
                                tool_name = getattr(message, "name", None)
                                tool_id = getattr(message, "tool_call_id", None)
                                content_val = getattr(message, "content", "")
                                status_val = getattr(message, "status", "success") or "success"
                                await _send("tool_end", {
                                    "id": tool_id or tool_name or "unknown",
                                    "name": tool_name or "tool",
                                    "status": status_val,
                                    "output": str(content_val)[:500],
                                })
                                pending_tools.pop(tool_id, None)
                                if not pending_tools:
                                    await _send("status", {"state": "thinking"})

                    # ── Plain dict format (default stream_mode) ──
                    elif isinstance(chunk, dict):
                        if "__interrupt__" in chunk:
                            await _send("status", {"state": "interrupted"})
                            break
                        for node_name, node_data in chunk.items():
                            if node_name.startswith("__"):
                                continue
                            if isinstance(node_data, dict):
                                await _process_updates_messages(node_data.get("messages", []))

                # Final response from state if streaming didn't capture it
                if not full_text.strip():
                    state = await agent.aget_state(config)
                    if state:
                        msgs = getattr(state, "values", {}).get("messages", [])
                        logger.info("Extracting final response from %d messages in state", len(msgs))

                        # Helper: check if content is just reasoning
                        def _is_reasoning(m_obj, text_val):
                            ak = getattr(m_obj, "additional_kwargs", None) or {}
                            r = ak.get("reasoning_content") or ak.get("reasoning") or ""
                            return bool(r and text_val.strip() == r.strip())

                        # Pass 1: AI message without tool_calls (the real reply)
                        for m in reversed(msgs):
                            msg_type = getattr(m, "type", "")
                            has_tools = getattr(m, "tool_calls", None)
                            if msg_type not in ("ai", "AIMessage") or has_tools:
                                continue
                            blocks = getattr(m, "content_blocks", None)
                            if blocks:
                                text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text" and not _is_reasoning(m, b.get("text", ""))]
                                combined = " ".join(t for t in text_parts if t.strip())
                                if combined.strip():
                                    full_text = combined.strip()
                                    break
                            else:
                                c = getattr(m, "content", None)
                                if isinstance(c, list):
                                    text_parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text" and not _is_reasoning(m, b.get("text", ""))]
                                    combined = " ".join(t for t in text_parts if t.strip())
                                    if combined.strip():
                                        full_text = combined.strip()
                                        break
                                elif isinstance(c, str) and c.strip():
                                    if _is_reasoning(m, c):
                                        continue
                                    full_text = c.strip()
                                    break
                            if full_text.strip():
                                logger.info("Found final AI response: %.200s", full_text)

                        # Pass 2: synthesize from tool results when agent called tools but didn't reply
                        if not full_text.strip():
                            tool_results: list[str] = []
                            tool_names: list[str] = []
                            for m in msgs:
                                if getattr(m, "type", "") in ("tool", "ToolMessage"):
                                    tc_name = getattr(m, "name", "tool") or "tool"
                                    tc_content = str(getattr(m, "content", "") or "")
                                    tool_names.append(tc_name)
                                    tool_results.append(f"{tc_name}: {tc_content[:200]}")
                            if tool_results:
                                unique_tools = list(dict.fromkeys(tool_names))
                                full_text = (
                                    f"Done. Used {', '.join(unique_tools)}.\n"
                                    + "\n".join(tool_results[-3:])
                                )
                                logger.info("Synthesized response from %d tool results", len(tool_results))

                        # Pass 3: any non-empty content as last resort
                        if not full_text.strip():
                            for m in reversed(msgs):
                                blocks = getattr(m, "content_blocks", None)
                                if blocks:
                                    text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text" and not _is_reasoning(m, b.get("text", ""))]
                                    combined = " ".join(t for t in text_parts if t.strip())
                                    if combined.strip():
                                        full_text = combined.strip()
                                        break
                                else:
                                    c = getattr(m, "content", None)
                                    if isinstance(c, str) and c.strip() and not _is_reasoning(m, c):
                                        full_text = c.strip()
                                        break

                final = full_text.strip() or "No response received."
                logger.info("Final response for client: %.200s", final)
                await _send("done", {
                    "response": final,
                    "thread_id": thread_id,
                    "task_id": task_id,
                })

            except Exception as exc:
                logger.exception("SSE /chat/stream error")
                await _send("error", {"message": str(exc)})

        try:
            await resp.write_eof()
        except Exception:
            pass
        return resp


    app.router.add_get("/settings", settings_get)
    app.router.add_post("/settings", settings_post)
    app.router.add_options("/settings", settings_options)
    app.router.add_get("/health", health)
    app.router.add_post("/chat", chat)
    app.router.add_post("/chat/stream", chat_stream)
    app.router.add_get("/history/{thread_id}", history_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", API_PORT)
    await site.start()
    logger.info("Local dashboard server listening on http://localhost:%d", API_PORT)
    logger.info("  model      = %s", _MODEL)
    logger.info("  agent_id   = %s", AGENT_ID)

    while True:
        await asyncio.sleep(3600)


async def main() -> None:
    logger.info("Starting local dashboard server (no Telegram)...")

    async with server_session(
        assistant_id=AGENT_ID,
        model_name=_MODEL,
        auto_approve=True,
        sandbox_type=_SANDBOX,
        enable_shell=_ENABLE_SHELL,
        interactive=True,
        enable_memory=True,
        enable_skills=True,
        no_mcp=True,
    ) as (agent, _server):
        await start_api_server(agent)


if __name__ == "__main__":
    asyncio.run(main())
