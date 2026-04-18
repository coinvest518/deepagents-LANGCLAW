"""Quick local test for `start_api_server`.

Creates a dummy agent with minimal `astream`/`aget_state` behaviour,
starts the HTTP API server (aiohttp) from `deploy.telegram_bot`, and
verifies `/health` and `/chat` endpoints respond as expected.

Run with: python deploy/tests/local_server_test.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.dirname(__file__))
ROOT = os.path.dirname(_HERE)
if str(ROOT) not in sys.path:
    sys.path.insert(0, ROOT)

from deploy.telegram_bot import start_api_server, API_PORT  # type: ignore


class DummyAgent:
    async def astream(self, agent_input, config=None):
        # Yield a single messages chunk with an AI message
        yield ((), "messages", (SimpleNamespace(type="ai", content="Hello from dummy agent"), {}))

    async def aget_state(self, config):
        class State:
            values = {"messages": [{"type": "ai", "content": "Hello from dummy agent"}]}
        return State()


async def _run_test():
    agent = DummyAgent()
    server_task = asyncio.create_task(start_api_server(agent, bot=None))
    # wait a moment for server to start
    await asyncio.sleep(1)

    import aiohttp

    async with aiohttp.ClientSession() as sess:
        url = f"http://127.0.0.1:{API_PORT}/health"
        async with sess.get(url) as r:
            print("GET /health ->", r.status, await r.text())

        url = f"http://127.0.0.1:{API_PORT}/chat"
        payload = {"message": "hello test", "thread_id": "local-test"}
        async with sess.post(url, json=payload) as r:
            print("POST /chat ->", r.status)
            try:
                print(await r.json())
            except Exception:
                print(await r.text())

    server_task.cancel()

    # Test TTS proxy handling using a fake voice_handler implementation.
    sys.modules['voice_handler'] = SimpleNamespace(synthesize=lambda text: b'FAKEAUDIO')
    server_task = asyncio.create_task(start_api_server(agent, bot=None))
    await asyncio.sleep(1)
    try:
        async with aiohttp.ClientSession() as sess:
            url = f"http://127.0.0.1:{API_PORT}/tts"
            async with sess.post(url, json={"text": "hello audio"}) as r:
                print("POST /tts ->", r.status)
                body = await r.read()
                print("/tts bytes:", len(body))
    finally:
        server_task.cancel()
        sys.modules.pop('voice_handler', None)


if __name__ == "__main__":
    asyncio.run(_run_test())
