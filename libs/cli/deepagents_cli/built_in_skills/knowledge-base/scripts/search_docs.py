"""
knowledge-base search_docs.py
-------------------------------
Search the agent's knowledge base for relevant document chunks.
Uses Mem0 semantic search (primary) + AstraDB text scan (fallback).

Usage:
    python search_docs.py "your question here"
    python search_docs.py "machine learning basics" --limit 5
    python search_docs.py "revenue forecast" --file "report.pdf"

Requirements:
    pip install mem0ai astrapy
"""

import os
import sys
import json


def get_mem0():
    key = os.environ.get("MEM0_API_KEY")
    if not key:
        return None
    try:
        from mem0 import MemoryClient
        return MemoryClient(api_key=key)
    except ImportError:
        return None


def get_astra():
    api_key = os.environ.get("ASTRA_DB_API_KEY")
    endpoint = os.environ.get("ASTRA_DB_ENDPOINT")
    keyspace = os.environ.get("ASTRA_DB_KEYSPACE", "default_keyspace")
    if not api_key or not endpoint:
        return None
    try:
        from astrapy import DataAPIClient
        client = DataAPIClient(token=api_key)
        return client.get_database(endpoint, keyspace=keyspace)
    except Exception:
        return None


def search_mem0(mem0, query: str, limit: int, filename_filter: str | None) -> list[dict]:
    try:
        results = mem0.search(query, user_id="knowledge_base", limit=limit)
        out = []
        for r in results:
            meta = r.get("metadata", {})
            if filename_filter and filename_filter.lower() not in meta.get("filename", "").lower():
                continue
            out.append({
                "source": "mem0",
                "filename": meta.get("filename", "?"),
                "page": meta.get("page", "?"),
                "chunk": meta.get("chunk", "?"),
                "score": r.get("score", 0),
                "text": r.get("memory", r.get("text", "")),
            })
        return out
    except Exception as e:
        print(f"WARN Mem0 search error: {e}")
        return []


def search_astra(astra_db, query: str, limit: int, filename_filter: str | None) -> list[dict]:
    try:
        col = astra_db.get_collection("knowledge_base")
        query_words = set(query.lower().split())
        results = []
        for doc in col.find({}, limit=500):
            text = (doc.get("text") or "").lower()
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                if filename_filter and filename_filter.lower() not in doc.get("filename", "").lower():
                    continue
                results.append({
                    "source": "astradb",
                    "filename": doc.get("filename", "?"),
                    "page": doc.get("page", "?"),
                    "chunk": doc.get("chunk", "?"),
                    "score": score,
                    "text": doc.get("text", ""),
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    except Exception as e:
        print(f"WARN AstraDB search error: {e}")
        return []


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print(__doc__)
        sys.exit(0)

    query = args[0]
    limit = 5
    filename_filter = None

    for i, a in enumerate(args[1:], 1):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if a == "--file" and i + 1 < len(args):
            filename_filter = args[i + 1]

    mem0 = get_mem0()
    astra_db = get_astra()

    if not mem0 and not astra_db:
        print("ERROR: No storage backend. Set MEM0_API_KEY and/or ASTRA_DB_API_KEY.")
        sys.exit(1)

    results = []

    # Mem0 is primary — semantic search
    if mem0:
        results = search_mem0(mem0, query, limit, filename_filter)

    # AstraDB fallback if Mem0 returned nothing
    if not results and astra_db:
        results = search_astra(astra_db, query, limit, filename_filter)

    if not results:
        print(f'No results found for: "{query}"')
        sys.exit(0)

    print(f'\n🔍 Results for: "{query}"\n{"─" * 60}')
    for i, r in enumerate(results, 1):
        score_str = f"{r['score']:.2f}" if isinstance(r["score"], float) else str(r["score"])
        print(f"\n[{i}] {r['filename']}  page {r['page']}, chunk {r['chunk']}  (score: {score_str})")
        print(f"    {r['text'][:400]}{'...' if len(r['text']) > 400 else ''}")

    # Also output as JSON for agent parsing
    print(f'\n{"─" * 60}')
    print("JSON:", json.dumps(results, indent=2))


if __name__ == "__main__":
    main()