# DeepAgents Tool/Skill Loading Architecture

## Overview

The DeepAgents CLI system uses a **middleware-first architecture** to inject tools and skills dynamically without overloading system prompts. Tools reach the LLM through two paths:

1. **SDK middleware** (`deepagents.middleware.*`) — system-prompt injection + dynamic filtering
2. **Consumer-provided tools** — plain callables passed to `create_deep_agent()`

Both paths are merged by `create_agent()` from LangChain's agent framework. The key insight: middleware intercepts EVERY LLM request via `wrap_model_call()` to dynamically modify the system message.

---

## Key Files & Architecture

### 1. **libs/deepagents/deepagents/graph.py** — Main Agent Graph Assembly

**Lines 7, 245-520:** `create_deep_agent()` function uses LangChain agent framework:

- **Model resolution** (L280-290): Detects best available LLM, adds fallback providers
- **Middleware stacking** (L360-500): Builds middleware in order:
  1. `TodoListMiddleware()`
  2. `MemoryMiddleware` (if `memory` paths provided)
  3. `SkillsMiddleware` (if `skills` paths provided)
  4. `FilesystemMiddleware()`
  5. `SubAgentMiddleware()`
  6. `SummarizationMiddleware()`
  7. `AnthropicPromptCachingMiddleware` (if anthropic available)
  8. `LoopDetectionMiddleware()`
  9. `PatchToolCallsMiddleware()`
  10. User-provided middleware
  11. `HumanInTheLoopMiddleware` (if `interrupt_on` config)

- **Key call** (L493-520): Passes to LangChain's `create_agent()`:
  ```python
  return create_agent(
      model_with_fallbacks,
      system_prompt=final_system_prompt,
      tools=tools,  # Plain tools list
      middleware=deepagent_middleware,
      ...
  ).with_config({"recursion_limit": 50})
  ```

**Why middleware?** Tools + system prompt can both be dynamically modified per-request without recompiling the graph.

### 2. **libs/deepagents/deepagents/middleware/__init__.py** — Exports

Exports all middleware types that consumers use:
- `SkillsMiddleware` — loads and injects skill documentation
- `MemoryMiddleware` — injects memory context
- `FilesystemMiddleware` — manages file tool availability
- `SubAgentMiddleware` — handles subagent spawning
- `SummarizationMiddleware` — token-aware context compression

### 3. **libs/deepagents/deepagents/middleware/skills.py** — Skill Injection Engine

**Lines 165-205:** `SkillMetadata` TypedDict defines skill structure:
```python
class SkillMetadata(TypedDict):
    path: str  # "/skills/user/web-research/SKILL.md"
    name: str  # "web-research"
    description: str  # What the skill does
    license: str | None
    compatibility: str | None
    metadata: dict[str, str]
    allowed_tools: list[str]
```

**Lines 482-560:** `_alist_skills()` async function:
- Lists all skill directories under `source_path`
- Downloads `SKILL.md` from each
- Parses YAML frontmatter (lines 250-400: `_parse_skill_metadata()`)
- Returns list of `SkillMetadata`

**Lines 708-725:** `modify_request()` — THE KEY HOOK:
```python
def modify_request(self, request: ModelRequest[ContextT]) -> ModelRequest[ContextT]:
    skills_metadata = request.state.get("skills_metadata", [])
    skills_list = self._format_skills_list(skills_metadata)
    skills_section = self.system_prompt_template.format(
        skills_locations=skills_locations,
        skills_list=skills_list,
    )
    new_system_message = append_to_system_message(request.system_message, skills_section)
    return request.override(system_message=new_system_message)
```

This runs **before every model call** — skills documentation is appended to system message dynamically.

**Lines 766-800:** `before_agent()` & `abefore_agent()`:
- Called once per session (before first turn)
- Loads all skills from `sources` into `request.state["skills_metadata"]`
- Stored in state (not system prompt) for reuse across turns

