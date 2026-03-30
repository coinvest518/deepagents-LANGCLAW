"""LangChain tools that let the agent manage its own scheduled (cron) jobs.

These tools are added to the agent's tool list automatically so it can say
things like "remind me daily" or "run this analysis every morning" and have
those tasks actually persist and execute.

The agent can:
- ``create_cron_job`` — schedule a recurring task
- ``list_cron_jobs``  — see what is scheduled
- ``delete_cron_job`` — remove a scheduled task
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from deepagents_cli.cron_store import CronStore

logger = logging.getLogger(__name__)

# Module-level store so all three tools share one instance.
_store = CronStore()


@tool
def create_cron_job(name: str, schedule: str, prompt: str) -> str:
    """Schedule a recurring autonomous task.

    Use this whenever the user asks you to do something on a recurring basis
    — e.g. "summarise the news every morning", "check disk space hourly",
    "send me a weekly report".

    Supported schedule values
    -------------------------
    Named:    "minutely" | "hourly" | "daily" | "weekly"
    Interval: "every 15m" | "every 2h" | "every 3d"

    Args:
        name: Short, descriptive label (e.g. "daily-news-summary").
        schedule: How often to run (see above).
        prompt: The exact task/prompt the agent should execute on each run.
            Be specific — include any file paths, URLs, or context needed.

    Returns:
        Confirmation string with the job ID and next scheduled run time.
    """
    # Deduplication: if a job with this name already exists, return it instead
    # of creating a duplicate.  This prevents loop-prone LLMs from registering
    # the same job dozens of times when they keep retrying after a success.
    existing = [j for j in _store.list_jobs() if j.name == name]
    if existing:
        job = existing[0]
        return (
            f"Cron job '{name}' already exists — no duplicate created.\n"
            f"  ID       : {job.id}\n"
            f"  Name     : {job.name}\n"
            f"  Schedule : {job.schedule}\n"
            f"  Next run : {job.next_run}\n"
            f"\nThe existing job is already scheduled. "
            f"Use delete_cron_job('{job.id}') first if you want to replace it."
        )

    try:
        job = _store.create_job(name=name, schedule=schedule, prompt=prompt)
    except ValueError as exc:
        return f"Error creating cron job: {exc}"
    return (
        f"Cron job created.\n"
        f"  ID       : {job.id}\n"
        f"  Name     : {job.name}\n"
        f"  Schedule : {job.schedule}\n"
        f"  Next run : {job.next_run}\n"
        f"\nThe job will run the next time `deepagents cron run` (or the cron daemon) executes."
    )


@tool
def list_cron_jobs() -> str:
    """List all scheduled cron jobs.

    Returns:
        A formatted table of all jobs, or a message if none exist.
    """
    jobs = _store.list_jobs()
    if not jobs:
        return "No cron jobs scheduled."
    lines = ["Scheduled cron jobs:", ""]
    for job in jobs:
        status = "enabled" if job.enabled else "disabled"
        last = job.last_run or "never"
        lines.append(
            f"[{job.id}] {job.name!r}  |  {job.schedule}  |  {status}"
            f"\n        Last run : {last}"
            f"\n        Next run : {job.next_run}"
            f"\n        Prompt   : {job.prompt[:80]}{'...' if len(job.prompt) > 80 else ''}"
        )
        lines.append("")
    return "\n".join(lines)


@tool
def delete_cron_job(job_id: str) -> str:
    """Remove a scheduled cron job by its ID.

    Args:
        job_id: The short ID shown by ``list_cron_jobs`` (e.g. "a3f9c12b").

    Returns:
        Confirmation or an error if the ID was not found.
    """
    if _store.delete_job(job_id):
        return f"Cron job '{job_id}' deleted."
    return f"No cron job found with ID '{job_id}'. Use list_cron_jobs to see current jobs."


# Exported list for easy consumption in server_graph.py / tools.py
CRON_TOOLS = [create_cron_job, list_cron_jobs, delete_cron_job]