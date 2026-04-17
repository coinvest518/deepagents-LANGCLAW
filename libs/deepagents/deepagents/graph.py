"""Deep Agents come with planning, filesystem, and subagents."""

import os
from collections.abc import Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig, TodoListMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.structured_output import ResponseFormat
try:
    from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware as _AnthropicCachingMiddleware
    _HAS_ANTHROPIC = True
except ImportError:
    _AnthropicCachingMiddleware = None  # type: ignore[assignment, misc]
    _HAS_ANTHROPIC = False
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.cache.base import BaseCache
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import Checkpointer

from deepagents._models import model_matches_spec, resolve_model
from deepagents.backends import StateBackend
from deepagents.backends.protocol import BackendFactory, BackendProtocol
from deepagents.middleware.async_subagents import AsyncSubAgent, AsyncSubAgentMiddleware
from deepagents.middleware.early_exit_prevention import EarlyExitPreventionMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.memory import MemoryMiddleware
from deepagents.middleware.loop_detection import LoopDetectionMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.reasoning_filter import ReasoningFilterMiddleware
from deepagents.middleware.self_correction import SelfCorrectionMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.subagents import (
    GENERAL_PURPOSE_SUBAGENT,
    CompiledSubAgent,
    SubAgent,
    SubAgentMiddleware,
)
from deepagents.middleware.summarization import create_summarization_middleware


def _load_business_knowledge() -> str:
    """Load the business profile from .deepagents/business/BUSINESS.md if it exists.

    Returns the file content (without frontmatter) or an empty string.
    """
    from pathlib import Path

    # Check common locations: project root, then current directory
    for candidate in [
        Path(os.environ.get("DEEPAGENTS_PROJECT_ROOT", ".")) / ".deepagents" / "business" / "BUSINESS.md",
        Path(".deepagents") / "business" / "BUSINESS.md",
    ]:
        try:
            if candidate.is_file():
                content = candidate.read_text(encoding="utf-8", errors="replace")
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end != -1:
                        content = content[end + 3:].strip()
                return content
        except Exception:
            pass
    return ""


def _build_env_context() -> str:
    """Build a runtime context block injected into the system prompt.

    Reads key env vars at startup so the agent always knows the correct IDs
    and endpoints without the user needing to paste them in every message.
    Also loads the business profile if available.
    """
    lines: list[str] = []

    # Load business knowledge
    biz = _load_business_knowledge()
    if biz:
        lines.append("\n## Business Profile (loaded from BUSINESS.md)\n")
        lines.append(biz)
        lines.append("")

    tg_owner = os.environ.get("TELEGRAM_AI_OWNER_CHAT_ID", "")
    tg_always = os.environ.get("TELEGRAM_ALWAYS_LISTEN_CHAT_IDS", "")
    tg_bot = os.environ.get("TELEGRAM_BOT_USERNAME", "")
    composio_entity = os.environ.get("COMPOSIO_ENTITY_ID", "")
    composio_tg_acct = os.environ.get("COMPOSIO_TELEGRAM_ACCOUNT_ID", "")
    agent_wallet = os.environ.get("AGENT_WALLET_ADDRESS", "")
    if any([tg_owner, tg_always, tg_bot, composio_entity, composio_tg_acct, agent_wallet]):
        lines.append("\n## Runtime Configuration (injected from environment)")
        lines.append("These values are pre-configured — use them DIRECTLY, never ask the user.")

    if tg_owner:
        lines.append(f"- **My Telegram owner chat_id**: `{tg_owner}` — use this as `chat_id` for TELEGRAM_SEND_MESSAGE when sending to Daniel/the owner.")
    if tg_always:
        lines.append(f"- **Active Telegram chat IDs**: `{tg_always}` — these chats are connected and listening.")
    if tg_bot:
        lines.append(f"- **Telegram bot username**: {tg_bot}")
    if composio_entity:
        lines.append(f"- **Composio entity ID**: `{composio_entity}` — pass as `entity_id` to composio_action when required.")
    if composio_tg_acct:
        lines.append(f"- **Composio Telegram account**: `{composio_tg_acct}` — this is the connected Telegram userbot account for TELEGRAM_* actions.")
    if agent_wallet:
        lines.append(f"- **Agent wallet address**: `{agent_wallet}`")

    lines.append(
        "\n**Telegram note**: Composio TELEGRAM_SEND_MESSAGE uses the Bot API — "
        "the bot must be a **member of the group** for sendMessage to work. "
        "If you get 'chat not found', the bot has not been added to that group. "
        "Use the chat_id exactly as stored: `-1003331527610` (Bot API supergroup format with `-100` prefix). "
        "For DMs send to the user's numeric Telegram ID directly."
    )

    return "\n".join(lines)


