---
name: gateway
description: Start or stop the Telegram gateway that receives messages from Telegram and forwards them into this agent.
---

# Run Telegram Gateway Skill

Use this skill when you want to start or stop the Telegram gateway process that listens for Telegram messages and forwards them to the agent.

## Requirements

- The following environment variables must be set in your `.env` (or environment):
  - `BOT_TOKEN` (or `TELEGRAM_BOT_TOKEN`)
  - `TELEGRAM_AI_OWNER_CHAT_ID`

## How to start the gateway

Run one of the gateway scripts:

```
execute("python examples/telegram_gateway/polling_gateway.py")
```

Or (recommended) run the SDK-based gateway for better integration (command routing, file/voice support, and direct agent calls):

```
execute("python examples/telegram_gateway/sdk_gateway.py")
```

Both scripts start long polling and deliver messages to the agent.

### SDK gateway command routing
When using `sdk_gateway.py`, you can route input to specialized subagents:

- `/research` — research-focused agent
- `/code` — coding assistant
- `/review` — reviewer assistant

Attachments (voice/photo/document) are downloaded to `.deepagents/telegram/downloads/` and presented to the agent for processing.

## How to stop the gateway

Stop it by terminating the process (Ctrl+C) or by closing the terminal running the gateway.

## Troubleshooting

- If the bot doesn’t respond, verify the token and chat ID are correct.
- Make sure the script is run from the repo root so paths resolve properly.
