# Deploy DeepAgents to Render

This deploys the agent as a **Render Background Worker** that listens to
Telegram 24/7.  No public port is needed — the bot uses outbound long-polling.

---

## What runs on Render

```
deploy/telegram_bot.py
  └── server_manager.server_session()       starts the LangGraph server
        └── TelegramIntegration.poll_loop()  polls Telegram
              └── agent.astream()            processes each message
                    └── deliver_reply()      sends formatted response
```

The full agent stack is available — all tools, MCP servers, Mem0, AstraDB,
cron jobs, etc.  Telegram is just the input/output channel.

---

## Step-by-step deployment

### 1  Push your repo to GitHub

Render needs to pull the code from a Git repo.  Push `main` (or a deploy
branch) to GitHub:

```bash
git push origin main
```

### 2  Create the Render service

1. Log in at [render.com](https://render.com) and click **New → Background Worker**.
2. Connect your **GitHub** account and select this repository.
3. Render detects the Dockerfile automatically.  Confirm:
   - **Environment**: Docker
   - **Dockerfile path**: `Dockerfile`
   - **Start command**: leave blank (uses the Dockerfile default)

> Use `.env.example` as a local environment template. Copy it to `.env`, fill in secrets, and keep `.env` out of version control.

### 3  Set environment variables (secrets)

In the Render dashboard → your service → **Environment**, add:

| Key | Value | Required |
|-----|-------|----------|
| `BOT_TOKEN` | Your Telegram bot token from [@BotFather](https://t.me/BotFather) | **Yes** |
| `ANTHROPIC_API_KEY` | Anthropic API key | Yes (or another model key) |
| `OPENAI_API_KEY` | OpenAI API key | If using GPT/o-series models |
| `GOOGLE_API_KEY` | Google API key | If using Gemini models |
| `TELEGRAM_AI_OWNER_CHAT_ID` | Your Telegram user ID — restricts the bot to you only | Recommended |
| `MEM0_API_KEY` | Mem0 API key for persistent memory | Optional |
| `ASTRA_DB_API_KEY` | AstraDB API key | Optional |
| `ASTRA_DB_ENDPOINT` | AstraDB endpoint URL | Optional |
| `ASTRA_DB_KEYSPACE` | AstraDB keyspace | Optional |

Non-secret settings (safe to commit in `render.yaml`):

| Key | Default | Notes |
|-----|---------|-------|
| `DA_MODEL` | `` | Explicit model spec override; if omitted the agent picks a provider from the available credentials (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `NVIDIA_API_KEY`, etc.) |
| `DA_AUTO_APPROVE` | `1` | Auto-approve tool calls (no confirmation prompts) |
| `DA_ENABLE_SHELL` | `0` | `1` enables shell execution in the container |

### 4  (Optional) Add a persistent disk

Without a disk, session history and cron jobs are lost when the service
restarts.  To persist them:

1. Render dashboard → your service → **Disks** → **Add Disk**.
2. Set **Mount Path** to `/root/.deepagents` and size to **1 GB**.

### 5  Deploy

Click **Deploy** (or push a new commit to trigger auto-deploy).
Watch the logs — successful startup looks like:

```
INFO  deepagents.telegram_bot: Starting DeepAgents headless Telegram bot...
INFO  deepagents.telegram_bot:   model        = anthropic:claude-sonnet-4-6
INFO  deepagents.telegram_bot:   auto_approve = True
INFO  server: LangGraph server ready on http://127.0.0.1:2024
INFO  deepagents.telegram_bot: Headless bot ready
```

### 6  Test via Telegram

Open a chat with your bot and send any message.  You should see the
⏳ placeholder appear immediately, then the agent's formatted response.

---

## Telegram bot commands

| Command | What it does |
|---------|-------------|
| `/start` or `/help` | Show available commands |
| `/reset` | Clear conversation history (start fresh) |
| `/research <query>` | Route to the research subagent |
| `/code <task>` | Route to the coder subagent |
| `/review <text>` | Route to the reviewer subagent |
| Any other text | Chat with the default agent |

---

## Running other modes on Render

Override `START_CMD` in your Render environment variables to run a
different mode without changing the Dockerfile:

```bash
# Cron daemon — runs scheduled agent jobs from ~/.deepagents/crons.json
START_CMD="python -m deepagents_cli cron daemon"

# One-shot non-interactive (e.g. for a Render Cron Job service)
START_CMD="python -m deepagents_cli -n 'your prompt here' -y -q"
```

---

## Architecture notes

- **No inbound port** — uses Telegram long-polling (outbound HTTPS only).
  Choose **Background Worker** in Render, not Web Service.
- **Agent tools available** — file I/O, HTTP fetch, web search (Tavily),
  MCP servers, Mem0, AstraDB, cron job scheduling, sub-agents.
- **Shell tool** — disabled by default (`DA_ENABLE_SHELL=0`).  Enable
  carefully; the container filesystem is ephemeral unless a disk is mounted.
- **Conversation memory** — each Telegram `chat_id` maps to a unique
  LangGraph `thread_id`, so each user has their own conversation history.
- **Session persistence** — LangGraph checkpointer writes to
  `~/.deepagents/sessions.db` (SQLite).  Mount a disk to persist across deploys.
