FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies needed by langgraph-cli and build tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       git \
       curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy repository
COPY . /app

# Install base packages first (no optional extras that may not be on PyPI).
# Cloud stores (mem0ai, astrapy) are runtime-optional: the agent auto-detects
# them from env vars and skips gracefully if packages are absent.
# Upgrade pip first to avoid legacy resolver warnings.
RUN pip install --upgrade pip setuptools wheel --root-user-action=ignore \
    && pip install -e "libs/deepagents" --root-user-action=ignore \
    && pip install -e "libs/cli" --root-user-action=ignore

# Install optional cloud-store packages separately so a single failure
# does not break the whole build.  These are non-fatal if unavailable.
RUN pip install "mem0ai>=0.1.0" "astrapy>=1.0.0" --root-user-action=ignore || \
    echo "Optional cloud-store packages not available — stores disabled at runtime"

# Persistent storage lives under ~/.deepagents (sessions, cron logs, workspace cache)
# Render mounts a disk here when you add a persistent disk to the service.
ENV DEEPAGENTS_HOME=/root/.deepagents

# ── Default start: headless Telegram bot ──────────────────────────────────────
# Override with Render startCommand or START_CMD env var for other modes:
#
#   Non-interactive one-shot:
#     python -m deepagents_cli -n "your prompt" -y -q
#
#   Cron daemon (run scheduled jobs):
#     python -m deepagents_cli cron daemon
#
ENV START_CMD="python deploy/telegram_bot.py"

CMD ["/bin/sh", "-c", "${START_CMD}"]