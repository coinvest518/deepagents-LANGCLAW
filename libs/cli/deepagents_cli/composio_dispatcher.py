"""Lightweight Composio dispatcher used by agents.

Provides a small, defensive helper to execute Composio actions via the
Composio HTTP execute endpoint. Returns a consistent shape so calling
code can handle failures gracefully.
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

try:
    import requests
except Exception:  # pragma: no cover - network optional
    requests = None


_SERVICE_ACCOUNT_OVERRIDES: Dict[str, str] = {
    # Google Sheets native token is broken — use the Google Drive OAuth account
    "GOOGLESHEETS": "COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID",
}


def _resolve_account_for_service(action_slug: str) -> Optional[str]:
    """Resolve an account env var based on the action slug prefix.

    Example: GMAIL_SEND_EMAIL -> COMPOSIO_GMAIL_ACCOUNT_ID

    Some services need a different account (e.g. Google Sheets uses Drive OAuth).
    """
    if not action_slug or "_" not in action_slug:
        return None
    service = action_slug.split("_", 1)[0].upper()
    env_key = _SERVICE_ACCOUNT_OVERRIDES.get(service, f"COMPOSIO_{service}_ACCOUNT_ID")
    return os.environ.get(env_key)


def dispatch(action_slug: str, arguments: Dict[str, Any], hint_account_env: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Dispatch a Composio action.

    Returns a dict with `success`, and either `result` or `error`.
    """
    api_key = os.environ.get("COMPOSIO_API_KEY")
    api_url = os.environ.get("COMPOSIO_API_URL")

    if not api_key or not api_url:
        return {"success": False, "error": "COMPOSIO not configured (COMPOSIO_API_KEY or COMPOSIO_API_URL missing)"}

    account_id = None
    if hint_account_env:
        account_id = os.environ.get(hint_account_env)
    if not account_id:
        account_id = _resolve_account_for_service(action_slug)

    payload = {"action": action_slug, "arguments": arguments}
    if account_id:
        payload["account_id"] = account_id

    if requests is None:
        return {"success": False, "error": "requests library not available to call Composio API"}

    try:
        resp = requests.post(
            f"{api_url.rstrip('/')}/v1/execute",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"status_code": resp.status_code, "text": resp.text}

        if 200 <= resp.status_code < 300:
            return {"success": True, "result": data}
        return {"success": False, "error": f"Composio error: status={resp.status_code} body={data}"}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


# Compatibility wrappers expected by the CLI/tooling: `composio_action` and `composio_get_schema`.
def _maybe_tool_decorator():
    try:
        from langchain_core.tools import tool
        return tool
    except Exception:
        return lambda f: f


@_maybe_tool_decorator()
def composio_get_schema(action: str) -> str:
    """Return a compact JSON schema for an action, or an error string.

    Only call this when the action slug is NOT documented in the loaded skill file.
    If the skill file already lists parameters for the action, call composio_action directly.
    """
    try:
        from composio import Composio  # type: ignore
    except Exception:
        return "ERROR: composio SDK not installed"

    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        return "ERROR: COMPOSIO_API_KEY not set"

    try:
        client = Composio(api_key=api_key)
        raw = client.tools.get_raw_composio_tool_by_slug(action)
        # try to extract input_parameters
        params = getattr(raw, "input_parameters", None)
        if params is None and isinstance(raw, dict):
            params = raw.get("input_parameters", {})
        if hasattr(params, "__dict__"):
            params = params.__dict__
        out = {"action": action, "parameters": params if params is not None else {}}
        return json.dumps(out, default=str)
    except Exception as exc:
        return f"ERROR: Could not get schema for {action}: {exc}"


@_maybe_tool_decorator()
def composio_action(action: str, arguments: dict | str | None = None) -> str:
    """Execute a composio action (compat wrapper).

    Uses the Composio Python SDK to execute the action, automatically resolving
    the connected account ID from the environment.

    Returns a JSON string on success or an error string starting with ERROR:.
    """
    try:
        from composio import Composio  # type: ignore
    except Exception:
        return "ERROR: composio SDK not installed"

    # Coerce argument shapes
    if isinstance(arguments, str):
        s = arguments.strip()
        if s in ("", "null", "none", "undefined"):
            arguments = {}
        else:
            try:
                arguments = json.loads(s)
            except Exception:
                arguments = {}
    if arguments is None:
        arguments = {}

    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        return "ERROR: COMPOSIO_API_KEY not set"

    account_id = _resolve_account_for_service(action)

    try:
        client = Composio(api_key=api_key)
        kwargs: Dict[str, Any] = {"dangerously_skip_version_check": True}
        if account_id:
            kwargs["connected_account_id"] = account_id
        result = client.tools.execute(action, arguments=arguments, **kwargs)
        try:
            return json.dumps(result, default=str)
        except Exception:
            return str(result)
    except Exception as exc:
        return f"ERROR: Composio error: {exc}"
