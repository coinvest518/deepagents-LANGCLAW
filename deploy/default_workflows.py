"""Default autonomous workflows registered as cron jobs on first boot.

These workflows implement the Observe -> Learn -> Plan -> Act -> Measure
loops that make the system autonomous.  They are registered once via the
agent's ``create_cron_job`` tool on startup.  If a job with the same name
already exists it is skipped (deduplication is built into the cron store).
"""

from __future__ import annotations

import logging

from deepagents_cli.cron_store import CronStore

logger = logging.getLogger(__name__)

# ── Workflow definitions ────────────────────────────────────────────────
# Each tuple: (name, schedule, prompt)

DEFAULT_WORKFLOWS: list[tuple[str, str, str]] = [
    # ── Workflow 1: Daily Analytics Digest ──────────────────────────────
    (
        "daily-analytics-digest",
        "daily",
        (
            "Run a full analytics digest. Delegate to the analyst sub-agent:\n"
            "1. Pull Google Analytics traffic for the last 24 hours (page views, sessions, top pages, traffic sources).\n"
            "2. Pull social media stats from Twitter, LinkedIn, and Instagram (engagement, followers, impressions).\n"
            "3. Compare to previous day and weekly averages from memory.\n"
            "4. Identify trends — what's up, what's down, any anomalies.\n"
            "5. Save key insights to memory with today's date.\n"
            "6. Send a concise digest (5-7 bullet points) to the owner via Telegram."
        ),
    ),
    # ── Workflow 2: Smart Content Scheduling ────────────────────────────
    (
        "smart-content-creation",
        "daily",
        (
            "Create today's content based on analyst insights. Delegate to the content-creator sub-agent:\n"
            "1. Search memory for the latest analytics insights and content strategy.\n"
            "2. Read the business profile for tone, topics, and target audience.\n"
            "3. Decide what to create based on what's performing best.\n"
            "4. Create one piece of content for the highest-priority platform.\n"
            "5. Post it using composio_action (read the platform skill file first).\n"
            "6. Save what was posted to memory for tracking.\n"
            "7. Report what was created and posted via Telegram."
        ),
    ),
    # ── Workflow 3: Post Performance Tracker ────────────────────────────
    (
        "post-performance-tracker",
        "every 6h",
        (
            "Check how recent posts are performing. Delegate to the analyst sub-agent:\n"
            "1. Get recent posts across Twitter, LinkedIn, and Instagram.\n"
            "2. Pull engagement metrics for each post.\n"
            "3. Compare to historical averages from memory.\n"
            "4. Flag winners (> 2x average) and losers (< 0.5x average).\n"
            "5. Save performance data to memory.\n"
            "6. If something is performing exceptionally well, note it for the content agent to double down on."
        ),
    ),
    # ── Workflow 4: System Health Monitor ───────────────────────────────
    (
        "system-health-monitor",
        "hourly",
        (
            "Check system health. Delegate to the ops-monitor sub-agent:\n"
            "1. Query LangSmith for recent runs (last hour).\n"
            "2. Check error rates, latency, and model usage.\n"
            "3. If error rate > 20%, send an ALERT via Telegram immediately.\n"
            "4. Track sub-agent performance and activity.\n"
            "5. Save health status to memory.\n"
            "6. Only send a Telegram message if there's a problem or if this is the daily summary (8am)."
        ),
    ),
]


def register_default_workflows() -> int:
    """Register all default workflows, skipping any that already exist.

    Returns the number of newly registered workflows.
    """
    store = CronStore()
    existing_names = {j.name for j in store.list_jobs()}
    registered = 0

    for name, schedule, prompt in DEFAULT_WORKFLOWS:
        if name in existing_names:
            logger.debug("Workflow '%s' already registered — skipping", name)
            continue
        try:
            job = store.create_job(name=name, schedule=schedule, prompt=prompt)
            logger.info("Registered workflow '%s' (id=%s, next=%s)", name, job.id, job.next_run)
            registered += 1
        except Exception:
            logger.warning("Failed to register workflow '%s'", name, exc_info=True)

    if registered:
        logger.info("Registered %d default workflow(s)", registered)
    return registered
