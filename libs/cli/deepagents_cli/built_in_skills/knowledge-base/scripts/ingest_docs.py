"""
knowledge-base ingest_docs.py
-------------------------------
Ingest PDFs, TXT, and Markdown files into the agent's knowledge base.
Stores chunks in Mem0 (semantic search) + AstraDB (structured backup).

Usage:
    python ingest_docs.py <path>          # single file
    python ingest_docs.py <directory>     # all PDFs/TXT/MD in folder
    python ingest_docs.py <path> --list   # list already-ingested docs
    python ingest_docs.py --clear         # wipe knowledge base

Requirements:
    pip install pypdf mem0ai astrapy
"""

import os
import sys
import json
import hashlib
import textwrap
from pathlib import Path
from datetime import datetime

CHUNK_SIZE = 600       # words per chunk
CHUNK_OVERLAP = 80     # word overlap between chunks


# ── Text extraction ──────────────────────────────────────────────────────────

def extract_pdf(path: str) -> list[dict]:
    """Returns list of {page, text} dicts."""
    try:
        import pypdf
    except ImportError:
        print("ERROR: pypdf not installed. Run: pip install pypdf")
        sys.exit(1)

    pages = []
    with open(path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"page": i + 1, "text": text.strip()})
    return pages


def extract_text(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return [{"page": 1, "text": text}]


def extract_file(path: str) -> list[dict]:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    elif ext in (".txt", ".md", ".rst", ".csv", ".json"):
        return extract_text(path)
    else:
        print(f"SKIP: unsupported file type {ext} — {path}")
        return []


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


# ── Storage ──────────────────────────────────────────────────────────────────

def get_mem0():
    mem0_key = os.environ.get("MEM0_API_KEY")
    if not mem0_key:
        return None
    try:
        from mem0 import MemoryClient
        return MemoryClient(api_key=mem0_key)
    except ImportError:
        print("WARN: mem0ai not installed. Run: pip install mem0ai")
        return None


def get_astra():
    api_key = os.environ.get("ASTRA_DB_API_KEY")
    endpoint = os.environ.get("ASTRA_DB_ENDPOINT")
    keyspace = os.environ.get("ASTRA_DB_KEYSPACE", "default_keyspace")
    if not api_key or not endpoint:
        return None, None
    try:
        from astrapy import DataAPIClient
        client = DataAPIClient(token=api_key)
        db = client.get_database(endpoint, keyspace=keyspace)
        return db, keyspace
    except Exception as e:
        print(f"WARN: AstraDB unavailable — {e}")
        return None, None


def get_vector_store():
    """Try to get an AstraDB vector store using HuggingFace embeddings (free).
    Falls back to None if sentence-transformers or langchain-astradb not installed.
    Install with: pip install sentence-transformers langchain-astradb
    """
    api_key = os.environ.get("ASTRA_DB_API_KEY")
    endpoint = os.environ.get("ASTRA_DB_ENDPOINT")
    if not api_key or not endpoint:
        return None
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_astradb import AstraDBVectorStore
        print("  Using HuggingFace embeddings (sentence-transformers/all-MiniLM-L6-v2)…")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vs = AstraDBVectorStore(
            embedding=embeddings,
            collection_name="knowledge_base_vectors",
            api_endpoint=endpoint,
            token=api_key,
        )
        return vs
    except ImportError:
        return None  # not installed — silent fallback to Mem0+AstraDB
    except Exception as e:
        print(f"WARN: Vector store unavailable — {e}")
        return None


def store_chunk(mem0, astra_db, chunk_text: str, meta: dict, chunk_id: str, vector_store=None):
    """Store a single chunk in Mem0 and/or AstraDB."""
    content = f"[{meta['filename']} | page {meta['page']} | chunk {meta['chunk']}]\n\n{chunk_text}"

    # Mem0 — stores with embedding for semantic search
    if mem0:
        try:
            mem0.add(
                messages=[{"role": "user", "content": content}],
                user_id="knowledge_base",
                metadata={**meta, "chunk_id": chunk_id},
            )
        except Exception as e:
            print(f"  WARN Mem0: {e}")

    # HuggingFace vector store (best semantic search, free embeddings)
    if vector_store:
        try:
            from langchain_core.documents import Document
            vector_store.add_documents(
                [Document(page_content=chunk_text, metadata={**meta, "chunk_id": chunk_id})],
                ids=[chunk_id],
            )
        except Exception as e:
            print(f"  WARN VectorStore: {e}")

    # AstraDB — structured backup
    if astra_db:
        try:
            col = astra_db.create_collection("knowledge_base", if_not_exists=True)
            col.insert_one({
                "_id": chunk_id,
                "text": chunk_text,
                "content": content,
                "ingested_at": datetime.utcnow().isoformat(),
                **meta,
            })
        except Exception as e:
            print(f"  WARN AstraDB: {e}")


# ── Ingestion ─────────────────────────────────────────────────────────────────

def ingest_file(path: str, mem0, astra_db, vector_store=None):
    filename = Path(path).name
    print(f"\n📄 Ingesting: {filename}")

    pages = extract_file(path)
    if not pages:
        return 0

    total_chunks = 0
    for page_data in pages:
        chunks = chunk_text(page_data["text"])
        for i, chunk in enumerate(chunks):
            meta = {
                "filename": filename,
                "filepath": str(path),
                "page": page_data["page"],
                "chunk": i + 1,
                "total_chunks": len(chunks),
            }
            chunk_id = hashlib.md5(f"{filename}:p{page_data['page']}:c{i}".encode()).hexdigest()
            store_chunk(mem0, astra_db, chunk, meta, chunk_id, vector_store)
            total_chunks += 1
            print(f"  ✓ page {page_data['page']}, chunk {i+1}/{len(chunks)}", end="\r")

    print(f"  ✓ {total_chunks} chunks stored from {len(pages)} page(s)")
    return total_chunks


def list_docs(mem0, astra_db):
    print("\n📚 Knowledge Base Contents\n")

    if astra_db:
        try:
            col = astra_db.get_collection("knowledge_base")
            seen = {}
            for doc in col.find({}, limit=500):
                fn = doc.get("filename", "?")
                if fn not in seen:
                    seen[fn] = {"pages": set(), "chunks": 0}
                seen[fn]["pages"].add(doc.get("page", 0))
                seen[fn]["chunks"] += 1
            if seen:
                for fn, info in sorted(seen.items()):
                    print(f"  {fn}  —  {info['chunks']} chunks, {len(info['pages'])} pages")
            else:
                print("  (empty)")
            return
        except Exception:
            pass

    if mem0:
        try:
            results = mem0.search("document", user_id="knowledge_base", limit=100)
            files = set()
            for r in results:
                meta = r.get("metadata", {})
                if meta.get("filename"):
                    files.add(meta["filename"])
            if files:
                for f in sorted(files):
                    print(f"  {f}")
            else:
                print("  (empty)")
            return
        except Exception as e:
            print(f"  Error: {e}")

    print("  No storage backends available. Check ASTRA_DB_API_KEY or MEM0_API_KEY.")


def clear_knowledge_base(astra_db):
    if astra_db:
        try:
            astra_db.drop_collection("knowledge_base")
            print("✓ AstraDB knowledge_base collection dropped")
        except Exception as e:
            print(f"WARN: {e}")
    print("NOTE: Mem0 memories cannot be bulk-deleted via API. Clear manually in Mem0 dashboard.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    mem0 = get_mem0()
    astra_db, _ = get_astra()
    vector_store = get_vector_store()

    if not mem0 and not astra_db and not vector_store:
        print("ERROR: No storage backend found. Set MEM0_API_KEY and/or ASTRA_DB_API_KEY + ASTRA_DB_ENDPOINT.")
        sys.exit(1)

    print(
        f"Storage: {'Mem0 ✓' if mem0 else 'Mem0 ✗'}  |  "
        f"{'AstraDB ✓' if astra_db else 'AstraDB ✗'}  |  "
        f"{'HuggingFace VectorStore ✓' if vector_store else 'HuggingFace VectorStore ✗ (pip install sentence-transformers langchain-astradb to enable)'}"
    )

    if "--clear" in args:
        clear_knowledge_base(astra_db)
        return

    path_arg = args[0]
    list_mode = "--list" in args

    if list_mode:
        list_docs(mem0, astra_db)
        return

    target = Path(path_arg)
    if not target.exists():
        print(f"ERROR: Path not found: {path_arg}")
        sys.exit(1)

    files = []
    if target.is_dir():
        for ext in ("*.pdf", "*.txt", "*.md", "*.rst"):
            files.extend(target.rglob(ext))
    else:
        files = [target]

    if not files:
        print("No supported files found (.pdf .txt .md .rst)")
        sys.exit(0)

    total = 0
    for f in files:
        total += ingest_file(str(f), mem0, astra_db, vector_store)

    print(f"\n✅ Done — {total} total chunks ingested from {len(files)} file(s)")


if __name__ == "__main__":
    main()