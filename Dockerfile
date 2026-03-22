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

# Composio — multi-toolkit connector (GitHub, Gmail, LinkedIn, Sheets, etc.)
RUN pip install "composio>=1.0.0" "composio-langchain>=0.9.0" "composio-client>=1.0.0" \
    --root-user-action=ignore || echo "Composio not available"

# Web interaction tools
RUN pip install "langchain-hyperbrowser>=0.4.0" "hyperbrowser>=0.39.0" \
    --root-user-action=ignore || echo "Hyperbrowser not available"
RUN pip install "firecrawl-py>=4.0.0" --root-user-action=ignore || \
    echo "Firecrawl not available"

# browser-use — open-source AI browser agent
# Install Playwright system dependencies first, then the Python package,
# then download the Chromium browser binary (non-fatal if either step fails).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
       libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
       libgbm1 libasound2 libpango-1.0-0 libcairo2 libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/* || true
RUN pip install "browser-use>=0.12.0" --root-user-action=ignore || \
    echo "browser-use not available"
RUN python -m playwright install chromium --with-deps 2>/dev/null || \
    echo "Playwright Chromium install skipped (non-fatal)"

# Daytona sandbox — agent-native cloud execution environment
RUN pip install "langchain-daytona>=0.0.4" "daytona>=0.1.0" \
    --root-user-action=ignore || echo "Daytona not available"

# Blockchain / wallet tools
RUN pip install "eth-account>=0.11.0" \
    --root-user-action=ignore || echo "eth-account not available"

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