**Lines 802-834:** `wrap_model_call()` & `awrap_model_call()`:
- Calls `modify_request()` to inject skill docs into system message
- Handler processes modified request

### 4. **libs/deepagents/deepagents/middleware/_utils.py** — System Prompt Injection

**Lines 1-20:** `append_to_system_message()`:
```python
def append_to_system_message(
    system_message: SystemMessage | None,
    text: str,
) -> SystemMessage:
    new_content = list(system_message.content_blocks) if system_message else []
    if new_content:
        text = f"\n\n{text}"
    new_content.append({"type": "text", "text": text})
    return SystemMessage(content_blocks=new_content)
```

**Key design:** Appends to system message's content blocks without truncating. Prevents prompt injection via LangChain's structured message system.

### 5. **libs/cli/deepagents_cli/agent.py** — CLI Agent Assembly

**Lines 15-48:** Imports and dependencies:
```python
from deepagents import create_deep_agent
from deepagents.middleware import MemoryMiddleware, SkillsMiddleware
```

**Lines 642-1050:** `create_cli_agent()` function:

**Step 1: Setup directories** (L730-750):
- Ensures `~/.deepagents/{agent_id}/` exists
- Creates empty `AGENTS.md` for user customizations
- Ensures skill dirs exist in both user and project locations

**Step 2: Build middleware stack** (L800-870):
- `ConfigurableModelMiddleware()` — model selection
- `AskUserMiddleware()` — question tool
- `MemoryMiddleware` (if enabled) — loads `AGENTS.md` from:
  - `~/.deepagents/{agent_id}/AGENTS.md`
  - `.deepagents/AGENTS.md` (project)
- `SkillsMiddleware` (if enabled) — loads from precedence order:
  1. `<package>/built_in_skills/`
  2. `~/.deepagents/{agent_id}/skills/`
  3. `~/.agents/skills/` (alias)
  4. `.deepagents/skills/` (project)
  5. `.agents/skills/` (project alias)

**Step 3: Setup backend** (L875-920):
- Local mode: `LocalShellBackend` (if shell enabled) or `FilesystemBackend`
- Remote mode: Provided `SandboxBackendProtocol` (Modal, Daytona, etc.)

**Step 4: Build composite backend** (L970-990):
- Routes `/large_tool_results/` to temp dir
- Routes `/conversation_history/` to temp dir
- Prevents working dir pollution

**Step 5: Configure interrupts** (L945-960):
```python
if auto_approve:
    interrupt_on = {}  # No interrupts
else:
    interrupt_on = _add_interrupt_on()  # Full HITL approval for shell, file, web tools
```

**Step 6: Call create_deep_agent()** (L1010-1040):
```python
agent_kwargs = {
    "model": model,
    "system_prompt": system_prompt,
    "tools": tools,  # Consumer-provided tools
    "backend": composite_backend,
    "middleware": agent_middleware,  # CLI middleware stack
    "interrupt_on": interrupt_on,
    ...
}
agent = create_deep_agent(**agent_kwargs).with_config(config)
```

### 6. **libs/cli/deepagents_cli/config.py** — Settings & Configuration

**Lines 1-50:** Environment detection:
- Loads `.env` files
- Detects API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.)
- Reads LangSmith project overrides (`DEEPAGENTS_LANGSMITH_PROJECT`)
- Parses shell allow-list (`DEEPAGENTS_SHELL_ALLOW_LIST`)

**Lines 600-800+:** `Settings` dataclass:
- Tracks available API keys
- Detects project root (git repo)
- Provides methods like `has_openai`, `has_anthropic` for UI branching
- `reload_from_environment()` for runtime refresh

### 7. **libs/cli/deepagents_cli/skills/load.py** — CLI Skill Listing

**Lines 1-100+:** `list_skills()` function:
- Wraps `list_skills_from_backend()` from middleware
- Loads skills from precedence directories
- Adds `source` field ("`built-in`", "`user`", "`project`")
- Used by CLI commands (`deepagents skill list`, etc.)

### 8. **libs/deepagents/deepagents/__init__.py** — Public SDK Exports

