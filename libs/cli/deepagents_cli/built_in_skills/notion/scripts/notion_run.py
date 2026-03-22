#!/usr/bin/env python3
"""
notion_run.py — execute any Notion action via Composio.

Usage:
  python notion_run.py ACTION_SLUG '{"param": "value"}'
  python notion_run.py NOTION_CREATE_NOTION_PAGE '{"parent_id": "...", "title": "My Page"}'
  python notion_run.py --list-actions
"""
import json
import os
import sys


def get_client_and_account():
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        print("ERROR: COMPOSIO_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)
    try:
        from composio import Composio
    except ImportError:
        print("ERROR: composio not installed. Run: pip install composio", file=sys.stderr)
        sys.exit(1)

    client = Composio(api_key=api_key)

    # Find the active Notion connected account
    try:
        accounts = client.connected_accounts.list()
        acc = next(
            (a for a in accounts.items
             if getattr(a.toolkit, "slug", "").lower() == "notion"
             and a.data.get("status") == "ACTIVE"),
            None
        )
    except Exception as e:
        print(f"ERROR: Could not list connected accounts — {e}", file=sys.stderr)
        sys.exit(1)

    if acc is None:
        print("ERROR: No active Notion connection found in Composio.", file=sys.stderr)
        print("Connect Notion at: https://app.composio.dev/connections", file=sys.stderr)
        sys.exit(1)

    return client, acc


def list_actions():
    client, _ = get_client_and_account()
    try:
        tools = client.tools.get_raw_composio_tools(toolkits=["notion"], limit=100)
        print("Available Notion actions:")
        for t in tools:
            print(f"  {t.slug}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def run_action(action_slug: str, arguments: dict):
    client, acc = get_client_and_account()

    print(f"Action : {action_slug}", file=sys.stderr)
    print(f"Args   : {json.dumps(arguments, indent=2)}", file=sys.stderr)
    print(file=sys.stderr)

    try:
        result = client.tools.execute(
            action_slug,
            arguments=arguments,
            connected_account_id=acc.id,
            dangerously_skip_version_check=True,
        )
        output = result if isinstance(result, (dict, list)) else {"result": str(result)}
        print(json.dumps(output, indent=2, default=str))
        return output
    except Exception as e:
        print(f"ERROR: Action failed — {e}", file=sys.stderr)
        sys.exit(1)


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if args[0] == "--list-actions":
        list_actions()
        return

    if len(args) < 1:
        print("Usage: python notion_run.py ACTION_SLUG ['{\"key\": \"value\"}']", file=sys.stderr)
        sys.exit(1)

    action_slug = args[0]
    arguments = {}
    if len(args) >= 2:
        try:
            arguments = json.loads(args[1])
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON arguments — {e}", file=sys.stderr)
            sys.exit(1)

    run_action(action_slug, arguments)


if __name__ == "__main__":
    main()