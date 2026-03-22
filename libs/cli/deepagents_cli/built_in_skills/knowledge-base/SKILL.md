---
name: knowledge-base
description: >
  Document knowledge base — ingest PDFs, text files, and Markdown into
  the agent's long-term memory. Stores chunks in Mem0 (semantic/vector search)
  and AstraDB (structured backup). Use this skill when the user says "remember
  this document", "read this PDF", "add this to your knowledge", "search my docs",
  or "what does the report say about X". Requires MEM0_API_KEY and/or
  ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT in env (both already configured).
license: MIT
compatibility: deepagents-cli
---

# Knowledge Base Skill

Lets the agent ingest and retrieve documents — PDFs, text files, Markdown.
Chunks are stored in **Mem0** (semantic vector search) + **AstraDB** (structured backup).
No extra embedding API key needed — Mem0 handles its own embeddings.

## Install Required Package

```bash
pip install pypdf
```
(mem0ai and astrapy are already installed in the system)

## Commands

### Ingest a PDF or document
```bash
python scripts/ingest_docs.py /path/to/document.pdf
python scripts/ingest_docs.py /path/to/notes.txt
python scripts/ingest_docs.py /path/to/docs_folder/     # ingest whole folder
```

### List ingested documents
```bash
python scripts/ingest_docs.py /any --list
```

### Search the knowledge base
```bash
python scripts/search_docs.py "what is the revenue forecast?"
python scripts/search_docs.py "machine learning basics" --limit 5
python scripts/search_docs.py "Q3 results" --file "annual_report.pdf"
```

### Clear the knowledge base
```bash
python scripts/ingest_docs.py --clear
```

## How It Works

```
PDF/TXT/MD file
    ↓
Extract text (pypdf for PDFs, plain read for text)
    ↓
Chunk into ~600-word pieces with 80-word overlap
    ↓
Store each chunk in:
    ├── Mem0 (semantic embedding + search) ← primary retrieval
    └── AstraDB collection "knowledge_base" ← backup + browsing
    ↓
Agent searches with: python scripts/search_docs.py "query"
    → Mem0 semantic search returns relevant chunks
```

## Supported File Types

| Extension | Parsing method |
|-----------|---------------|
| `.pdf`    | pypdf (text extraction per page) |
| `.txt`    | plain read |
| `.md`     | plain read |
| `.rst`    | plain read |
| `.csv`    | plain read |
| `.json`   | plain read |

## Agent Usage Examples

When user says "add this PDF to your knowledge":
```bash
python scripts/ingest_docs.py /path/to/file.pdf
```

When user asks "what does the report say about pricing?":
```bash
python scripts/search_docs.py "pricing strategy"
```
→ Returns top 5 relevant chunks from all ingested documents.

When user wants to see what's been ingested:
```bash
python scripts/ingest_docs.py . --list
```

## Environment Variables Required

| Variable | Purpose |
|----------|---------|
| `MEM0_API_KEY` | Mem0 semantic storage (primary) |
| `ASTRA_DB_API_KEY` | AstraDB token |
| `ASTRA_DB_ENDPOINT` | AstraDB URL |
| `ASTRA_DB_KEYSPACE` | AstraDB keyspace (default: `default_keyspace`) |

Both are already configured in your `.env` / Render environment.

## Tips

- Large PDFs (100+ pages) take a minute — chunks are stored in parallel
- Mem0 semantic search finds conceptually related content, not just keyword matches
- AstraDB keeps a browsable backup if Mem0 is unavailable
- Re-ingesting the same file is safe — chunk IDs are deterministic (MD5 of filename+page+chunk)
- To update a document: `--clear` then re-ingest