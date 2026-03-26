---
name: memory
description: >
  Long-term memory, database storage, and document management — search past
  conversations, save facts/preferences, store structured data, save and
  retrieve documents. Uses Mem0 for semantic memory search and AstraDB for
  structured storage across 3 collections: agent_memory, agent_data,
  agent_documents.
license: MIT
compatibility: deepagents-cli
---

# Memory, Database & Document Storage Skill

Six native tools give the agent persistent memory, structured database access,
and document storage — each with a distinct purpose:

## Collections in AstraDB

| Collection | Purpose |
|------------|---------|
| `agent_memory` | Facts, preferences, learned context (long-term memory) |
| `agent_data` | Structured key-value records (configs, analysis results) |
| `agent_documents` | Full documents (notes, PDFs, web content, emails) |

## Tools

| Tool | Backend | Purpose |
|------|---------|---------|
| `search_memory` | Mem0 + AstraDB | Search long-term memory — facts, preferences, past context |
| `save_memory` | Mem0 + AstraDB | Save a fact/preference to long-term memory |
| `search_database` | AstraDB `agent_data` | Search structured key-value records |
| `save_to_database` | AstraDB `agent_data` | Store structured JSON data by key |
| `search_documents` | AstraDB `agent_documents` | Search stored documents by type/tags |
| `save_document` | AstraDB `agent_documents` | Save a document (note, PDF, web content) |

## When to Use Each Tool

### search_memory / save_memory
- "What did we talk about last time?" → `search_memory(query="...")`
- "Remember that I prefer dark mode" → `save_memory(content="...", category="preference")`
- After learning an important fact → `save_memory(content="...", category="fact")`

### search_database / save_to_database
- "What data do we have stored?" → `search_database()`
- "Save these API results" → `save_to_database(key="api_results_march", data={...})`
- "Look up the config we saved" → `search_database(query_filter={"type": "config"})`

### search_documents / save_document
- "Save this email for later" → `save_document(title="...", content="...", doc_type="email")`
- "Find my saved notes about project X" → `search_documents(tags=["project-x"])`
- "Store this PDF text" → `save_document(title="Contract.pdf", content="...", doc_type="pdf")`

## Examples

**Search memory:**
```
search_memory(query="pricing model discussion", user_id="default")
```

**Save a preference:**
```
save_memory(content="User prefers weekly reports on Monday mornings", category="preference")
```

**Store analysis results:**
```
save_to_database(key="competitor_analysis_q1", data={"company": "Acme", "score": 85})
```

**Save a document:**
```
save_document(title="Meeting Notes March 2025", content="...", doc_type="note", tags=["meetings", "q1"])
```

**Search documents by type:**
```
search_documents(doc_type="email", limit=10)
```

## Environment Variables Required

| Variable | Purpose |
|----------|---------|
| `MEM0_API_KEY` | Mem0 semantic memory (optional) |
| `ASTRA_DB_API_KEY` | AstraDB token (required for database/documents) |
| `ASTRA_DB_ENDPOINT` | AstraDB endpoint URL |

At least one backend must be configured. Mem0 provides semantic search;
AstraDB provides structured storage. Both work independently or together.