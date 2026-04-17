# The Anatomy of the LANGCLAW Agent Harness

Full breakdown of how the agent runs, loops, stops, retries, and uses tools/skills — derived from the actual codebase.

---

## 1. The Main Agent Loop

The agent runs inside a **`while True` loop** in the interactive adapter (`libs/cli/deepagents_cli/textual_adapter.py:645`).

```
while True:
    async for chunk in agent.astream(...):
        # process chunks, detect HITL interrupts

    if interrupt_occurred and resume_payload:
        stream_input = Command(resume=resume_payload)  # reloop with user decision
    else:
        await dispatch_hook("task.complete", ...)
        break  # <-- NORMAL EXIT: agent decided it's done
```

### How the Agent Stops

The agent stops when **the model emits a text-only response with no tool calls**. That's it. The LangGraph `create_agent()` routes to `END` when the last `AIMessage` has no `tool_calls`. There is no explicit "I'm done" signal — the model just stops calling tools.

**This is the core problem:** If the model generates text like "I wasn't able to find that" without trying more tools, the loop ends. The harness does NOT force it to retry or try other tools.

### Exit Points

| Exit Point | File | What Triggers It |
|---|---|---|
| Normal completion (model stops calling tools) | `textual_adapter.py:1293` | `break` after `task.complete` hook |
| User rejects all HITL commands | `textual_adapter.py:1288` | `return turn_stats` |
| Ctrl+C / cancellation | `textual_adapter.py:1295` | `asyncio.CancelledError` |
| LangGraph recursion limit hit | `graph.py:727` | `recursion_limit: 50` steps |
| Loop detection hard stop | `loop_detection.py:156` | Tool calls stripped, agent forced to text-only |

### Non-Interactive Mode

In `non_interactive.py:655`, there's a simpler HITL loop with a hard cap:

```
_MAX_HITL_ITERATIONS = 50
while state.interrupt_occurred:
    iterations += 1
    if iterations > _MAX_HITL_ITERATIONS:
        raise HITLIterationLimitError(...)
```

---

## 2. The Middleware Stack

All middleware is assembled in `graph.py:674-702` and runs in order:

```python
deepagent_middleware = [
    TodoListMiddleware(),              # Track task progress
    MemoryMiddleware(),                # Search/save persistent memory
    SkillsMiddleware(),                # Inject skill metadata into prompt
    FilesystemMiddleware(),            # File read/write/edit/ls/glob/grep
    SubAgentMiddleware(),              # Spawn subagents for delegation
    SummarizationMiddleware(),         # Compact context when 85% full
    AnthropicCachingMiddleware(),      # (if Anthropic provider)
    ReasoningFilterMiddleware(),       # Catch models that output reasoning as text
    EarlyExitPreventionMiddleware(),   # Catch premature "giving up" exits [NEW]
    SelfCorrectionMiddleware(),        # Block repeated failed tool calls [NEW]
    LoopDetectionMiddleware(),         # Detect + break infinite tool loops
    PatchToolCallsMiddleware(),        # Fix malformed tool arguments
    AsyncSubAgentMiddleware(),         # Async subagent support
    HumanInTheLoopMiddleware(),        # Require user approval for dangerous ops
]
```

Each middleware has `before_agent` and/or `after_model` hooks that intercept the agent at different points.

### Middleware Execution Order (after_model)

The order matters. After the model generates a response, middleware fires in stack order:

1. **ReasoningFilterMiddleware** — catches "thinking out loud" responses (no tool calls, just reasoning text). Nudges model to act. Max 2 retries.
2. **EarlyExitPreventionMiddleware** — catches "giving up" responses where the agent hasn't tried enough tools yet. Lists untried tools and nudges. Max 2 retries.
3. **SelfCorrectionMiddleware** — catches repeated failed tool calls (same tool + same args that already errored). Blocks the call, suggests fallback tools. Max 3 corrections per tool.
4. **LoopDetectionMiddleware** — catches infinite loops of the SAME tool call. Soft warning at 3 exact / 10 name repeats, hard stop at 3 exact / 15 name repeats.
5. **PatchToolCallsMiddleware** — fixes malformed tool arguments (JSON strings that should be dicts/lists, null sentinels, etc.)