```python
from deepagents.graph import create_deep_agent
from deepagents.middleware import (
    AsyncSubAgent, AsyncSubAgentMiddleware,
    CompiledSubAgent, FilesystemMiddleware, MemoryMiddleware,
    SubAgent, SubAgentMiddleware,
)
```

Only `create_deep_agent` exported as main API; consumers don't import middleware directly (it's auto-wired).

---

## Key Design Patterns

### Middleware vs. Tool Functions

**Middleware** (2-way hook at request/response boundaries):
- Filter tools dynamically per-request
- Inject context into system prompt
- Track state across turns
- Transform messages (summarization, caching)

```python
# Middleware lifecycle
before_agent() → abefore_agent()     # Once per session
modify_request() → wrap_model_call() # Every LLM call
```

**Plain Tools** (invoked only by LLM):
- Stateless, self-contained functions
- No system-prompt access
- Consumer-specific (CLI only)

### Skill Metadata Loaded Once, Injected Every Turn

**Session startup:**
```
before_agent()
  └─ backend.alist(source_path)
     └─ state["skills_metadata"] = [all skills parsed & validated]
```

**Every LLM call:**
```
wrap_model_call()
  └─ modify_request()
     └─ read state["skills_metadata"]
     └─ format skill list (name, description, path to SKILL.md)
     └─ append to system_message
```

**Why?** Metadata is tiny (name + 1-line desc), full content is only referenced, not inlined.

### Prompt Injection Prevention

Two protections:

1. **Content blocks** (not string concatenation):
   ```python
   new_content.append({"type": "text", "text": text})
   ```

2. **File size limits** (lines 117-120 in skills.py):
   ```python
   MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024  # 10MB DoS protection
   ```

---

## Flow Diagram: User Message → Tool Execution

```
User Input
    ↓
create_cli_agent()
    ├─ Builds middleware stack (SkillsMiddleware, MemoryMiddleware, etc.)
    ├─ Calls create_deep_agent()
    │  └─ Wraps model with fallbacks
    │  └─ Registers middleware
    │  └─ Calls LangChain's create_agent()
    └─ Returns (graph, composite_backend)
    ↓
graph.invoke(input)
    ├─ Calls before_agent() on each middleware (once per session)
    │  └─ SkillsMiddleware.before_agent()
    │     └─ Loads SKILL.md files → state["skills_metadata"]
    ├─ Main agent loop:
    │  ├─ Calls wrap_model_call() on each middleware
    │  │  └─ SkillsMiddleware.modify_request()
    │  │     ├─ Reads state["skills_metadata"]
    │  │     ├─ Formats skill list (metadata only, not full content)
    │  │     └─ Appends to system_message via append_to_system_message()
    │  ├─ Sends modified request to LLM
    │  ├─ LLM reads system message (includes skill metadata)
    │  ├─ LLM calls tools if needed
    │  ├─ Tool execution (handled by graph)
    │  └─ Loop until done
    └─ Return final response
```

---

## Summary: How System Prompt Stays Small

1. **Skills metadata injected, not hardcoded:**
   - System prompt starts with BASE_AGENT_PROMPT (base tier instructions)
   - Skills middle-ware appends brief metadata listing on every call
   - Full SKILL.md content is referenced (path), not inlined
   - User can read `~/.deepagents/{agent}/skills/{skill}/SKILL.md` directly

2. **Middleware layers context dynamically:**
   - Each middleware appends its section to system message
   - Order: base → memory → skills → subagents → ...
   - No fixed "maximum tools" — as many skills as fit in context window

3. **Skill loading is lazy:**
   - Skills loaded once at session start (not every request)
   - Cached in state["skills_metadata"]
   - Formatting happens on every request but cost is O(n_skills)

4. **Backend abstraction prevents filesystem bloat:**
   - Skills loaded from backend (filesystem OR remote storage)
   - No implicit file reads
   - Each source can override earlier ones (last-one-wins precedence)
