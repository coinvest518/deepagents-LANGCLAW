---
name: astra-admin
description: >
  Inspect and clean up AstraDB collections. Use when the user asks to "list
  astra collections", "clean up astra", "delete a collection", "fix the 100
  index limit", "free up astra space", or when an astra write fails with
  "Cannot have more than 100 indexes". AstraDB free tier caps each keyspace
  at 100 Storage Attached Indexes (~25 collections). This skill wraps
  scripts/astra_cleanup.py so the agent can diagnose and recover.
license: MIT
compatibility: deepagents-cli
---

# AstraDB Admin Skill

Lets the agent inspect the AstraDB keyspace and drop unused collections to
free up the 100-index quota. Requires `ASTRA_DB_API_KEY` and
`ASTRA_DB_ENDPOINT` in the environment.

## Why this exists

AstraDB free tier: **100 Storage Attached Indexes per keyspace**. Each
collection costs ~4 indexes — so ~25 collections before new ones fail with
`Cannot have more than 100 indexes`. Old test collections, old
knowledge-base runs, and experimental data accumulate. This skill drops the
stale ones to free slots.

The log warning `AstraDB 100-index limit hit for 'X' — switching to
get_collection` is **already handled gracefully** in deploy/astra_store.py
(the collection still works). But if you want to create a **new** collection,
you have to free slots first.

## Commands

### List every collection with doc counts

```bash
python scripts/astra_cleanup.py
```

Prints a numbered table: name, doc count, and the cap warning.

### Drop one specific collection

```bash
python scripts/astra_cleanup.py --delete collection_name_here
```

Prompts for `[y/N]` confirmation before dropping.

### Interactive purge — keep a whitelist, review the rest

```bash
python scripts/astra_cleanup.py --keep agent_tasks,conversation_history,mem0_*
```

Walks every collection NOT matching the keep patterns and asks `[y/N/q]` for
each one. `q` stops the loop. Prefix match with trailing `*`
(`mem0_*` matches `mem0_main`, `mem0_test`, etc.).

Add `--yes` to auto-confirm every candidate (dangerous — only use when you
already ran without `--yes` and know the list is correct):

```bash
python scripts/astra_cleanup.py --keep agent_tasks,conversation_history,mem0_* --yes
```

## Core collections (NEVER delete these)

- `agent_tasks` — task lifecycle records for the dashboard
- `conversation_history` — raw message log, used as fallback when the
  LangGraph checkpointer is empty after a Render restart
- Any `mem0_*` — Mem0 semantic memory
- Any active knowledge-base collections

## When the agent should use this skill

1. User reports AstraDB errors ("100 index limit", "collection create failed")
2. User says "clean up astra" / "list my collections" / "delete X from astra"
3. An agent tool call itself fails with the 100-index message and the agent
   wants to free space before retrying

## Safety

- Dropping a collection is **irreversible**. The script always prompts
  unless `--yes` is passed.
- Always run without `--delete`/`--keep` first to see the current state.
- Never drop `agent_tasks` or `conversation_history` — the dashboard and
  history-replay-on-restart depend on them.

## Reference

- Implementation: `scripts/astra_cleanup.py`
- AstraDB client in the app: `deploy/astra_store.py`
- AstraDB Python SDK: [astrapy docs](https://docs.datastax.com/en/astra-api-docs/index.html)
