"""
create_composio_skills.py — Auto-create skill files for new Composio connections.

Run after adding a new Composio connected account:
    python deploy/scripts/create_composio_skills.py

For each active connection that doesn't have a skill file, this script:
  1. Fetches the top 15 action slugs for that toolkit
  2. Generates a SKILL.md in built_in_skills/<toolkit>/
  3. Updates the Composio SKILL.md direct-tools list if needed
  4. Optionally updates .env with the new account ID

Usage:
    python deploy/scripts/create_composio_skills.py           # dry-run
    python deploy/scripts/create_composio_skills.py --write   # write files
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Load .env
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

SKILLS_DIR = Path(__file__).parent.parent.parent / "libs/cli/deepagents_cli/built_in_skills"

TEMPLATE = """\
---
name: {toolkit}
description: Interact with {toolkit_title} via Composio. Pre-authenticated — execute actions directly without OAuth. Account ID is pre-loaded in env.
---

# {toolkit_title} Skill

## Execute actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["{env_var}"]

result = client.tools.execute(
    "{first_action}",
    arguments={{}},   # fill in required args
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Available actions (top {n_actions})

{action_list}

## Discover more actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["{toolkit}"], limit=20)
for t in tools:
    print(t.slug)
```

## Rules
- Use `{env_var}` env var — never call `accounts.list()`
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
"""


def get_active_accounts(api_key: str) -> list[dict]:
    from composio import Composio
    client = Composio(api_key=api_key)
    accounts = client.connected_accounts.list()
    result = []
    for a in accounts.items or []:
        slug = getattr(a.toolkit, "slug", "unknown")
        status = a.data.get("status", "?")
        if status == "ACTIVE":
            result.append({"slug": slug, "id": a.id})
    return result


def get_top_actions(api_key: str, toolkit: str, limit: int = 15) -> list[str]:
    from composio import Composio
    client = Composio(api_key=api_key)
    try:
        tools = client.tools.get_raw_composio_tools(toolkits=[toolkit], limit=limit)
        return [t.slug for t in tools]
    except Exception as e:
        print(f"  WARNING: Could not fetch actions for {toolkit}: {e}")
        return []


def skill_exists(toolkit: str) -> bool:
    skill_file = SKILLS_DIR / toolkit / "SKILL.md"
    return skill_file.exists()


def create_skill(toolkit: str, account_id: str, actions: list[str], write: bool) -> None:
    env_var = f"COMPOSIO_{toolkit.upper().replace('-', '_')}_ACCOUNT_ID"
    toolkit_title = toolkit.replace("-", " ").replace("_", " ").title()
    first_action = actions[0] if actions else f"{toolkit.upper()}_EXAMPLE_ACTION"
    action_list = "\n".join(f"- `{a}`" for a in actions)

    content = TEMPLATE.format(
        toolkit=toolkit,
        toolkit_title=toolkit_title,
        env_var=env_var,
        first_action=first_action,
        n_actions=len(actions),
        action_list=action_list,
    )

    skill_dir = SKILLS_DIR / toolkit
    skill_file = skill_dir / "SKILL.md"

    if write:
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content)
        print(f"  CREATED: {skill_file}")
    else:
        print(f"  DRY-RUN: would create {skill_file}")
        print(f"  First 300 chars:\n{content[:300]}\n")


def update_env_var(toolkit: str, account_id: str, write: bool) -> None:
    env_var = f"COMPOSIO_{toolkit.upper().replace('-', '_')}_ACCOUNT_ID"
    current = os.environ.get(env_var)
    if current == account_id:
        return  # already set

    if write:
        with open(env_file, "a") as f:
            f.write(f"\n{env_var}={account_id}\n")
        print(f"  APPENDED to .env: {env_var}={account_id}")
    else:
        print(f"  DRY-RUN: would append to .env: {env_var}={account_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write files (default: dry-run)")
    args = parser.parse_args()

    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        print("ERROR: COMPOSIO_API_KEY not set")
        sys.exit(1)

    print("Fetching active Composio accounts...")
    accounts = get_active_accounts(api_key)
    print(f"Found {len(accounts)} active account(s)\n")

    new_count = 0
    for acc in accounts:
        toolkit = acc["slug"]
        account_id = acc["id"]

        if skill_exists(toolkit):
            print(f"SKIP {toolkit}: skill already exists")
            continue

        print(f"NEW: {toolkit} (id={account_id})")
        actions = get_top_actions(api_key, toolkit)
        create_skill(toolkit, account_id, actions, write=args.write)
        update_env_var(toolkit, account_id, write=args.write)
        new_count += 1

    print(f"\nDone: {new_count} new skill(s) {'created' if args.write else 'would be created'}")
    if not args.write and new_count > 0:
        print("Run with --write to actually create files.")


if __name__ == "__main__":
    main()
