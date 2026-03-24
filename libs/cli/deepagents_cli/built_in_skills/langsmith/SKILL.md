---
name: langsmith
description: Query LangSmith traces to find errors, slow runs, and failing tools. Use this to monitor what the agent is doing, diagnose failures, and hand off fixes to the coding agent or Daytona sandbox.
---

# LangSmith Monitoring Skill

LangSmith records every agent run, tool call, and error automatically.
Use this skill to **find errors → understand what failed → fix it**.

## The big picture (simple version)

```
Agent runs → LangSmith records everything → You query traces → Find errors → Fix with code
```

Think of LangSmith like a black box recorder on a plane. Every time the agent
does something, it gets logged. When something breaks you can rewind and see exactly
what happened, what tools were called, what the inputs/outputs were, and where it failed.

---

## Tool: call the LangSmith API directly

Use `http_request` to query LangSmith:

```python
import os, json

LS_KEY = os.environ["LANGSMITH_API_KEY"]
LS_PROJECT = os.environ.get("LANGSMITH_PROJECT", "deeperagents")
BASE = "https://api.smith.langchain.com/api/v1"

# Step 1: get the session UUID for your project
resp = http_request(
    url=f"{BASE}/sessions?name={LS_PROJECT}",
    headers={"x-api-key": LS_KEY}
)
session_id = resp["content"][0]["id"]  # first match

# Step 2: query recent root-level runs (one per user message)
runs = http_request(
    url=f"{BASE}/runs/query",
    method="POST",
    headers={"x-api-key": LS_KEY},
    data={
        "session": [session_id],
        "filter": "eq(is_root, true)",
        "limit": 20,
    }
)["content"]["runs"]
```

## Recipes

### Find all errors from the last 24 hours

```python
errors = [r for r in runs if r.get("error")]
for e in errors:
    print(f'{e["start_time"][:19]}  {e["name"]}  ERROR: {e["error"][:200]}')
```

### Find slow runs (> 30 seconds)

```python
def latency(r):
    if not r.get("start_time") or not r.get("end_time"):
        return 0
    return (
        __import__("datetime").datetime.fromisoformat(r["end_time"].replace("Z",""))
        - __import__("datetime").datetime.fromisoformat(r["start_time"].replace("Z",""))
    ).total_seconds()

slow = [(latency(r), r["id"], r["name"]) for r in runs if latency(r) > 30]
slow.sort(reverse=True)
for s, rid, name in slow[:5]:
    print(f'{s:.1f}s  {name}  {rid}')
```

### Get the full trace tree for a run (all tool calls inside it)

```python
trace_id = "paste-run-id-here"
spans = http_request(
    url=f"{BASE}/runs/query",
    method="POST",
    headers={"x-api-key": LS_KEY},
    data={
        "session": [session_id],
        "filter": f'eq(trace_id, "{trace_id}")',
        "limit": 100,
    }
)["content"]["runs"]

# Print the call tree
for s in sorted(spans, key=lambda x: x["start_time"]):
    indent = "  " if s.get("parent_run_id") else ""
    err = f'  ❌ {s["error"][:80]}' if s.get("error") else ""
    print(f'{indent}{s["run_type"]:8} {s["name"]:<40}{err}')
```

### Find which tools are failing most

```python
# Get ALL spans (not just root) to see tool-level failures
all_spans = http_request(
    url=f"{BASE}/runs/query",
    method="POST",
    headers={"x-api-key": LS_KEY},
    data={"session": [session_id], "limit": 200}
)["content"]["runs"]

tool_errors = {}
for s in all_spans:
    if s.get("error") and s["run_type"] == "tool":
        name = s["name"]
        tool_errors[name] = tool_errors.get(name, 0) + 1

for name, count in sorted(tool_errors.items(), key=lambda x: -x[1]):
    print(f'{count:3}x  {name}')
```

---

## Workflow: Error → Fix

### Step 1: Find the error

```
"Check LangSmith for recent errors in the deeperagents project"
```

Use the recipes above. Get the error message and the run ID.

### Step 2: Get full context

```
"Get the full trace for run ID abc123 — show all tool calls and inputs"
```

### Step 3: Fix with the coding agent

Once you know WHAT failed and WHY, hand it to the coding agent:

```
"I found this error in LangSmith: [paste error + trace].
The issue is in [file]. Fix it."
```

### Step 4: Test in Daytona (optional — for risky fixes)

Daytona is a cloud sandbox — a disposable environment where you can run code
without affecting the live system:

```python
# Run a fix in isolation before deploying
from langchain_daytona import DaytonaSandbox

with DaytonaSandbox() as sandbox:
    sandbox.process.start("python test_fix.py")
    result = sandbox.process.get_output()
    print(result)
```

Use Daytona when:
- The fix involves changing how tools call external APIs
- You want to test without hitting real Gmail/GitHub accounts
- The bug is in a critical path (composio_dispatcher, server_graph, etc.)

---

## Auto-monitoring: cron job approach

Set up a cron to run every hour and alert you if errors spike:

```python
# Save as: scripts/monitor_errors.py
import os, json, requests

LS_KEY = os.environ["LANGSMITH_API_KEY"]
LS_PROJECT = os.environ.get("LANGSMITH_PROJECT", "deeperagents")
BASE = "https://api.smith.langchain.com/api/v1"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_AI_OWNER_CHAT_ID", "")

sessions = requests.get(f"{BASE}/sessions?name={LS_PROJECT}",
    headers={"x-api-key": LS_KEY}).json()
session_id = sessions[0]["id"]

runs = requests.post(f"{BASE}/runs/query",
    headers={"x-api-key": LS_KEY},
    json={"session": [session_id], "filter": "eq(is_root, true)", "limit": 50}
).json()["runs"]

errors = [r for r in runs if r.get("error")]
error_rate = len(errors) / max(len(runs), 1) * 100

if error_rate > 20 and BOT_TOKEN:  # alert if >20% error rate
    msg = f"⚠️ LangSmith alert: {len(errors)}/{len(runs)} runs failing ({error_rate:.0f}%)\n"
    msg += "\n".join(f"• {e['error'][:100]}" for e in errors[:3])
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg})
    print(msg)
else:
    print(f"OK: {len(errors)}/{len(runs)} errors ({error_rate:.0f}%)")
```

Schedule it: `deepagents cron add "0 * * * *" "python scripts/monitor_errors.py"`

---

## Key concepts (simple)

| Term | What it means |
|------|--------------|
| **Run** | One complete agent response to one message |
| **Span** | One step inside a run (one tool call, one LLM call) |
| **Trace** | The full tree of spans for a run |
| **Root run** | The top-level run (the whole thing) |
| **is_root=true** | Filter to get one entry per user message |
| **session** | Your LangSmith project (UUID, not name) |
| **Daytona** | A cloud VM sandbox — run and test code safely in isolation |

---

## CRITICAL: session lookup

The LangSmith API requires `session: ["<uuid>"]` — NOT `session_name`.
Always resolve the project name to a UUID first using `/sessions?name=projectname`.

Project: `deeperagents` → UUID: `74184a69-e379-43ba-93fc-8bef025c6935`
