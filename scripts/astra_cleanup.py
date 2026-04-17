"""AstraDB keyspace inspector + cleanup tool.

AstraDB free tier caps each keyspace at 100 Storage Attached Indexes.
Each collection costs ~4 indexes, so ~25 collections before new ones
fail to create. This script lists every collection, shows its doc count
and size, and lets you drop the ones you don't need anymore.

Usage:
    .venv/Scripts/python scripts/astra_cleanup.py              # list only
    .venv/Scripts/python scripts/astra_cleanup.py --delete X   # delete by name
    .venv/Scripts/python scripts/astra_cleanup.py --keep agent_tasks,conversation_history,mem0_*
                                                               # interactive purge of rest

Requires ASTRA_DB_API_KEY and ASTRA_DB_ENDPOINT in .env.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_REPO / ".env", override=False)
except ImportError:
    pass


def _get_db():
    api_key = os.environ.get("ASTRA_DB_API_KEY")
    endpoint = os.environ.get("ASTRA_DB_ENDPOINT")
    keyspace = os.environ.get("ASTRA_DB_KEYSPACE", "default_keyspace")
    if not api_key or not endpoint:
        print("ERROR: ASTRA_DB_API_KEY / ASTRA_DB_ENDPOINT not set in .env")
        sys.exit(1)
    try:
        from astrapy import DataAPIClient
    except ImportError:
        print("ERROR: pip install astrapy")
        sys.exit(1)
    return DataAPIClient(token=api_key).get_database(endpoint, keyspace=keyspace), keyspace


def list_collections(db, keyspace: str) -> list[dict]:
    """Return [{name, count}, ...] for every collection in the keyspace."""
    rows: list[dict] = []
    for name in db.list_collection_names():
        count = "?"
        try:
            col = db.get_collection(name)
            # estimated_document_count is cheap; exact count can scan the collection
            try:
                count = col.estimated_document_count()
            except Exception:
                count = col.count_documents({}, upper_bound=10_000)
        except Exception as exc:
            count = f"err: {exc!s:.40}"
        rows.append({"name": name, "count": count})
    return rows


def print_table(rows: list[dict], keyspace: str) -> None:
    print(f"\nKeyspace: {keyspace}")
    print(f"Collections: {len(rows)}   (cap ~25 before 100-index limit)\n")
    print(f"  {'#':>3}  {'COLLECTION':<40} {'DOCS':>10}")
    print(f"  {'-'*3}  {'-'*40} {'-'*10}")
    for i, r in enumerate(rows, 1):
        print(f"  {i:>3}  {r['name']:<40} {str(r['count']):>10}")
    print()


def delete_one(db, name: str) -> bool:
    try:
        db.drop_collection(name)
        print(f"  DROPPED: {name}")
        return True
    except Exception as exc:
        print(f"  FAILED to drop {name!r}: {exc}")
        return False


def matches_pattern(name: str, patterns: list[str]) -> bool:
    """Simple glob match — supports trailing '*' only. keep=agent_tasks,mem0_*"""
    for p in patterns:
        p = p.strip()
        if not p:
            continue
        if p.endswith("*"):
            if name.startswith(p[:-1]):
                return True
        elif name == p:
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--delete", metavar="NAME", help="Drop one collection by name and exit.")
    parser.add_argument("--keep", metavar="LIST", help="Comma-separated collection names/prefixes to KEEP. Everything else is offered for deletion one-by-one.")
    parser.add_argument("--yes", action="store_true", help="Skip per-collection confirmation when using --keep.")
    args = parser.parse_args()

    db, keyspace = _get_db()
    rows = list_collections(db, keyspace)
    print_table(rows, keyspace)

    if args.delete:
        if not any(r["name"] == args.delete for r in rows):
            print(f"No collection named {args.delete!r} in keyspace {keyspace!r}.")
            sys.exit(1)
        confirm = input(f"Drop {args.delete!r} from {keyspace!r}? [y/N]: ").strip().lower()
        if confirm == "y":
            delete_one(db, args.delete)
        else:
            print("Aborted.")
        return

    if args.keep:
        keep = [p.strip() for p in args.keep.split(",") if p.strip()]
        to_offer = [r for r in rows if not matches_pattern(r["name"], keep)]
        if not to_offer:
            print(f"Nothing to delete — all {len(rows)} collections matched the keep list.")
            return
        print(f"KEEP patterns: {keep}")
        print(f"Candidates for deletion: {len(to_offer)}\n")
        for r in to_offer:
            if args.yes:
                ok = True
            else:
                ans = input(f"  Drop {r['name']!r} (docs={r['count']})? [y/N/q]: ").strip().lower()
                if ans == "q":
                    print("Stopped.")
                    break
                ok = ans == "y"
            if ok:
                delete_one(db, r["name"])
        return

    # No action args — just listed collections above.
    print("No action specified. Use --delete NAME or --keep LIST. See --help.")


if __name__ == "__main__":
    main()