This creates a **layered defense**: reasoning filter → early exit prevention → self-correction → loop detection → arg patching.

---

## 3. Loop Detection — The Anti-Stuck Mechanism

**File:** `libs/deepagents/deepagents/middleware/loop_detection.py`

This is the main mechanism to prevent the agent from getting stuck calling the same tool forever. It has **three levels** with **soft warnings → hard stop escalation**:

### Level 1: Exact Loop (same tool + same args)

| Threshold | Action |
|---|---|
| 3 consecutive identical calls (`MAX_REPEATS_EXACT = 3`) | **Soft warning**: Injects `ToolMessage` saying "Loop detected, respond with what you have" |
| 3rd call (`_HARD_STOP_EXACT = 3`) | **Hard stop**: Strips ALL tool calls from AIMessage, forces text-only response → agent exits |

### Level 2: Name Loop (same tool, different args)

| Threshold | Action |
|---|---|
| 10 consecutive calls (`MAX_REPEATS_NAME = 10`) | **Soft warning**: Injects loop warning |
| 15 consecutive calls (`_HARD_STOP_NAME = 15`) | **Hard stop**: Strips tool calls, agent exits |

### Level 3: Session-Wide Total

| Threshold | Action |
|---|---|
| 50 total calls to same tool across entire session (`_SESSION_HARD_STOP = 50`) | **Hard stop** |

### Hard Stop Implementation (`_force_stop`)

```python
def _force_stop(self, messages, last, reason):
    # Replace AIMessage: keep text content, drop all tool_calls
    forced_ai = last.model_copy(update={"tool_calls": [], "content": forced_text})
    # Agent sees no tool calls → routes to END → loop breaks
```

**Key insight:** Loop detection only prevents the agent from calling the SAME tool too many times. It does NOT force the agent to try DIFFERENT tools.

---

## 4. Reasoning Filter — Catching "Thinking Out Loud"

**File:** `libs/deepagents/deepagents/middleware/reasoning_filter.py`

Some models (NVIDIA Nemotron, etc.) output their chain-of-thought as the response instead of calling tools. This middleware catches that pattern.

### How It Works

1. After model generates response, check if it's "reasoning-only" (no tool calls + matches reasoning patterns like "Let me check...", "I need to...", "First, I'll...")
2. If yes: **Remove the reasoning message entirely** and inject a nudge:
   ```
   [SYSTEM] You just output reasoning instead of acting.
   Execute the next action immediately using a tool call, or give a final answer.
   ```
3. Jump back to the model (`jump_to: "model"`) for a retry
4. Max 2 retries (`MAX_REASONING_RETRIES = 2`), then give up and strip the content

**This is a retry mechanism** — but only for the specific case of reasoning-as-content. It does NOT retry failed tool calls or try alternative approaches.

---

## 5. Context Management — Compaction & Truncation

**File:** `libs/deepagents/deepagents/middleware/summarization.py`

### When Context Gets Full

| Model Type | Trigger | Keep |
|---|---|---|
| Models with profile (max_input_tokens known) | 85% of context used | 10% of context |
| Models without profile | 170K tokens | Last 6 messages |

### Two-Stage Process

1. **Argument Truncation** (lightweight, fires first): Clips large tool-call args (file contents, edit patches) in older messages. Keeps recent messages intact.
2. **Full Summarization** (expensive, fires at higher threshold): LLM summarizes older conversation history → offloads full history to `/conversation_history/{thread_id}.md` → replaces old messages with summary.

The agent continues seamlessly — compaction happens mid-turn, no restart needed.

### Context Overflow Fallback

If the model call fails with a context overflow error even before thresholds are hit, the middleware catches it and forces summarization as an emergency fallback (`summarization.py:923`).

---

## 6. Tool & Skill Loading

### Tools: Bound Once at Creation

All tools are passed to `create_agent()` at startup (`graph.py:716`). There is **no dynamic tool loading** during a run. The agent works with what it's given.

### Skills: Progressive Disclosure

Skills use a **demand-driven** pattern (`middleware/skills.py:611-639`):

1. Agent sees **metadata only** (name + one-line description) in system prompt
2. Agent decides if a skill is relevant
3. Agent explicitly calls `read_file("/skills/built-in/<service>/SKILL.md")`
4. Follows the skill's instructions

