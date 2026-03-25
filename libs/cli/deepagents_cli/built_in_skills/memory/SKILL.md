---
name: memory
description: >
  Long-term memory and database storage — search past conversations,
  save facts/preferences, store and retrieve structured data. Uses Mem0
  for semantic memory search and AstraDB for structured document storage.
  Use when the user says "remember", "recall", "look up what we discussed",
  "save this", "store this data", "check the database", or when you want
  to persist information across conversations.
license: MIT
compatibility: deepagents-cli
---

# Memory & Database Skill

Four native tools give the agent persistent memory and database access:

## Tools

| Tool | Backend | Purpose |
|------|---------|---------|
| `search_memory` | Mem0 | Semantic search across saved memories — use natural language queries |
| `save_memory` | Mem0 + AstraDB | Save a fact, preference, or piece of info to long-term memory |
| `search_database` | AstraDB | Browse/list structured documents stored in the database |
| `save_to_database` | AstraDB + Mem0 | Store structured JSON data (records, analysis results, etc.) |

## When to Use Each Tool

### search_memory
- User asks "what did we talk about last time?"
- User asks "do you remember my preference for X?"
- You need context from a prior conversation
- Searching for a fact the user previously told you

### save_memory
- User says "remember that I prefer dark mode"
- User says "note that the API key rotates monthly"
- You learn an important fact worth persisting
- After completing a task — save a summary for future reference

### search_database
- User asks "what data do we have stored?"
- User asks "show me the records from the analysis"
- Browsing previously saved structured data

### save_to_database
- User says "save these results to the database"
- Storing extracted data from documents, APIs, or analysis
- Persisting structured records (JSON) for later retrieval

## Examples

**Search memory:**
> "What did we discuss about the pricing model?"
→ Call `search_memory(query="pricing model discussion")`

**Save a preference:**
> "Remember that I prefer weekly reports on Monday mornings"
→ Call `save_memory(content="User prefers weekly reports delivered Monday mornings")`

**Store analysis results:**
> "Save this competitor analysis"
→ Call `save_to_database(key="competitor_analysis_2024", data={...}, collection="agent__research")`

**Look up stored data:**
> "What research do we have saved?"
→ Call `search_database(collection="agent__research")`

## Environment Variables Required

| Variable | Purpose |
|----------|---------|
| `MEM0_API_KEY` | Mem0 semantic memory (primary) |
| `ASTRA_DB_API_KEY` | AstraDB token |
| `ASTRA_DB_ENDPOINT` | AstraDB URL |
| `ASTRA_DB_KEYSPACE` | AstraDB keyspace |

At least one backend must be configured. Both can work independently.