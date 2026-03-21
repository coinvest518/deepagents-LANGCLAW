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

# Install LLM provider packages for the models we actually use.
# Each is in a separate || echo so one failure never blocks the others.
RUN pip install "langchain-nvidia-ai-endpoints>=1.0.0" --root-user-action=ignore || \
    echo "NVIDIA provider not available"
RUN pip install "langchain-mistralai>=0.2.0" --root-user-action=ignore || \
    echo "Mistral provider not available"
RUN pip install "langchain-openai>=0.3.0" --root-user-action=ignore || \
    echo "OpenAI/OpenRouter provider not available"
RUN pip install "langchain-anthropic>=0.3.0" --root-user-action=ignore || \
    echo "Anthropic provider not available"
RUN pip install "langchain-huggingface>=0.1.0" --root-user-action=ignore || \
    echo "HuggingFace provider not available"

# Optional cloud-store packages — non-fatal if unavailable.
RUN pip install "mem0ai>=0.1.0" "astrapy>=1.0.0" --root-user-action=ignore || \
    echo "Optional cloud-store packages not available — stores disabled at runtime"

# Persistent storage lives under ~/.deepagents (sessions, cron logs, workspace cache)
# Render mounts a disk here when you add a persistent disk to the service.
ENV DEEPAGENTS_HOME=/root/.deepagents
# LangGraph SDK requires LANGSMITH_API_KEY even for local dev servers —
# it's a client-side check. "local" satisfies it; override in Render env
# vars with your real LangSmith key if you have one.
ENV LANGSMITH_API_KEY=local

# ── Default start: headless Telegram bot ──────────────────────────────────────
# Override with Render startCommand or START_CMD env var for other modes:
#
#   Non-interactive one-shot:
#     python -m deepagents_cli -n "your prompt" -y -q
#
#   Cron daemon (run scheduled jobs):
#     python -m deepagents_cli cron daemon
#
ENV DA_MODEL="mistralai:mistral-large-latest"
ENV START_CMD="python deploy/telegram_bot.py"

CMD ["/bin/sh", "-c", "${START_CMD}"]