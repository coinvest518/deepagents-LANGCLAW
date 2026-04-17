"""LangSmith query tools for the ops-monitor sub-agent.

Provides tools to query LangSmith for run data, error rates, model usage,
and sub-agent activity.  Used by the ops-monitor sub-agent to monitor
system health and report on agent activity.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_LS_KEY = os.environ.get("LANGSMITH_API_KEY", "")
_LS_PROJECT = os.environ.get("LANGSMITH_PROJECT", "deeperagents")
_BASE = "https://api.smith.langchain.com/api/v1"

# Cache session ID
_session_id: str | None = None


def _headers() -> dict[str, str]:
    return {"x-api-key": _LS_KEY, "Content-Type": "application/json"}


def _get_session_id() -> str | None:
    global _session_id
    if _session_id:
        return _session_id
    if not _LS_KEY:
        return None
    try:
        resp = httpx.get(
            f"{_BASE}/sessions?name={_LS_PROJECT}",
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            sessions = resp.json()
            match = next((s for s in sessions if s.get("name") == _LS_PROJECT), None)
            if match:
                _session_id = match["id"]
                return _session_id
    except Exception:
        logger.warning("Failed to look up LangSmith session", exc_info=True)
    return None


def _query_runs(
    *,
    limit: int = 25,
    is_root: bool = True,
    start_time: str | None = None,
) -> list[dict[str, Any]]:
    """Query LangSmith runs for the project."""
    session_id = _get_session_id()
    if not session_id:
        return []

    body: dict[str, Any] = {
        "session": [session_id],
        "limit": limit,
        "is_root": is_root,
    }
    if start_time:
        body["start_time"] = start_time

    try:
        resp = httpx.post(
            f"{_BASE}/runs/query",
            headers=_headers(),
            json=body,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("runs", [])
    except Exception:
        logger.warning("Failed to query LangSmith runs", exc_info=True)
    return []


def _format_run(run: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a LangSmith run."""
    total_tokens = run.get("total_tokens") or 0
    prompt_tokens = run.get("prompt_tokens") or 0
    completion_tokens = run.get("completion_tokens") or 0
    start = run.get("start_time", "")
    end = run.get("end_time")
    latency = 0.0
    if start and end:
        try:
            s = datetime.fromisoformat(start.replace("Z", "+00:00"))
            e = datetime.fromisoformat(end.replace("Z", "+00:00"))
            latency = round((e - s).total_seconds(), 2)
        except Exception:
            pass

    # Extract model from metadata
    model = ""
    extra = run.get("extra", {}) or {}
    metadata = extra.get("metadata", {}) or {}
    model = metadata.get("ls_model_name", "") or metadata.get("model_name", "")

    return {
        "id": run.get("id", ""),
        "name": run.get("name", ""),
        "run_type": run.get("run_type", ""),
        "status": run.get("status", ""),
        "latency_s": latency,
        "model": model,
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "error": run.get("error"),
        "parent_run_id": run.get("parent_run_id"),
    }


@tool
def langsmith_recent_runs(limit: int = 15) -> str:
    """Get recent agent runs from LangSmith tracing.

    Returns the most recent root-level runs with their status, latency,
    model, token usage, and any errors.

    Args:
        limit: Number of recent runs to fetch (default 15, max 50).

    Returns:
        JSON string with list of recent runs and summary stats.
    """
    if not _LS_KEY:
        return json.dumps({"error": "LANGSMITH_API_KEY not configured"})

    limit = min(limit, 50)
    runs = _query_runs(limit=limit)
    formatted = [_format_run(r) for r in runs]

    # Compute summary stats
    total_tokens = sum(r["total_tokens"] for r in formatted)
    errors = sum(1 for r in formatted if r["status"] == "error")
    models_used = {}
    for r in formatted:
        if r["model"]:
            models_used[r["model"]] = models_used.get(r["model"], 0) + 1
    avg_latency = (
        round(sum(r["latency_s"] for r in formatted) / len(formatted), 2)
        if formatted
        else 0
    )

    return json.dumps({
        "summary": {
            "total_runs": len(formatted),
            "total_tokens": total_tokens,
            "errors": errors,
            "error_rate": f"{errors/len(formatted)*100:.1f}%" if formatted else "0%",
            "avg_latency_s": avg_latency,
            "models_used": models_used,
        },
        "runs": formatted,
    }, default=str)


