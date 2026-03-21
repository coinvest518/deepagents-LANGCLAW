"""
Composio connection test script.

Run with:
    python scripts/test_composio.py

Requires COMPOSIO_API_KEY in environment or .env file.
Tests all connected accounts and executes a live Gmail fetch.
"""

from __future__ import annotations

import os
import sys

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main() -> None:
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        print("ERROR: COMPOSIO_API_KEY not set in environment or .env")
        sys.exit(1)

    print(f"COMPOSIO_API_KEY: {api_key[:12]}...")
    print()

    try:
        from composio import Composio
    except ImportError:
        print("ERROR: composio package not installed. Run: pip install composio")
        sys.exit(1)

    client = Composio(api_key=api_key)
    print("Composio client: OK")
    print()

    # ── Connected accounts ────────────────────────────────────────────────────
    print("=== Connected Accounts ===")
    accounts = client.connected_accounts.list()
    items = accounts.items if hasattr(accounts, "items") else []
    active_by_toolkit: dict[str, str] = {}  # slug → account_id

    for acc in items:
        slug = str(getattr(acc.toolkit, "slug", "unknown")) if hasattr(acc, "toolkit") else "unknown"
        status = acc.data.get("status", "?") if isinstance(getattr(acc, "data", None), dict) else "?"
        print(f"  {slug:20} {status:10} {acc.id}")
        if status == "ACTIVE":
            active_by_toolkit[slug] = acc.id

    print()
    print(f"Active toolkits: {list(active_by_toolkit.keys())}")
    print()

    # ── List tools for each active toolkit ───────────────────────────────────
    print("=== Available Tools Per Toolkit ===")
    for slug in list(active_by_toolkit.keys())[:4]:  # sample first 4
        try:
            raw = client.tools.get_raw_composio_tools(toolkits=[slug], limit=6)
            names = [getattr(t, "slug", "?") for t in raw]
            print(f"  {slug}: {len(raw)} tools — {names[:6]}")
        except Exception as e:
            print(f"  {slug}: error — {e}")
    print()

    # ── Live action: fetch recent Gmail ───────────────────────────────────────
    if "gmail" in active_by_toolkit:
        print("=== Live Test: GMAIL_FETCH_EMAILS ===")
        try:
            # Get gmail toolkit version
            toolkits = client.toolkits.list()
            tk_items = toolkits.items if hasattr(toolkits, "items") else []
            gmail_tk = next(
                (t for t in tk_items if getattr(t, "slug", "") == "gmail"), None
            )
            version = gmail_tk.meta.version if gmail_tk and hasattr(gmail_tk, "meta") else None

            result = client.tools.execute(
                "GMAIL_FETCH_EMAILS",
                arguments={"max_results": 3, "label_ids": ["INBOX"]},
                connected_account_id=active_by_toolkit["gmail"],
                version=version,
            )

            data = result if isinstance(result, dict) else getattr(result, "data", {})
            messages = data.get("messages", []) if isinstance(data, dict) else []
            print(f"  Fetched {len(messages)} message(s) from inbox")
            for msg in messages[:3]:
                subj = msg.get("subject", "(no subject)")[:60] if isinstance(msg, dict) else str(msg)[:60]
                frm = msg.get("sender", msg.get("from", "?"))[:40] if isinstance(msg, dict) else ""
                print(f"    From: {frm}")
                print(f"    Subject: {subj}")
                print()
        except Exception as e:
            print(f"  Gmail fetch error: {e}")
    else:
        print("  Gmail not connected — skipping live test")

    print("=== Test Complete ===")
    print()
    print("Your agent has access to these toolkits via the Composio skill:")
    for slug in active_by_toolkit:
        print(f"  - {slug}")
    print()
    print("To use in agent: the Composio skill is at:")
    print("  libs/cli/deepagents_cli/built_in_skills/composio/")
    print("  Agent will use it when it sees tasks involving Gmail, LinkedIn,")
    print("  Google Sheets, Twitter, Telegram, Google Drive, etc.")


if __name__ == "__main__":
    main()