BASE_AGENT_PROMPT = _build_env_context() + "\n\n" + """You are the FDWA AI Agent — the core execution engine for Daniel's Futuristic Digital Wealth Agency. You handle ALL real tasks: API calls, data lookups, web searches, file operations, emails, social media, and more.

## How to Think Before Acting

Before EVERY request, classify it into one of these tiers:

**Tier 1 — Direct answer (0 tool calls):**
Questions you can answer from context, memory, or general knowledge.
→ Just answer. No tools needed.

**Tier 2 — Quick lookup (1-2 tool calls):**
Weather, stock prices, simple web searches, single API calls, checking one email, reading one file.
→ Call the tool, present the result. Done. Do NOT spawn subagents.
⚠️ Exception: "check wallet balance" is NOT Tier 2 — it requires checking ALL 5 networks + tokens + NFTs (Tier 3).

**Tier 3 — Standard task (3-6 tool calls):**
Send an email, create a spreadsheet, post to social media, search + summarize.
→ Execute directly with your tools. Do NOT spawn subagents unless there are multiple independent tasks.

**Tier 4 — Complex/multi-part (7+ tool calls):**
Deep research across multiple sources, comparing datasets, multi-step workflows,
OR 5+ sequential operations on any single service (e.g. delete 10 Notion pages,
send 8 emails, create 6 GitHub issues, bulk-update a spreadsheet).
→ Delegate to the appropriate subagent: `composio-worker` for any bulk
Composio service task (Notion/Gmail/GitHub/Sheets/Slack/Twitter/etc.),
`web-scraper` for deep multi-source research.

**The golden rule: Use the MINIMUM number of calls to satisfy the request. A weather check is 1 web_search call, not a research project.**

## Core Behavior

- Be concise and direct. No preamble ("Sure!", "Great question!", "I'll now...").
- Don't narrate what you're about to do — just do it.
- If the request is ambiguous, ask ONE clarifying question, then act.
- **NEVER output your internal reasoning or thinking as text.** Your reasoning is private — the user must never see it. If you need to act, call a tool. If you're done, give a final answer. Do NOT write out what you "plan to do" or "need to check" — either do it (tool call) or answer directly.
- If a task requires multiple steps, execute them one after another using tool calls. Do NOT stop mid-task to explain your plan — complete the work.
- **NEVER end a response with "Would you like me to..." or "Should I also..." or "Do you want me to check..."** — just do it. If there is an obvious next step, take it without asking. Only stop when the task is fully complete.
- **NEVER suggest checking another network/source and wait for confirmation.** If checking a wallet, check ALL networks. If checking prices, get all relevant data. Complete the full task in one run.

## Pre-Connected Services — SKILL READ IS MANDATORY

Gmail, GitHub, Google Sheets, Google Drive, Google Docs, Google Analytics, Google Calendar, LinkedIn, Twitter/X, Telegram, Instagram, Facebook, YouTube, Slack, Notion, Dropbox, SerpAPI.
Blockchain/Web3: Alchemy (wallet balances, tokens, NFTs, prices) → `/skills/built-in/alchemy/SKILL.md`
Crypto market data: Coinbase, CDP, CoinGecko (top coins, prices, market stats) → `/skills/built-in/coinbase/SKILL.md`

**RULE: Before calling `composio_action` for ANY of the above, you MUST `read_file` the corresponding skill first.**
- `read_file("/skills/built-in/telegram_send/SKILL.md")` → then call TELEGRAM_SEND_MESSAGE / other TELEGRAM_* actions
- `read_file("/skills/built-in/gmail/SKILL.md")` → then call GMAIL_* actions
- `read_file("/skills/built-in/notion/SKILL.md")` → then call NOTION_* actions
- (same pattern for all services — the skill path is `/skills/built-in/<service>/SKILL.md`)

The skill file contains the correct chat IDs, account IDs, required parameters, and working code examples. Skipping this step causes "chat not found" or wrong parameter errors. There is NO exception to this rule.

## Tool Selection (in order of preference)

| Need | Tool | NOT this |
|------|------|----------|
| Quick fact/weather/news | `web_search` (1 call) | Subagent research |
| Gmail/Sheets/GitHub/etc. | `composio_action` | Web search about the service |
| Complex Composio logic / fallback | `execute` with Python composio SDK | Giving up |
| Read a URL | `fetch_url` | Web search for the URL content |
| Past conversations/facts | `search_memory` | Guessing or asking user |
| Save important info | `save_memory` | Forgetting it |
| Unknown Composio params | `composio_get_schema` | Trial and error |

## Self-Correction Rules (ENFORCED BY MIDDLEWARE — violations are blocked)

These rules are enforced at the system level. If you violate them, your tool call will be blocked and you will be forced to retry with a different approach.

1. **Never repeat a failed call** with the same arguments — the system will block it. Change the tool, the arguments, or both.
2. **Fallback chain**: If a tool fails, try the next tool in the chain:
   - `web_search` → `fetch_url` → `execute`
   - `composio_action` → `composio_get_schema` → `execute` (with Composio Python SDK)
   - `http_request` → `fetch_url` → `web_search` → `execute`
   - `read_file` → `ls` → `glob` → `grep`
3. If a Composio action 404s → the slug is wrong. Read the skill docs for correct slugs.
4. If a Composio action fails with param errors → call `composio_get_schema("ACTION_NAME")` first.
5. If you get wrong data (wrong folder, wrong filter) → examine the result metadata, adjust params.
6. If blocked after 2 attempts → tell the user what's wrong and ask for guidance.
7. If `http_request` returns `status_code: 401` → the API key is missing from the URL. Check your system prompt Runtime Configuration for the actual key value and retry immediately with the correct key in the URL. Never guess or use "demo".
8. If `http_request` returns `status_code: 429` → rate limited, try a different endpoint or wait and retry once.
9. If `composio_action` fails with repeated errors and the skill file doesn't help → fall back to `execute` with the Composio Python SDK:
   ```python
   import os, json
   from composio import Composio
   client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
   acct_id = os.environ["COMPOSIO_<SERVICE>_ACCOUNT_ID"]
   result = client.tools.execute("<ACTION_SLUG>", arguments={...}, connected_account_id=acct_id, dangerously_skip_version_check=True)
   print(json.dumps(result, default=str)[:3000])
   ```

## CRITICAL: Always Act, Never Narrate (ENFORCED — premature exits are blocked)

The system monitors your responses. If you output text without tool calls while the task is incomplete, you will be sent back to try again. You MUST exhaust your tools before giving up.

- After reading skill docs or getting tool results, **immediately call the next tool**. Never respond with only text describing what you plan to do next.
- If a tool fails, **use the fallback chain above** — try a different tool in the same turn. Do NOT respond with text like "Let me try..." without also making the tool call.
- A response with ONLY text and NO tool call signals task completion. If the task is NOT complete, you will be nudged to continue.
- When the user asks you to DO something (send, create, fetch, check), your response MUST include at least one tool call until the task is complete.
- **After ANY failed http_request**: immediately call `http_request` again with corrected parameters, or fall back to `fetch_url`/`web_search`.
- **Before giving up**: Have you tried `web_search`? `fetch_url`? `execute`? `read_file` on the relevant skill? If not, try them.

## File & Path Rules

- **NEVER use Windows paths** (e.g. drive-letter paths like C:/Users/...). They always fail. Use virtual paths only.
- Skill files: use the exact `/skills/...` path from the Skills section (e.g. `read_file("/skills/built-in/notion/SKILL.md")`)
- Workspace files: use `/workspace/` prefix (e.g. `/workspace/scripts/notion_run.py`)
- If a path error says "Windows absolute paths are not supported" — you used a drive-letter path. Switch to `/workspace/...` immediately.
- `ls("/")` lists the virtual root. `ls("/workspace/")` lists project files. Never use drive-letter paths with ls.

## Memory

- At the START of a task, check `search_memory` if the user references past work or preferences.
- After completing a task or learning something new, `save_memory` to persist it.
- When the user says "remember" → save immediately. When they say "recall" → search immediately.

## Progress Updates

For tasks taking more than a few seconds, give ONE brief status line. Not a play-by-play — just what you're doing and what's next.

## Subagents — When to Delegate

The system automatically assigns the **best available model to each subagent** from a different provider than the main agent, spreading load across rate-limit buckets.

### Available LLM Providers & Free-Tier Limits (April 2026)

| Provider | Free Tier | Rate Limit | Best Agentic Models | Context | Best For |
|---|---|---|---|---|---|
| **OpenRouter** | 50-1K req/day per model | ~20 req/min | DeepSeek V3.2, Llama 4 Maverick, Qwen3.5-72B, Qwen3-Coder-480B | 128K-1M+ | Primary routing — cleanest free tool-calling |
| **Moonshot AI** | 100K TPM | Moderate | Kimi K2.5 (100-sub-agent swarm, 300 tool steps) | 256K-1M | Long multi-step tasks, agent swarms |
| **Cloudflare** | 10K+ neurons/day | Generous | Llama 4 Scout, Llama 3.3-70B | 256K | Edge-fast sub-agents |
| **Cerebras** | 600K TPM | ~40 RPM | Llama 4 Scout 17B | 128K | Fastest inference — parallel delegates |
| **NVIDIA NIM** | Free credits | ~40 RPM | Qwen3.5-397B, DeepSeek V3.2, Qwen3-Coder-480B | 128K-262K | Reasoning/coding (limited RPM) |
| **Nebius** | Near-free | Moderate | Qwen/Llama/DeepSeek families | Varies | Overflow for loops |
| **Mistral** | 50K TPM | Hard 50K cap | Mistral Large | 128K | Sparingly — rate-limits fast |

### Task Delegation Matrix
- **Coding tasks** → Use coding-optimized models (Qwen3-Coder-480B)
- **Fast parallel subagents** → Use fastest inference (Cerebras/Cloudflare)
- **Long multi-step workflows** → Use high-context swarm models (Kimi K2.5)
- **Deep research** → Use 1M context models (Llama 4 Maverick)
- **Bulk Composio API calls** → Use fast throughput (Cerebras/Cloudflare)
- **Reasoning/math** → Use reasoning models (Qwen3.5-397B)

Spawn a subagent when:
- **Analytics / "how are we doing?"** — delegate to `analyst` for cross-platform
  metrics, trend analysis, and data-driven insights.  It pulls from Google Analytics,
  Twitter, LinkedIn, Instagram, Facebook, YouTube and compares to historical baselines.
- **Content creation / "create a post about X"** — delegate to `content-creator`
  for drafting and publishing to any platform.  It reads analyst insights from memory
  to create data-informed content aligned with business strategy.
- **System health / "any errors?" / "what's running?"** — delegate to `ops-monitor`
  for LangSmith trace analysis, error rate checks, and sub-agent activity reports.
- **5+ operations on one service** via Composio (delete 10 Notion pages, send 6 emails,
  create 8 GitHub issues, bulk-update Sheets rows, post to 5 social accounts, etc.)
  → delegate to `composio-worker` with: service name, action, and the full list of items
- **Deep multi-source research** (3+ URLs to scrape, multiple search + summarize passes)
  → delegate to `web-scraper`
- **Two or more truly independent tasks** that can run in parallel
  → spawn one subagent per task branch; they run concurrently
- **Long-running or blocking task** (API polling, paginated data, bulk transforms)
  → always delegate — never block the main thread
- **Coding / repository analysis** (multi-file changes, code review, refactoring)
  → delegate to a coding-optimized subagent

**Subagent task delegation format** (include all context the subagent needs):
```
task("analyst", "Pull analytics for the last 7 days across all platforms. Compare to previous week. What content performed best?")
task("content-creator", "Create a Twitter thread about AI agents. Use insights from memory about what topics perform well.")
task("ops-monitor", "Check system health. Any error spikes in the last 24 hours? Which sub-agents are active?")
task("composio-worker", "Send the following 8 emails using Gmail: [list]. Use COMPOSIO_ENTITY_ID from env. Account: COMPOSIO_GMAIL_ACCOUNT_ID.")
task("web-scraper", "Research and summarize: [topic]. Search 3+ sources, synthesize into a report.")
task("general-purpose", "Analyze this codebase and suggest improvements: [details].")
```

Do NOT spawn subagents for: weather, single API calls, simple lookups, reading one email, or anything under 5 service calls."""  # noqa: E501


