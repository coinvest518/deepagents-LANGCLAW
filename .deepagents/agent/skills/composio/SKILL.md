---
name: composio
description: Use 1000+ external apps via Composio - either directly through the CLI or by building AI agents and apps with the SDK
tags: [composio, tool-router, agents, mcp, tools, api, automation, cli]
---

## When to Apply

- User wants to access or interact with external apps (Gmail, Slack, GitHub, Notion, etc.)
- User wants to automate a task using an external service (send email, create issue, post message)
- Building an AI agent or app that integrates with external tools
- Multi-user apps that need per-user connections to external services

## Setup

Check if the CLI is installed; if not, install it:
```bash
curl -fsSL https://composio.dev/install | bash
```

After installation, restart your terminal or source your shell config, then authenticate:
```bash
composio login       # OAuth; interactive org/project picker (use -y to skip)
composio whoami      # verify org_id, project_id, user_id
```
For agents without direct browser access: `composio login --no-wait | jq` to get URL/key, share URL with user, then `composio login --key <cli_key> --no-wait` once they complete login.

---

### 1. Use Apps via Composio CLI

**Use this when:** The user wants to take action on an external app directly — no code writing needed. The agent uses the CLI to search, connect, and execute tools on behalf of the user.

Key commands (new top-level aliases):
- `composio search "<query>"` — find tools by use case
- `composio execute "<TOOL_SLUG>" -d '{...<input params>}'` — execute a tool
- `composio link [toolkit]` — connect a user account to an app (agents: always use `--no-wait` for non-interactive mode)
- `composio listen` — listen for real-time trigger events

Typical workflow: **search → link (if needed) → execute**

> Full reference: [Composio CLI Guide](rules/composio-cli.md)

---

### 2. Building Apps and Agents with Composio

**Use this when:** Writing code — an AI agent, app, or backend service that integrates with external tools via the Composio SDK.

Run this first inside the project directory to set up the API key:
```bash
composio init
```

> Full reference: [Building with Composio](rules/building-with-composio.md)

---

## Quick Reference (agent guidance)

- Tools are single API actions (tool slugs) grouped by toolkits like `gmail`, `github`, `googlesheets`.
- All tool calls must be scoped to a user — resolve account IDs via `COMPOSIO_<TOOLKIT>_ACCOUNT_ID` env vars or `deploy/composio_routing.json` + `libs/cli/deepagents_cli/composio_router.py`.
- Before calling an unfamiliar action, call `composio_get_schema("ACTION_SLUG")` to learn parameter names, types, and required fields.

### Recommended agent flow
1. Discover schema with `composio_get_schema("ACTION_SLUG")`.
2. Validate/coerce arguments to the schema types.
3. Execute with `composio_action("ACTION_SLUG", arguments)` or via the unified dispatcher `deepagents_cli.composio_dispatcher.dispatch(action, arguments)` for non-blocking agent code.
4. If you get a 404 / "not found" error, do not retry — the slug is likely incorrect. Use `composio_get_schema` or consult the skill docs to find the exact slug.

### Error handling hints
- When arguments are malformed, return the schema to the LLM as a hint so it can correct the argument shape.
- If Composio is not configured (missing `COMPOSIO_API_KEY`/`COMPOSIO_API_URL`), return a clear message like `COMPOSIO not configured` instead of raw exception traces.

### Dispatcher
- Use `libs/cli/deepagents_cli/composio_dispatcher.py` for a consistent HTTP-based execute flow. It resolves account ids from env, posts to `/v1/execute`, and returns `{"success": True/False, "result"/"error": ...}`.

### MCP docs
If programmatic docs are needed, `.mcp.json` includes `composio-docs` so tools can fetch Composio docs via MCP.

