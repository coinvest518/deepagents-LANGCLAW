"""Composio Health Check + Slug Validator.

Combines two functions:
  #1  Health Check  — pings each connected account with a lightweight test call.
  #5  Slug Validator — checks every action slug in composio_router.py actually
                       exists in the Composio catalog.

Usage:
    # Basic health check (reads COMPOSIO_API_KEY from env):
    python deploy/scripts/composio_health_check.py

    # Validate slugs too (slower — fetches catalog per toolkit):
    python deploy/scripts/composio_health_check.py --validate-slugs

    # Refresh account_id values in composio_routing.json from live API:
    python deploy/scripts/composio_health_check.py --refresh

    # Run against a specific toolkit only:
    python deploy/scripts/composio_health_check.py --toolkit gmail
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make sure the CLI package is importable when run from project root
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[2]
_CLI_SRC = _ROOT / "libs" / "cli"
if str(_CLI_SRC) not in sys.path:
    sys.path.insert(0, str(_CLI_SRC))

# Load .env if dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass  # dotenv not installed — rely on shell env

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from deepagents_cli.composio_router import (  # noqa: E402
    ACTIONS_DEFAULT,
    ACTIONS_PRIMARY,
)

ROUTING_JSON = _ROOT / "deploy" / "composio_routing.json"

# ANSI colours (disabled on Windows if not supported)
_USE_COLOR = sys.stdout.isatty() and os.name != "nt" or os.environ.get("FORCE_COLOR")
GREEN  = "\033[92m" if _USE_COLOR else ""
YELLOW = "\033[93m" if _USE_COLOR else ""
RED    = "\033[91m" if _USE_COLOR else ""
CYAN   = "\033[96m" if _USE_COLOR else ""
RESET  = "\033[0m"  if _USE_COLOR else ""

OK   = f"{GREEN}✅{RESET}"
WARN = f"{YELLOW}⚠️ {RESET}"
FAIL = f"{RED}❌{RESET}"
INFO = f"{CYAN}ℹ️ {RESET}"


def _get_client():
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        print(f"{FAIL} COMPOSIO_API_KEY not set in environment.")
        sys.exit(1)
    from composio import Composio  # type: ignore[import-untyped]
    return Composio(api_key=api_key)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def run_health_check(toolkit_filter: str | None = None) -> dict[str, str]:
    """Ping each toolkit with its test_action. Returns {toolkit: status}."""
    client = _get_client()

    with open(ROUTING_JSON) as f:
        routing = json.load(f)

    results: dict[str, str] = {}
    toolkits = routing["toolkits"]

    if toolkit_filter:
        if toolkit_filter not in toolkits:
            print(f"{FAIL} Unknown toolkit '{toolkit_filter}'")
            sys.exit(1)
        toolkits = {toolkit_filter: toolkits[toolkit_filter]}

    print(f"\n{CYAN}=== Composio Health Check ==={RESET}\n")

    for name, info in toolkits.items():
        account_id = os.environ.get(info["account_id_env"], "")
        test_action = info.get("test_action")

        # Check env var
        if not account_id:
            print(f"  {WARN} {name:20s} — env var {info['account_id_env']} not set")
            results[name] = "no_env"
            continue

        # No test action configured
        if not test_action:
            print(f"  {INFO} {name:20s} — no test action configured (skipped)")
            results[name] = "skipped"
            continue

        # Execute test
        try:
            result = client.tools.execute(
                test_action,
                arguments=info.get("test_args", {}),
                connected_account_id=account_id,
                dangerously_skip_version_check=True,
            )
            # A result with "error" key at top level = failed
            if isinstance(result, dict) and result.get("error"):
                err = str(result["error"])[:120]
                print(f"  {FAIL} {name:20s} — {err}")
                results[name] = "error"
            else:
                print(f"  {OK} {name:20s} — OK")
                results[name] = "ok"
        except Exception as exc:
            short = str(exc)[:120]
            print(f"  {FAIL} {name:20s} — {short}")
            results[name] = "exception"

    # Summary
    counts = {}
    for s in results.values():
        counts[s] = counts.get(s, 0) + 1
    print(f"\nSummary: {counts}\n")
    return results


# ---------------------------------------------------------------------------
# Slug validator (#5)
# ---------------------------------------------------------------------------

def run_slug_validator() -> bool:
    """Check every action in ACTIONS_PRIMARY + ACTIONS_DEFAULT exists in catalog."""
    client = _get_client()
    print(f"\n{CYAN}=== Slug Validator ==={RESET}\n")

    all_actions = ACTIONS_PRIMARY + ACTIONS_DEFAULT
    # Get unique toolkits implied by the slugs (first word before _)
    toolkits_needed: set[str] = set()
    for action in all_actions:
        # Map prefix → composio toolkit name
        _prefix_map = {
            "gmail": "gmail", "github": "github",
            "googledrive": "googledrive", "googledocs": "googledocs",
            "googlesheets": "googlesheets", "googleanalytics": "googleanalytics",
            "linkedin": "linkedin", "twitter": "twitter",
            "telegram": "telegram", "instagram": "instagram",
            "facebook": "facebook", "youtube": "youtube",
            "slack": "slack", "notion": "notion", "dropbox": "dropbox",
            "serpapi": "serpapi",
        }
        # Find longest matching prefix
        matched = None
        for p, tk in _prefix_map.items():
            if action.lower().startswith(p):
                if matched is None or len(p) > len(matched[0]):
                    matched = (p, tk)
        if matched:
            toolkits_needed.add(matched[1])

    # Fetch catalog slugs per toolkit
    catalog: dict[str, set[str]] = {}
    for tk in sorted(toolkits_needed):
        try:
            tools = client.tools.get_raw_composio_tools(toolkits=[tk], limit=200)
            catalog[tk] = {t.slug for t in tools}
        except Exception as exc:
            print(f"  {WARN} Could not fetch catalog for '{tk}': {exc}")
            catalog[tk] = set()

    # Validate each slug
    all_ok = True
    for action in sorted(all_actions):
        matched_tk = None
        for tk in catalog:
            if action.lower().startswith(tk.lower()):
                if matched_tk is None or len(tk) > len(matched_tk):
                    matched_tk = tk
        if matched_tk is None:
            print(f"  {WARN} {action} — toolkit not in catalog fetch list")
            continue
        if action in catalog[matched_tk]:
            print(f"  {OK} {action}")
        else:
            print(f"  {FAIL} {action} — NOT FOUND in {matched_tk} catalog")
            all_ok = False

    if all_ok:
        print(f"\n{OK} All slugs valid.\n")
    else:
        print(f"\n{FAIL} Some slugs are invalid — fix them in composio_router.py\n")
    return all_ok


# ---------------------------------------------------------------------------
# Refresh: write live account_id values back to composio_routing.json
# ---------------------------------------------------------------------------

def run_refresh() -> None:
    """Fetch live account list and update account_id fields in composio_routing.json."""
    client = _get_client()
    print(f"\n{CYAN}=== Refreshing composio_routing.json ==={RESET}\n")

    with open(ROUTING_JSON) as f:
        routing = json.load(f)

    try:
        accounts = client.connected_accounts.list()
    except Exception as exc:
        print(f"{FAIL} Could not list accounts: {exc}")
        sys.exit(1)

    # Build map: toolkit_slug → list of account_ids
    from_api: dict[str, list[str]] = {}
    for acc in accounts:
        tk = getattr(acc, "appName", None) or getattr(acc, "app_name", None) or ""
        tk = tk.lower().replace("-", "_").replace(" ", "_")
        aid = getattr(acc, "id", None) or getattr(acc, "connectedAccountId", "")
        entity = getattr(acc, "clientUniqueUserId", "")
        if aid:
            from_api.setdefault(tk, []).append((aid, entity))
            print(f"  {INFO} {tk:20s} entity={entity}  id={aid}")

    # Update routing JSON
    changed = 0
    for toolkit_name, info in routing["toolkits"].items():
        env_var = info.get("account_id_env", "")
        current = os.environ.get(env_var, "")
        # Try to find matching account
        api_entries = from_api.get(toolkit_name, [])
        if api_entries:
            # Prefer entry whose id matches existing env var, else use first
            match = next((a for a, _ in api_entries if a == current), api_entries[0][0])
            if match != info.get("account_id"):
                print(f"  {YELLOW}Updated{RESET} {toolkit_name}: {info.get('account_id')} → {match}")
                info["account_id"] = match
                changed += 1

    with open(ROUTING_JSON, "w") as f:
        json.dump(routing, f, indent=2)

    print(f"\n{OK} Done. {changed} account_id(s) updated in composio_routing.json\n")
    if changed > 0:
        print(f"{WARN} Remember to also update .env and composio_router.py if IDs changed.\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Composio Health Check + Slug Validator"
    )
    parser.add_argument(
        "--validate-slugs", action="store_true",
        help="Also validate all action slugs against the Composio catalog (slower)."
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Refresh account_id values in composio_routing.json from live API."
    )
    parser.add_argument(
        "--toolkit", metavar="NAME",
        help="Only check a specific toolkit (e.g. gmail, slack)."
    )
    args = parser.parse_args()

    if args.refresh:
        run_refresh()
        return

    run_health_check(toolkit_filter=args.toolkit)

    if args.validate_slugs:
        run_slug_validator()


if __name__ == "__main__":
    main()