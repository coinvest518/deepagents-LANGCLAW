"""
test_system.py — Verify the FDWA agent system works end-to-end.

Tests:
1. Composio connection + Notion page creation
2. Skills loading (composio skill visible)
3. web_search works without Pydantic errors
4. write_todos arg coercion works
5. Local LangGraph server (if running)

Run:  python deploy/test_system.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent / "libs/cli"))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs/deepagents"))


PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"


# ---------------------------------------------------------------------------
# Test 1: Composio direct connection
# ---------------------------------------------------------------------------

def test_composio_connection() -> tuple[bool, str]:
    """Test that Composio is configured and connected."""
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        return False, "COMPOSIO_API_KEY not set"
    try:
        from composio import Composio
        client = Composio(api_key=api_key)
        accounts = client.connected_accounts.list()
        slugs = [
            getattr(a.toolkit, "slug", "?")
            for a in (accounts.items or [])
            if a.data.get("status") == "ACTIVE"
        ]
        if not slugs:
            return False, "No active connected accounts"
        return True, f"Connected: {', '.join(slugs)}"
    except Exception as exc:
        return False, str(exc)


def test_notion_via_composio() -> tuple[bool, str]:
    """Create a test Notion page via Composio."""
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        return False, "COMPOSIO_API_KEY not set — skip"
    try:
        from composio import Composio
        client = Composio(api_key=api_key)
        accounts = client.connected_accounts.list()
        notion_acc = next(
            (a for a in (accounts.items or [])
             if getattr(a.toolkit, "slug", "") == "notion"
             and a.data.get("status") == "ACTIVE"),
            None,
        )
        if notion_acc is None:
            return False, "Notion not connected in Composio"

        result = client.tools.execute(
            "NOTION_CREATE_A_PAGE",
            arguments={
                "title": "FDWA System Test",
                "content": f"Auto-test at {time.strftime('%Y-%m-%d %H:%M:%S')}. If you see this, Composio + Notion is working.",
            },
            connected_account_id=notion_acc.id,
            dangerously_skip_version_check=True,
        )
        return True, f"Notion page created: {result}"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Test 2: web_search without Pydantic error
# ---------------------------------------------------------------------------

def test_web_search() -> tuple[bool, str]:
    """Verify web_search works without session_params/crawl_params."""
    try:
        from deepagents_cli.tools import web_search
        import inspect
        sig = inspect.signature(web_search)
        params = list(sig.parameters.keys())
        if "session_params" in params or "crawl_params" in params:
            return False, f"session_params/crawl_params still in signature: {params}"

        # Check Tavily key
        tavily_key = os.environ.get("TAVILY_API_KEY", "")
        if not tavily_key:
            return True, "Signature clean (no session_params/crawl_params). Tavily key not set — skip live test"

        result = web_search("FDWA Futuristic Digital Wealth Agency", max_results=2)
        if "error" in result:
            return False, f"Search error: {result['error']}"
        n = len(result.get("results", []))
        return True, f"Search returned {n} results"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Test 3: write_todos arg coercion
# ---------------------------------------------------------------------------

def test_write_todos_coercion() -> tuple[bool, str]:
    """Verify PatchToolCallsMiddleware coerces string todos to list."""
    try:
        from deepagents.middleware.patch_tool_calls import _coerce_tool_call_args
        # Simulate what the LLM sends
        bad_call = {
            "name": "write_todos",
            "id": "call_123",
            "args": {
                "todos": '[{"content": "Test task", "status": "pending"}]'
            },
        }
        fixed = _coerce_tool_call_args(bad_call)
        todos = fixed["args"]["todos"]
        if not isinstance(todos, list):
            return False, f"Expected list, got {type(todos)}: {todos}"
        if todos[0].get("content") != "Test task":
            return False, f"Wrong content after coercion: {todos}"
        return True, f"Coerced correctly: {todos}"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Test 4: Skills loading — composio skill visible
# ---------------------------------------------------------------------------

def test_skills_loading() -> tuple[bool, str]:
    """Check composio skill is discoverable."""
    try:
        from deepagents_cli.config import settings
        built_in = settings.get_built_in_skills_dir()
        composio_skill = Path(built_in) / "composio" / "SKILL.md"
        if not composio_skill.exists():
            return False, f"Composio SKILL.md not found at {composio_skill}"

        content = composio_skill.read_text()
        if "googlesheets" not in content.lower():
            return False, "Composio SKILL.md doesn't mention googlesheets"
        return True, f"Composio skill found at {composio_skill}"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Test 5: Local LangGraph server ping
# ---------------------------------------------------------------------------

async def test_langgraph_server() -> tuple[bool, str]:
    """Ping local LangGraph server and send a simple message."""
    import httpx
    base = os.environ.get("LANGGRAPH_API_URL", "http://127.0.0.1:2024")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base}/ok")
            if resp.status_code != 200:
                return False, f"Server returned {resp.status_code}"
        return True, f"Server up at {base}"
    except Exception as exc:
        return False, f"Server not reachable at {base}: {exc}"


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

async def main() -> None:
    print("\n=== FDWA System Test ===\n")

    results = []

    def run(name: str, fn):
        ok, msg = fn()
        icon = PASS if ok else FAIL
        print(f"{icon} {name}: {msg}")
        results.append(ok)

    run("Composio connection", test_composio_connection)
    run("Notion page (Composio)", test_notion_via_composio)
    run("web_search signature", test_web_search)
    run("write_todos coercion", test_write_todos_coercion)
    run("Skills loading", test_skills_loading)

    ok, msg = await test_langgraph_server()
    icon = PASS if ok else FAIL
    print(f"{icon} LangGraph server: {msg}")
    results.append(ok)

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*30}")
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("Fix failing tests before deploying.\n")
        sys.exit(1)
    else:
        print("All good — ready to deploy.\n")


if __name__ == "__main__":
    # Load .env if present
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    asyncio.run(main())