@tool
def langsmith_check_errors(hours: int = 24) -> str:
    """Check for error spikes in recent agent runs.

    Looks at runs from the last N hours and reports error rate,
    most common errors, and which models/tools are failing.

    Args:
        hours: How many hours back to check (default 24).

    Returns:
        JSON with error analysis and recommendations.
    """
    if not _LS_KEY:
        return json.dumps({"error": "LANGSMITH_API_KEY not configured"})

    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    runs = _query_runs(limit=50, start_time=start)
    formatted = [_format_run(r) for r in runs]

    total = len(formatted)
    errors = [r for r in formatted if r["status"] == "error"]
    error_rate = len(errors) / total * 100 if total else 0

    # Group errors by type
    error_messages: dict[str, int] = {}
    error_models: dict[str, int] = {}
    for e in errors:
        msg = (e.get("error") or "unknown")[:100]
        error_messages[msg] = error_messages.get(msg, 0) + 1
        if e["model"]:
            error_models[e["model"]] = error_models.get(e["model"], 0) + 1

    alert = error_rate > 20
    return json.dumps({
        "period_hours": hours,
        "total_runs": total,
        "error_count": len(errors),
        "error_rate": f"{error_rate:.1f}%",
        "alert": alert,
        "alert_message": f"ERROR SPIKE: {error_rate:.0f}% error rate in last {hours}h" if alert else None,
        "top_errors": dict(sorted(error_messages.items(), key=lambda x: -x[1])[:5]),
        "failing_models": error_models,
        "recommendation": (
            "Error rate is high. Check model availability and API keys."
            if alert
            else "System is healthy."
        ),
    }, default=str)


@tool
def langsmith_subagent_activity() -> str:
    """Get sub-agent activity from LangSmith traces.

    Shows which sub-agents have been active, their run counts,
    success rates, and token usage.

    Returns:
        JSON with sub-agent breakdown and activity summary.
    """
    if not _LS_KEY:
        return json.dumps({"error": "LANGSMITH_API_KEY not configured"})

    # Get root runs AND child runs
    root_runs = _query_runs(limit=25, is_root=True)
    child_runs = _query_runs(limit=50, is_root=False)

    root_formatted = [_format_run(r) for r in root_runs]
    child_formatted = [_format_run(r) for r in child_runs]

    # Group children by parent
    parent_map: dict[str, list[dict[str, Any]]] = {}
    for child in child_formatted:
        pid = child.get("parent_run_id")
        if pid:
            parent_map.setdefault(pid, []).append(child)

    # Identify sub-agent patterns
    subagent_stats: dict[str, dict[str, Any]] = {}
    for child in child_formatted:
        name = child["name"]
        if name not in subagent_stats:
            subagent_stats[name] = {
                "runs": 0,
                "errors": 0,
                "total_tokens": 0,
                "models": set(),
            }
        subagent_stats[name]["runs"] += 1
        if child["status"] == "error":
            subagent_stats[name]["errors"] += 1
        subagent_stats[name]["total_tokens"] += child["total_tokens"]
        if child["model"]:
            subagent_stats[name]["models"].add(child["model"])

    # Serialize sets to lists
    result = {}
    for name, stats in subagent_stats.items():
        result[name] = {
            **stats,
            "models": list(stats["models"]),
            "success_rate": f"{(1 - stats['errors']/stats['runs'])*100:.0f}%" if stats["runs"] else "N/A",
        }

    # Active runs (status == "running")
    active = [r for r in root_formatted + child_formatted if r["status"] == "running"]

    return json.dumps({
        "active_runs": len(active),
        "active_run_details": active[:10],
        "subagent_breakdown": result,
        "total_root_runs": len(root_formatted),
        "total_child_runs": len(child_formatted),
    }, default=str)
