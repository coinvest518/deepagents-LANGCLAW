"""Persistent cron job registry stored at ``~/.deepagents/crons.json``.

Each job has a human-readable *schedule* string and a pre-computed
``interval_seconds`` so the daemon never needs to re-parse schedules.

Supported schedule strings
--------------------------
Named intervals:  ``"minutely"``, ``"hourly"``, ``"daily"``, ``"weekly"``
Explicit intervals: ``"every 30m"``, ``"every 2h"``, ``"every 3d"``
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_NAMED: dict[str, int] = {
    "minutely": 60,
    "hourly": 3600,
    "daily": 86400,
    "weekly": 7 * 86400,
}


def parse_schedule_seconds(schedule: str) -> int:
    """Convert a schedule string to a repeat interval in seconds.

    Args:
        schedule: Named interval or ``"every <N><unit>"`` string.

    Returns:
        Number of seconds between runs.

    Raises:
        ValueError: If the schedule string is not recognised.
    """
    s = schedule.strip().lower()
    if s in _NAMED:
        return _NAMED[s]
    if s.startswith("every "):
        rest = s[6:].strip()
        if rest.endswith("m") and rest[:-1].isdigit():
            return int(rest[:-1]) * 60
        if rest.endswith("h") and rest[:-1].isdigit():
            return int(rest[:-1]) * 3600
        if rest.endswith("d") and rest[:-1].isdigit():
            return int(rest[:-1]) * 86400
    msg = (
        f"Unsupported schedule {schedule!r}. "
        "Use 'minutely', 'hourly', 'daily', 'weekly', "
        "or 'every <N>m / every <N>h / every <N>d'."
    )
    raise ValueError(msg)


@dataclass
class CronJob:
    """A single scheduled agent task.

    Attributes:
        id: Short unique ID (first 8 chars of a UUID4).
        name: Human-readable label.
        prompt: The task prompt sent to the agent on each run.
        schedule: Original schedule string (e.g. ``"daily"``).
        interval_seconds: Pre-computed repeat interval.
        assistant_id: Agent identity for memory isolation.
        created_at: ISO-8601 creation timestamp.
        next_run: ISO-8601 timestamp of the next scheduled run.
        last_run: ISO-8601 timestamp of the most recent run, or ``None``.
        enabled: When ``False`` the job is skipped by the daemon.
    """

    id: str
    name: str
    prompt: str
    schedule: str
    interval_seconds: int
    assistant_id: str
    created_at: str
    next_run: str
    last_run: str | None = None
    enabled: bool = True


class CronStore:
    """Read/write the cron job registry at ``~/.deepagents/crons.json``.

    Args:
        path: Override the default registry path (useful in tests).
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path: Path = path or (Path.home() / ".deepagents" / "crons.json")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load crons.json; starting with empty list", exc_info=True)
            return []

    def _save(self, jobs: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_job(
        self,
        name: str,
        schedule: str,
        prompt: str,
        assistant_id: str = "default",
        run_immediately: bool = False,
    ) -> CronJob:
        """Create and persist a new cron job.

        Args:
            name: Human-readable label.
            schedule: Schedule string (see module docstring).
            prompt: Task prompt for the agent.
            assistant_id: Agent identity for memory isolation.
            run_immediately: If ``True`` set ``next_run`` to now so the
                daemon picks it up on the very next tick.

        Returns:
            The newly created :class:`CronJob`.

        Raises:
            ValueError: If *schedule* is not a recognised format.
        """
        interval = parse_schedule_seconds(schedule)
        now = datetime.now(UTC)
        next_run = now if run_immediately else now + timedelta(seconds=interval)
        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            prompt=prompt,
            schedule=schedule,
            interval_seconds=interval,
            assistant_id=assistant_id,
            created_at=now.isoformat(),
            next_run=next_run.isoformat(),
            last_run=None,
            enabled=True,
        )
        jobs = self._load()
        jobs.append(asdict(job))
        self._save(jobs)
        logger.info("Cron job created: id=%s name=%r schedule=%r", job.id, job.name, job.schedule)
        return job

    def list_jobs(self) -> list[CronJob]:
        """Return all stored cron jobs."""
        return [CronJob(**j) for j in self._load()]

    def get_job(self, job_id: str) -> CronJob | None:
        """Return the job with the given ID, or ``None``."""
        for j in self._load():
            if j["id"] == job_id:
                return CronJob(**j)
        return None

    def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID.

        Returns:
            ``True`` if a job was removed, ``False`` if not found.
        """
        jobs = self._load()
        filtered = [j for j in jobs if j["id"] != job_id]
        if len(filtered) < len(jobs):
            self._save(filtered)
            logger.info("Cron job deleted: id=%s", job_id)
            return True
        return False

    def enable_job(self, job_id: str, *, enabled: bool = True) -> bool:
        """Enable or disable a job without deleting it.

        Returns:
            ``True`` if the job was found and updated.
        """
        jobs = self._load()
        for j in jobs:
            if j["id"] == job_id:
                j["enabled"] = enabled
                self._save(jobs)
                return True
        return False

    def get_due_jobs(self) -> list[CronJob]:
        """Return all enabled jobs whose ``next_run`` is at or before now."""
        now = datetime.now(UTC).isoformat()
        return [j for j in self.list_jobs() if j.enabled and j.next_run <= now]

    def mark_run(self, job_id: str) -> None:
        """Record a completed run and advance ``next_run``.

        Args:
            job_id: ID of the job that just ran.
        """
        jobs = self._load()
        now = datetime.now(UTC)
        for j in jobs:
            if j["id"] == job_id:
                j["last_run"] = now.isoformat()
                j["next_run"] = (now + timedelta(seconds=j["interval_seconds"])).isoformat()
                break
        self._save(jobs)