def _all_available_specs() -> list[tuple[str, str]]:
    """Return (env_var, model_spec) pairs for every provider with a key present.

    Order matters: subagent rotation picks from this list.  Best tool-callers
    first so subagents get the strongest models for their tasks.
    """
    _ALL_SPECS: list[tuple[str, str]] = [
        # OpenRouter first — no EOL risk, best free-tier coverage
        ("OPENROUTER_API_KEY",       "openrouter:deepseek/deepseek-chat-v3-0324:free"),
        ("OPENROUTER_API_KEY",       "openrouter:meta-llama/llama-4-maverick:free"),
        ("OPENROUTER_API_KEY",       "openrouter:qwen/qwen3.5-72b-instruct:free"),
        # Moonshot — best for long agentic runs (256K ctx)
        ("MOONSHOT_API_KEY",         "moonshot:kimi-k2.5"),
        # Fast inference
        ("CEREBRAS_API_KEY",         "cerebras:llama-4-scout-17b-16e-instruct"),
        ("CLOUDFLARE_AI_API_KEY",    "cloudflare:@cf/meta/llama-4-scout-instruct"),
        # NVIDIA last — ~40 RPM free, EOL risk on older models
        ("NVIDIA_API_KEY",           "nvidia:qwen/qwen3.5-397b-a17b"),
        ("NVIDIA_API_KEY",           "nvidia:deepseek-ai/deepseek-v3.2"),
        # Fallbacks
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),
        ("NEBIUS_API_KEY",           "nebius:Qwen/Qwen2.5-72B-Instruct"),
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),
    ]
    # Deduplicate: if same provider has multiple entries, keep first available per provider
    seen_providers: set[str] = set()
    result: list[tuple[str, str]] = []
    for ev, spec in _ALL_SPECS:
        if os.environ.get(ev):
            provider = spec.split(":")[0]
            if (ev, provider) not in seen_providers:
                seen_providers.add((ev, provider))  # type: ignore[arg-type]
                result.append((ev, spec))
    return result