**No automatic fallback:** If the agent doesn't recognize it should use a skill, it won't. If one skill fails, the harness doesn't suggest trying another.

### MCP Tools

MCP servers loaded from JSON config. If a server fails to load → logged and skipped, not retried.

---

## 7. Model Fallback Chain

**File:** `libs/deepagents/deepagents/graph.py:280`

The model itself has provider-level fallbacks for 429/5xx errors:

```python
def _attach_fallbacks(model):
    # Wraps primary model with all other available providers
    # If primary returns 429/500, automatically tries next provider
    return model.with_fallbacks(fallback_models)
```

Provider priority order (`graph.py:250-267`):
1. OpenRouter (DeepSeek, Llama 4 Maverick, Qwen 3.5 — all free tier)
2. Moonshot (Kimi K2.5 — 256K context)
3. Cerebras (Llama 4 Scout — fast inference)
4. Cloudflare (Llama 4 Scout)
5. NVIDIA (Qwen 3.5, DeepSeek v3.2)
6. Mistral, Nebius, HuggingFace (last-resort fallbacks)

**This only handles provider failures (rate limits, server errors), NOT task failures.**

---

## 8. Self-Correction Rules (Prompt-Level)

The system prompt (`graph.py:151-174`) includes self-correction instructions:

```
1. Never repeat a failed call with the same arguments. Change your approach.
2. If a Composio action 404s → the slug is wrong. Read the skill docs.
3. If param errors → call composio_get_schema first.
4. If wrong data → examine metadata, adjust params.
5. If blocked after 2 attempts → tell user what's wrong, ask for guidance.
6. Track what you've tried. Never repeat a rejected approach.
7. If 401 → API key missing, check system prompt for key, retry.
8. If 429 → rate limited, try different endpoint or retry once.
9. If composio_action keeps failing → fall back to execute with Python SDK.
```

**These are prompt-level instructions, not enforced by code.** The model may or may not follow them.

---

## 9. Ralph Mode — The Outer Reloop

**File:** `examples/ralph_mode/ralph_mode.py`

Ralph Mode is an **outer loop** that re-invokes the entire agent with fresh context:

```python
while max_iterations == 0 or iteration <= max_iterations:
    prompt = f"Your previous work is in the filesystem. Check what exists and keep building.\nTASK:\n{task}"
    exit_code = await run_non_interactive(message=prompt, ...)
    iteration += 1
```

Key properties:
- **Fresh context each iteration** — no context rot
- **Filesystem persists** — work carries over via files + git
- **Unlimited iterations** by default (Ctrl+C to stop)
- Each iteration is a full independent agent run

**Ralph Mode is NOT built into the main agent.** It's an external orchestrator script. The default agent (interactive/non-interactive) does NOT have this reloop behavior.

---

## 10. SubAgent Delegation

**File:** `libs/deepagents/deepagents/middleware/subagents.py`

The main agent can spawn subagents for complex tasks. Subagents are defined as specs with their own:
- System prompts
- Tool sets
- Model configurations

SubAgent types include `general-purpose`, `composio-worker`, `web-scraper`. The main agent decides when to delegate based on task complexity tiers in the system prompt.

**Subagents run independently** — they have their own context windows, tool sets, and middleware stacks.

---

## 11. What Was MISSING — Fixes Applied

These gaps caused premature stopping. All have been addressed:

### FIXED: "Try All Tools" Enforcement
**Before:** No mechanism to force trying different tools before giving up.
**After:** `EarlyExitPreventionMiddleware` intercepts "giving up" text-only responses, checks how many distinct tools were tried, and nudges the model to try untried tools. Lists specific tools the agent hasn't used yet.

### FIXED: Automatic Fallback Chain for Tools
**Before:** Tools had no fallback chain — if `web_search` fails, nothing suggested alternatives.
**After:** `SelfCorrectionMiddleware` defines fallback chains (`web_search` → `fetch_url` → `execute`, etc.) and suggests them when a tool call fails. System prompt now documents these chains explicitly.

