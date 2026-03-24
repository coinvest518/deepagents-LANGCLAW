#!/usr/bin/env python3
"""LangSmith error monitor — run via cron or manually.

Usage:
    python monitor_errors.py              # print error summary
    python monitor_errors.py --alert      # also send Telegram alert if errors spike

Set up as cron:
    deepagents cron add "0 * * * *" "python libs/cli/deepagents_cli/built_in_skills/langsmith/scripts/monitor_errors.py --alert"
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests

LS_KEY = os.environ.get("LANGSMITH_API_KEY", "")
LS_PROJECT = os.environ.get("LANGSMITH_PROJECT", "deeperagents")
BASE = "https://api.smith.langchain.com/api/v1"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_YBOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_AI_OWNER_CHAT_ID", "")
ALERT_THRESHOLD = float(os.environ.get("LS_ALERT_THRESHOLD", "20"))  # % error rate


def get_session_id() -> str:
    resp = requests.get(
        f"{BASE}/sessions?name={LS_PROJECT}",
        headers={"x-api-key": LS_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    sessions = resp.json()
    if not sessions:
        sys.exit(f"Project '{LS_PROJECT}' not found in LangSmith")
    return sessions[0]["id"]


def get_recent_runs(session_id: str, limit: int = 50) -> list:
    resp = requests.post(
        f"{BASE}/runs/query",
        headers={"x-api-key": LS_KEY, "Content-Type": "application/json"},
        json={"session": [session_id], "filter": "eq(is_root, true)", "limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("runs", [])


def get_trace_spans(session_id: str, trace_id: str) -> list:
    resp = requests.post(
        f"{BASE}/runs/query",
        headers={"x-api-key": LS_KEY, "Content-Type": "application/json"},
        json={"session": [session_id], "filter": f'eq(trace_id, "{trace_id}")', "limit": 100},
        timeout=15,
    )
    resp.raise_for_status()
    spans = resp.json().get("runs", [])
    return sorted(spans, key=lambda x: x.get("start_time", ""))


def latency_s(run: dict) -> float:
    try:
        s = datetime.fromisoformat(run["start_time"].replace("Z", "+00:00"))
        e = datetime.fromisoformat(run["end_time"].replace("Z", "+00:00"))
        return (e - s).total_seconds()
    except Exception:
        return 0.0


def send_telegram(message: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=10,
        )
    except Exception as exc:
        print(f"  Telegram send failed: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alert", action="store_true", help="Send Telegram alert on error spike")
    parser.add_argument("--trace", help="Print full trace tree for a run ID")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if not LS_KEY:
        sys.exit("LANGSMITH_API_KEY not set")

    session_id = get_session_id()
    print(f"Project: {LS_PROJECT}  Session: {session_id}\n")

    if args.trace:
        spans = get_trace_spans(session_id, args.trace)
        print(f"Trace {args.trace} — {len(spans)} spans:\n")
        for s in spans:
            indent = "    " if s.get("parent_run_id") else ""
            err = f"  ❌ {s['error'][:120]}" if s.get("error") else ""
            lat = f"  {latency_s(s):.1f}s" if s.get("end_time") else ""
            print(f"{indent}{s['run_type']:8} {s['name']:<40}{lat}{err}")
        return

    runs = get_recent_runs(session_id, args.limit)
    if not runs:
        print("No runs found.")
        return

    errors = [r for r in runs if r.get("error")]
    error_rate = len(errors) / len(runs) * 100
    avg_lat = sum(latency_s(r) for r in runs) / len(runs)

    print(f"Last {len(runs)} runs:")
    print(f"  Errors:      {len(errors)} ({error_rate:.0f}%)")
    print(f"  Avg latency: {avg_lat:.1f}s")
    print()

    if errors:
        print("=== Recent Errors ===")
        for e in errors[:10]:
            ts = e.get("start_time", "")[:19]
            err_short = (e.get("error") or "")[:200]
            print(f"  [{ts}] {e['name']}: {err_short}")
        print()

        # Find which tool names appear in error spans
        tool_errors: dict[str, int] = {}
        for e in errors[:10]:
            spans = get_trace_spans(session_id, e["id"])
            for s in spans:
                if s.get("error") and s.get("run_type") == "tool":
                    name = s["name"]
                    tool_errors[name] = tool_errors.get(name, 0) + 1

        if tool_errors:
            print("=== Failing Tools ===")
            for name, count in sorted(tool_errors.items(), key=lambda x: -x[1]):
                print(f"  {count:3}x  {name}")
            print()

    if args.alert and error_rate > ALERT_THRESHOLD and BOT_TOKEN:
        msg = (
            f"⚠️ LangSmith alert — {LS_PROJECT}\n"
            f"{len(errors)}/{len(runs)} runs failing ({error_rate:.0f}%)\n\n"
        )
        for e in errors[:3]:
            msg += f"• {(e.get('error') or '')[:120]}\n"
        msg += "\nCheck dashboard or run: python monitor_errors.py"
        send_telegram(msg)
        print(f"Alert sent to Telegram (error rate {error_rate:.0f}% > {ALERT_THRESHOLD}%)")


if __name__ == "__main__":
    main()