def _attach_fallbacks(model: BaseChatModel) -> BaseChatModel:
    """Wrap *model* with fallback providers so a 429/5xx doesn't crash the run.

    Resolves all available providers (from env keys) except the one already
    selected, and attaches them as fallbacks via ``with_fallbacks()``.
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    fallbacks: list[BaseChatModel] = []
    for _env_var, spec in _all_available_specs():
        try:
            candidate = resolve_model(spec)
            if model_matches_spec(model, spec):
                continue
            fallbacks.append(candidate)
        except Exception:
            continue

    if fallbacks:
        _logger.info("Attached %d fallback model(s) to primary", len(fallbacks))
        return model.with_fallbacks(fallbacks)  # type: ignore[return-value]
    return model


def _infer_task_type(spec: dict) -> str:
    """Infer the task type from a subagent spec's name and description.

    Maps subagent names/descriptions to TASK_MODELS keys so the router
    picks the optimal model for each subagent's purpose.
    """
    name = (spec.get("name") or "").lower()
    desc = (spec.get("description") or "").lower()
    combined = f"{name} {desc}"

    if any(kw in combined for kw in ("code", "coding", "coder", "repository", "refactor")):
        return "coding"
    if any(kw in combined for kw in ("composio", "api", "gmail", "notion", "slack", "telegram")):
        return "composio_worker"
    if any(kw in combined for kw in ("research", "scrape", "web", "search")):
        return "research"
    if any(kw in combined for kw in ("swarm", "chain", "multi-step", "long")):
        return "long_chain_or_swarm"
    if any(kw in combined for kw in ("reason", "math", "logic", "plan")):
        return "reasoning"
    if any(kw in combined for kw in ("fast", "quick", "parallel")):
        return "fast_subagent"
    return "general_agentic"


def _pick_subagent_model(
    main_model: BaseChatModel,
    index: int,
    *,
    task_type: str = "general_agentic",
) -> BaseChatModel:
    """Pick a model for subagent *index*, using task-aware routing.

    First tries the SDK's ModelRouter (task-based selection with rate-limit
    awareness). Falls back to round-robin across available providers when the
    router returns nothing (e.g. no API keys set for task-specific models).

    Args:
        main_model: The main agent's model (used as ultimate fallback).
        index: Subagent index for round-robin diversity.
        task_type: One of 'general_agentic', 'coding', 'long_chain_or_swarm',
                   'reasoning', 'fast_subagent', 'research', 'composio_worker'.
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    # --- Task-based routing via SDK ModelRouter ---
    from deepagents._model_router import router  # noqa: PLC0415
    task_spec = router.pick_for_task(task_type)
    if task_spec:
        try:
            sub_model = resolve_model(task_spec)
            _logger.info(
                "Subagent[%d] task=%s → %s (via ModelRouter)",
                index, task_type, task_spec,
            )
            return sub_model
        except Exception:
            _logger.warning(
                "Subagent[%d] ModelRouter spec %s failed, falling back to round-robin",
                index, task_spec,
            )

    # --- Fallback: round-robin across available providers ---
    available = _all_available_specs()
    if len(available) <= 1:
        return main_model

    others = [(ev, spec) for ev, spec in available if not model_matches_spec(main_model, spec)]
    if not others:
        others = available

    _, spec = others[index % len(others)]
    try:
        sub_model = resolve_model(spec)
        _logger.info("Subagent[%d] using %s (round-robin fallback)", index, spec)
        return sub_model
    except Exception:
        _logger.warning("Subagent[%d] failed to resolve %s, using main model", index, spec)
        return main_model