### FIXED: "Exhaustion Check" Before Exit
**Before:** No middleware checked if the agent tried enough before stopping.
**After:** `EarlyExitPreventionMiddleware` tracks distinct tools used per turn and requires `MIN_TOOLS_TRIED = 2` before allowing a "giving up" exit. Up to 2 nudges before finally allowing exit.

### FIXED: Self-Correction Is Middleware-Enforced
**Before:** "Never repeat a failed call" was prompt-only — models could ignore it.
**After:** `SelfCorrectionMiddleware` tracks failed call signatures and **blocks** exact retries at the middleware level. Provides specific error-pattern advice (404 → check path, 401 → check auth, 429 → try different endpoint, etc.).

### STILL AVAILABLE: Ralph Loop (External)
Ralph Mode exists as `examples/ralph_mode/ralph_mode.py` for long-horizon tasks that need fresh-context relooping. The inner middleware fixes above handle the per-turn problem; Ralph handles the cross-session problem.

---

## Architecture Diagram

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  MAIN LOOP (while True)                              │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  agent.astream()                             │     │
│  │                                              │     │
│  │  ┌──── Middleware Stack (before_agent) ────┐ │     │
│  │  │  TodoList → Memory → Skills →           │ │     │
│  │  │  Filesystem → SubAgents                 │ │     │
│  │  └─────────────────────────────────────────┘ │     │
│  │              │                                │     │
│  │              ▼                                │     │
│  │  ┌──── MODEL CALL ────┐                      │     │
│  │  │  Primary provider   │                      │     │
│  │  │  ↓ (429/5xx)        │                      │     │
│  │  │  Fallback providers │                      │     │
│  │  └─────────────────────┘                      │     │
│  │              │                                │     │
│  │              ▼                                │     │
│  │  ┌──── Middleware Stack (after_model) ─────┐ │     │
│  │  │  Summarization → ReasoningFilter →      │ │     │
│  │  │  EarlyExitPrevention → SelfCorrection → │ │     │
│  │  │  LoopDetection → PatchToolCalls → HITL  │ │     │
│  │  └─────────────────────────────────────────┘ │     │
│  │              │                                │     │
│  │         ┌────┴────┐                           │     │
│  │    Has tool_calls?                            │     │
│  │    YES → execute tools → loop back to model   │     │
│  │    NO  → route to END                         │     │
│  └──────────────────────────────────────────────┘     │
│              │                                        │
│         ┌────┴────┐                                   │
│    HITL interrupt?                                    │
│    YES → get user decision → Command(resume=...)      │
│    NO  → dispatch("task.complete") → break            │
└───────────────────────────────────────────────────────┘
    │
    ▼
  Agent Done
```

---

## Key Files Reference

| Component | File |
|---|---|
| Main interactive loop | `libs/cli/deepagents_cli/textual_adapter.py:645-1293` |
| Main non-interactive loop | `libs/cli/deepagents_cli/non_interactive.py:655-669` |
| Middleware stack assembly | `libs/deepagents/deepagents/graph.py:674-732` |
| System prompt + self-correction rules | `libs/deepagents/deepagents/graph.py:100-190` |
| Early exit prevention middleware | `libs/deepagents/deepagents/middleware/early_exit_prevention.py` |
| Self-correction middleware | `libs/deepagents/deepagents/middleware/self_correction.py` |
| Loop detection middleware | `libs/deepagents/deepagents/middleware/loop_detection.py` |
| Reasoning filter middleware | `libs/deepagents/deepagents/middleware/reasoning_filter.py` |
| Summarization/compaction | `libs/deepagents/deepagents/middleware/summarization.py` |
| Skills progressive disclosure | `libs/deepagents/deepagents/middleware/skills.py:600-640` |
| SubAgent middleware | `libs/deepagents/deepagents/middleware/subagents.py` |
| Model fallback chain | `libs/deepagents/deepagents/graph.py:280-300` |
| Ralph Mode (external reloop) | `examples/ralph_mode/ralph_mode.py` |
| Tool argument patching | `libs/deepagents/deepagents/middleware/patch_tool_calls.py` |
| Filesystem middleware | `libs/deepagents/deepagents/middleware/filesystem.py` |
| Model auto-detection | `libs/deepagents/deepagents/graph.py:250-267` |
