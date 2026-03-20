"""CLI command implementations for ``deepagents cron``.

Subcommands
-----------
list   — Print all scheduled jobs.
run    — Execute all due jobs once and exit.
daemon — Loop forever, running jobs as they come due.
delete — Remove a job by ID.

Job execution
-------------
Each job is run by invoking the current ``deepagents`` executable with
``-n <prompt> -y --quiet`` so output goes to a log file and the daemon
doesn't need to manage a LangGraph server itself — that's handled by the
normal CLI startup path.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path

from rich.console import Console
from rich.table import Table

from deepagents_cli.cron_store import CronJob, CronStore

logger = logging.getLogger(__name__)
console = Console()
_store = CronStore()

# Logs for each job run are written here.
_LOG_DIR = Path.home() / ".deepagents" / "cron_logs"


def _log_path(job: CronJob) -> Path:
    """Return the log file path for *job*."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR / f"{job.id}.log"


def _run_job(job: CronJob, *, dry_run: bool = False) -> None:
    """Invoke the agent for *job*'s prompt via a subprocess.

    Args:
        job: The cron job to execute.
        dry_run: If ``True`` print what would run without running it.
    """
    cmd = [
        sys.executable,
        "-m",
        "deepagents_cli",
        "-n",
        job.prompt,
        "-y",   # auto-approve
        "-q",   # quiet: response only on stdout
        "--agent",
        job.assistant_id,
    ]

    if dry_run:
        console.print(
            f"[bold cyan]DRY RUN[/bold cyan] [{job.id}] {job.name!r}: "
            f"{job.prompt[:70]}{'...' if len(job.prompt) > 70 else ''}",
        )
        return

    log_file = _log_path(job)
    console.print(
        f"[green]▶ Running[/green] [{job.id}] {job.name!r}  (log: {log_file})"
    )

    try:
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{'='*60}\n")
            fh.write(f"Run started: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
            fh.write(f"Prompt: {job.prompt}\n")
            fh.write(f"{'='*60}\n")
            result = subprocess.run(
                cmd,
                stdout=fh,
                stderr=fh,
                timeout=600,  # 10-minute hard cap per job
            )
            fh.write(f"\nExit code: {result.returncode}\n")
    except subprocess.TimeoutExpired:
        logger.warning("Cron job %r timed out after 600 s", job.id)
    except Exception:
        logger.warning("Failed to run cron job %r", job.id, exc_info=True)
    finally:
        _store.mark_run(job.id)


# ------------------------------------------------------------------
# Subcommand handlers
# ------------------------------------------------------------------


def _cmd_list() -> None:
    """Print all cron jobs in a formatted table."""
    jobs = _store.list_jobs()
    if not jobs:
        console.print("[dim]No cron jobs scheduled.[/dim]")
        return

    table = Table(title="Scheduled Cron Jobs", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Schedule")
    table.add_column("Next Run")
    table.add_column("Last Run")
    table.add_column("Status")

    for job in jobs:
        status = "[green]enabled[/green]" if job.enabled else "[red]disabled[/red]"
        table.add_row(
            job.id,
            job.name,
            job.schedule,
            job.next_run[:19].replace("T", " "),
            (job.last_run or "never")[:19].replace("T", " "),
            status,
        )

    console.print(table)


def _cmd_run(dry_run: bool = False) -> None:
    """Run all due jobs and exit."""
    due = _store.get_due_jobs()
    if not due:
        console.print("[dim]No cron jobs are due right now.[/dim]")
        return

    label = "[bold cyan]DRY RUN[/bold cyan]" if dry_run else "[bold green]RUNNING[/bold green]"
    console.print(f"{label} — {len(due)} job(s) due")
    for job in due:
        _run_job(job, dry_run=dry_run)


def _cmd_daemon(poll_interval: int = 60) -> None:
    """Poll indefinitely and run jobs as they come due."""
    console.print(
        f"[bold green]Cron daemon started[/bold green] "
        f"(poll every {poll_interval}s — Ctrl-C to stop)"
    )
    try:
        while True:
            due = _store.get_due_jobs()
            if due:
                for job in due:
                    _run_job(job)
            else:
                logger.debug("No jobs due, sleeping %ds", poll_interval)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Cron daemon stopped.[/dim]")


def _cmd_delete(job_id: str) -> None:
    """Delete a cron job by ID."""
    if _store.delete_job(job_id):
        console.print(f"[green]Deleted[/green] cron job '{job_id}'.")
    else:
        console.print(
            f"[red]Not found:[/red] no cron job with ID '{job_id}'. "
            "Run [bold]deepagents cron list[/bold] to see current jobs."
        )


# ------------------------------------------------------------------
# Dispatch
# ------------------------------------------------------------------


def execute_cron_command(args: Namespace) -> None:
    """Route ``args.cron_command`` to the correct handler.

    Args:
        args: Parsed CLI namespace from argparse.
    """
    cmd = getattr(args, "cron_command", None)
    if cmd in {"list", "ls", None}:
        _cmd_list()
    elif cmd == "run":
        _cmd_run(dry_run=getattr(args, "dry_run", False))
    elif cmd == "daemon":
        _cmd_daemon(poll_interval=getattr(args, "interval", 60))
    elif cmd in {"delete", "rm"}:
        _cmd_delete(args.job_id)
    else:
        console.print(f"[red]Unknown cron subcommand:[/red] {cmd!r}")
        console.print("Available subcommands: list, run, daemon, delete")