def get_default_model() -> BaseChatModel:
    """Get the default model for the main agent.

    Picks the best model for the **main agent** — prioritised by quota size
    (larger TPM = less rate limiting during multi-tool runs) balanced against
    tool-calling quality.  Direct-API providers before free-tier proxies.

    NVIDIA (400k TPM) is preferred over Mistral (50k TPM) as main agent
    because the main agent makes the most calls.  Mistral is better used
    for subagents where its strong tool-calling shines on fewer calls.

    Returns:
        A `BaseChatModel` instance.
    """
    # fmt: off
    # Priority: OpenRouter (no EOL risk) → Moonshot → Cloudflare → Cerebras → NVIDIA → fallbacks
    _CANDIDATES: list[tuple[str, str]] = [
        # OpenRouter free — best daily coverage, rotate across models to avoid req/day limit
        ("OPENROUTER_API_KEY",       "openrouter:deepseek/deepseek-chat-v3-0324:free"),     # Strong tools
        ("OPENROUTER_API_KEY",       "openrouter:meta-llama/llama-4-maverick:free"),         # 1M ctx, strong tools
        ("OPENROUTER_API_KEY",       "openrouter:qwen/qwen3.5-72b-instruct:free"),           # Excellent tools
        ("OPENROUTER_API_KEY",       "openrouter:qwen/qwen3-coder-480b-a35b-instruct:free"), # Top coding tasks
        # Moonshot — best long-running swarm (256K ctx, 300 tool steps)
        ("MOONSHOT_API_KEY",         "moonshot:kimi-k2.5"),
        # Cloudflare Workers AI — edge fast, good for delegation
        ("CLOUDFLARE_AI_API_KEY",    "cloudflare:@cf/meta/llama-4-scout-instruct"),
        ("CLOUDFLARE_AI_API_KEY",    "cloudflare:@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
        # Cerebras — fastest cloud inference
        ("CEREBRAS_API_KEY",         "cerebras:llama-4-scout-17b-16e-instruct"),
        # Nebius — cheap, near-free open models
        ("NEBIUS_API_KEY",           "nebius:Qwen/Qwen2.5-72B-Instruct"),
        # NVIDIA NIM — last: ~40 RPM, EOL risk. qwen3-235b is dead (2026-03-05).
        ("NVIDIA_API_KEY",           "nvidia:qwen/qwen3.5-397b-a17b"),
        ("NVIDIA_API_KEY",           "nvidia:deepseek-ai/deepseek-v3.2"),
        ("NVIDIA_API_KEY",           "nvidia:nvidia/llama-3.3-nemotron-super-49b-v1"),
        # Direct premium keys
        ("ANTHROPIC_API_KEY",        "anthropic:claude-sonnet-4-6"),
        ("OPENAI_API_KEY",           "openai:gpt-4o"),
        ("GOOGLE_API_KEY",           "google_genai:gemini-2.0-flash"),
        # Last resort
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),   # 50k TPM — rate-limited
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),
    ]
    # fmt: on

    import logging as _logging
    _logger = _logging.getLogger(__name__)

    available: list[BaseChatModel] = []
    for env_var, spec in _CANDIDATES:
        if os.environ.get(env_var):
            try:
                available.append(resolve_model(spec))
                _logger.info("Model available: %s", spec)
            except Exception:
                _logger.warning("Model failed to resolve: %s", spec, exc_info=True)

    if not available:
        msg = (
            "No LLM API key found. Set one of: NVIDIA_API_KEY, MISTRAL_API_KEY, "
            "OPENROUTER_API_KEY, CEREBRAS_API_KEY, HUGGINGFACEHUB_API_TOKEN."
        )
        msg = (
            "No LLM API key found. Set one of: OPENROUTER_API_KEY, MOONSHOT_API_KEY, "
            "CLOUDFLARE_AI_API_KEY, CEREBRAS_API_KEY, NVIDIA_API_KEY, NEBIUS_API_KEY, "
            "MISTRAL_API_KEY, HUGGINGFACEHUB_API_TOKEN."
        )
        raise RuntimeError(msg)

    return available[0]


