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

# Install packages (editable) with cloud-store + all provider extras
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install -e "libs/deepagents[astrapy,mem0]" \
    && pip install -e "libs/cli[astrapy,mem0]"

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