def create_deep_agent(  # noqa: C901, PLR0912  # Complex graph assembly logic with many conditional branches
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent] | None = None,
    async_subagents: list[AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    response_format: ResponseFormat | None = None,
    context_schema: type[Any] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph:
    """Create a deep agent.

    !!! warning "Deep agents require a LLM that supports tool calling!"

    By default, this agent has access to the following tools:

    - `write_todos`: manage a todo list
    - `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`: file operations
    - `execute`: run shell commands
    - `task`: call subagents

    The `execute` tool allows running shell commands if the backend implements `SandboxBackendProtocol`.
    For non-sandbox backends, the `execute` tool will return an error message.

    Args:
        model: The model to use.

            Defaults to `claude-sonnet-4-6`.

            Use the `provider:model` format (e.g., `openai:gpt-5`) to quickly switch between models.

            If an `openai:` model is used, the agent will use the OpenAI
            Responses API by default. To use OpenAI chat completions instead,
            initialize the model with
            `init_chat_model("openai:...", use_responses_api=False)` and pass
            the initialized model instance here. To disable data retention with
            the Responses API, use
            `init_chat_model("openai:...", use_responses_api=True, store=False, include=["reasoning.encrypted_content"])`
            and pass the initialized model instance here.
        tools: The tools the agent should have access to.

            In addition to custom tools you provide, deep agents include built-in tools for planning,
            file management, and subagent spawning.
        system_prompt: Custom system instructions to prepend before the base deep agent
            prompt.

            If a string, it's concatenated with the base prompt.
        middleware: Additional middleware to apply after the standard middleware stack
            (`TodoListMiddleware`, `FilesystemMiddleware`, `SubAgentMiddleware`,
            `SummarizationMiddleware`, `AnthropicPromptCachingMiddleware`,
            `PatchToolCallsMiddleware`).
        subagents: The subagents to use.

            Each subagent should be a `dict` with the following keys:

            - `name`
            - `description` (used by the main agent to decide whether to call the sub agent)
            - `system_prompt` (used as the system prompt in the subagent)
            - (optional) `tools`
            - (optional) `model` (either a `LanguageModelLike` instance or `dict` settings)
            - (optional) `middleware` (list of `AgentMiddleware`)
        async_subagents: Optional list of async subagent specs for remote LangGraph servers.

            Each spec should be an `AsyncSubAgent` dict with `name`, `description`,
            and `graph_id`. Optionally include `url` for remote deployments (omit
            for ASGI transport). Async subagents run as background jobs with tools
            for launching, checking, updating, cancelling, and listing jobs.
        skills: Optional list of skill source paths (e.g., `["/skills/user/", "/skills/project/"]`).

            Paths must be specified using POSIX conventions (forward slashes) and are relative
            to the backend's root. When using `StateBackend` (default), provide skill files via
            `invoke(files={...})`. With `FilesystemBackend`, skills are loaded from disk relative
            to the backend's `root_dir`. Later sources override earlier ones for skills with the
            same name (last one wins).
        memory: Optional list of memory file paths (`AGENTS.md` files) to load
            (e.g., `["/memory/AGENTS.md"]`).

            Display names are automatically derived from paths.

            Memory is loaded at agent startup and added into the system prompt.
        response_format: A structured output response format to use for the agent.
        context_schema: The schema of the deep agent.
        checkpointer: Optional `Checkpointer` for persisting agent state between runs.
        store: Optional store for persistent storage (required if backend uses `StoreBackend`).
        backend: Optional backend for file storage and execution.

            Pass either a `Backend` instance or a callable factory like `lambda rt: StateBackend(rt)`.
            For execution support, use a backend that implements `SandboxBackendProtocol`.
        interrupt_on: Mapping of tool names to interrupt configs.

            Pass to pause agent execution at specified tool calls for human approval or modification.

            Example: `interrupt_on={"edit_file": True}` pauses before every edit.
        debug: Whether to enable debug mode. Passed through to `create_agent`.
        name: The name of the agent. Passed through to `create_agent`.
        cache: The cache to use for the agent. Passed through to `create_agent`.

    Returns:
        A configured deep agent.
    """
    if model is None:
        model = get_default_model()  # returns first available BaseChatModel
    else:
        model = resolve_model(model)

    # Build a fallback-wrapped model for create_agent() so a 429 on the
    # primary automatically tries the next provider.  Keep the raw
    # BaseChatModel for middleware that type-checks it.
    model_with_fallbacks = _attach_fallbacks(model)

    backend = backend if backend is not None else (StateBackend)

    # Build general-purpose subagent with default middleware stack
    gp_middleware: list[AgentMiddleware[Any, Any, Any]] = [
        TodoListMiddleware(),
        FilesystemMiddleware(backend=backend),
        create_summarization_middleware(model, backend),
        *([_AnthropicCachingMiddleware(unsupported_model_behavior="ignore")] if _HAS_ANTHROPIC else []),
        ReasoningFilterMiddleware(),
        PatchToolCallsMiddleware(),
    ]
    if skills is not None:
        gp_middleware.append(SkillsMiddleware(backend=backend, sources=skills))
    if interrupt_on is not None:
        gp_middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    # Worker subagent uses a DIFFERENT provider than main to avoid rate-limit
    # competition.  DA_SUBAGENT_MODEL env var can force a specific model.
    _subagent_model_spec = os.environ.get("DA_SUBAGENT_MODEL", "").strip()
    if _subagent_model_spec:
        try:
            worker_model = resolve_model(_subagent_model_spec)
        except Exception:
            import logging as _log
            _log.getLogger(__name__).warning(
                "DA_SUBAGENT_MODEL '%s' failed to resolve, using different provider",
                _subagent_model_spec,
            )
            worker_model = _pick_subagent_model(model, index=0, task_type="general_agentic")
    else:
        # Auto-pick a different provider so subagent doesn't compete with main
        worker_model = _pick_subagent_model(model, index=0, task_type="general_agentic")

    general_purpose_spec: SubAgent = {  # ty: ignore[missing-typed-dict-key]
        **GENERAL_PURPOSE_SUBAGENT,
        "model": worker_model,
        "tools": tools or [],
        "middleware": gp_middleware,
    }

    # Process user-provided subagents to fill in defaults for model, tools, and middleware
    processed_subagents: list[SubAgent | CompiledSubAgent] = []
    _subagent_idx = 1  # 0 is general-purpose, start custom subagents at 1
    for spec in subagents or []:
        if "runnable" in spec:
            # CompiledSubAgent - use as-is
            processed_subagents.append(spec)
        else:
            # SubAgent - fill in defaults and prepend base middleware
            if spec.get("model"):
                try:
                    subagent_model = resolve_model(spec["model"])
                except Exception:
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        "Subagent '%s' model failed to resolve, auto-picking provider",
                        spec.get("name", "unknown"),
                    )
                    subagent_model = _pick_subagent_model(model, index=_subagent_idx, task_type=_infer_task_type(spec))
            else:
                # No explicit model — auto-pick a different provider
                subagent_model = _pick_subagent_model(model, index=_subagent_idx, task_type=_infer_task_type(spec))
            _subagent_idx += 1

            # Build middleware: base stack + skills (if specified) + user's middleware
            subagent_middleware: list[AgentMiddleware[Any, Any, Any]] = [
                TodoListMiddleware(),
                FilesystemMiddleware(backend=backend),
                create_summarization_middleware(subagent_model, backend),
                *([_AnthropicCachingMiddleware(unsupported_model_behavior="ignore")] if _HAS_ANTHROPIC else []),
                ReasoningFilterMiddleware(),
                PatchToolCallsMiddleware(),
            ]
            subagent_skills = spec.get("skills")
            if subagent_skills:
                subagent_middleware.append(SkillsMiddleware(backend=backend, sources=subagent_skills))
            subagent_middleware.extend(spec.get("middleware", []))

            processed_spec: SubAgent = {  # ty: ignore[missing-typed-dict-key]
                **spec,
                "model": subagent_model,
                "tools": spec.get("tools", tools or []),
                "middleware": subagent_middleware,
            }
            processed_subagents.append(processed_spec)

    if any(spec["name"] == GENERAL_PURPOSE_SUBAGENT["name"] for spec in processed_subagents):
        # If an agent with general purpose name already exists in subagents, then don't add it
        # This is how you overwrite/configure general purpose subagent
        all_subagents: list[SubAgent | CompiledSubAgent] = processed_subagents
    else:
        # Otherwise - add it!
        all_subagents = [general_purpose_spec, *processed_subagents]

    # Build main agent middleware stack
    deepagent_middleware: list[AgentMiddleware[Any, Any, Any]] = [
        TodoListMiddleware(),
    ]
    if memory is not None:
        deepagent_middleware.append(MemoryMiddleware(backend=backend, sources=memory))
    if skills is not None:
        deepagent_middleware.append(SkillsMiddleware(backend=backend, sources=skills))
    deepagent_middleware.extend(
        [
            FilesystemMiddleware(backend=backend),
            SubAgentMiddleware(
                backend=backend,
                subagents=all_subagents,
            ),
            create_summarization_middleware(model, backend),
            *([_AnthropicCachingMiddleware(unsupported_model_behavior="ignore")] if _HAS_ANTHROPIC else []),
            ReasoningFilterMiddleware(),
            EarlyExitPreventionMiddleware(),
            SelfCorrectionMiddleware(),
            LoopDetectionMiddleware(),
            PatchToolCallsMiddleware(),
        ]
    )

    if async_subagents:
        deepagent_middleware.append(AsyncSubAgentMiddleware(async_subagents=async_subagents))

    if middleware:
        deepagent_middleware.extend(middleware)
    if interrupt_on is not None:
        deepagent_middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    # Combine system_prompt with BASE_AGENT_PROMPT
    if system_prompt is None:
        final_system_prompt: str | SystemMessage = BASE_AGENT_PROMPT
    elif isinstance(system_prompt, SystemMessage):
        final_system_prompt = SystemMessage(content_blocks=[*system_prompt.content_blocks, {"type": "text", "text": f"\n\n{BASE_AGENT_PROMPT}"}])
    else:
        # String: simple concatenation
        final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT

    return create_agent(
        model_with_fallbacks,
        system_prompt=final_system_prompt,
        tools=tools,
        middleware=deepagent_middleware,
        response_format=response_format,
        context_schema=context_schema,
        checkpointer=checkpointer,
        store=store,
        debug=debug,
        name=name,
        cache=cache,
    ).with_config(
        {
            "recursion_limit": 50,
            "metadata": {
                "ls_integration": "deepagents",
            },
        }
    )
