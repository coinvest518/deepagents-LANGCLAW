#!/usr/bin/env python3
"""
Fix the Ollama connection issue by updating the _quick_chat function.
"""

import os
import sys

def fix_quick_chat():
    """Fix the _quick_chat function to use direct HTTP requests."""

    # Read the current telegram_bot.py file
    with open('deploy/telegram_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the _quick_chat function and replace it
    old_function = '''async def _quick_chat(message: str) -> str:
    """Fast direct LLM call for casual messages — no tools, no middleware overhead.

    Bypasses the full agent stack entirely: no tool schemas (~13k tokens saved),
    no memory middleware, no summarization.  Falls back to empty string on any
    error so the caller can retry via the full agent.
    """
    try:
        from langchain.chat_models import init_chat_model
        from langchain_core.messages import HumanMessage
        from langchain_core.messages import SystemMessage as SM

        parts = CHAT_MODEL.split(":", 1)
        llm = init_chat_model(parts[1], model_provider=parts[0]) if len(parts) == 2 else init_chat_model(CHAT_MODEL)
        resp = await llm.ainvoke([
            SM(content="You are a helpful AI assistant. Be friendly, concise, and natural."),
            HumanMessage(content=message),
        ])
        return str(resp.content).strip() or ""
    except Exception:
        logger.warning("Quick chat failed, falling back to full agent", exc_info=True)
        return ""'''

    new_function = '''async def _quick_chat(message: str) -> str:
    """Fast direct LLM call for casual messages — no tools, no middleware overhead.

    Bypasses the full agent stack entirely: no tool schemas (~13k tokens saved),
    no memory middleware, no summarization.  Falls back to empty string on any
    error so the caller can retry via the full agent.
    """
    try:
        import requests
        import json

        # Check if we're using Ollama
        if CHAT_MODEL.startswith("ollama:"):
            model_name = CHAT_MODEL.replace("ollama:", "")
            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://13.222.51.51:11434")

            # Use direct HTTP request to Ollama API
            chat_data = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a helpful AI assistant. Be friendly, concise, and natural."},
                    {"role": "user", "content": message}
                ],
                "stream": False
            }

            response = requests.post(f"{ollama_url}/api/chat", json=chat_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return str(result.get("message", {}).get("content", "")).strip() or ""
            else:
                logger.warning("Ollama API returned status %d: %s", response.status_code, response.text)
                return ""

        # For other models, try the original LangChain approach
        try:
            from langchain.chat_models import init_chat_model
            from langchain_core.messages import HumanMessage
            from langchain_core.messages import SystemMessage as SM

            parts = CHAT_MODEL.split(":", 1)
            llm = init_chat_model(parts[1], model_provider=parts[0]) if len(parts) == 2 else init_chat_model(CHAT_MODEL)
            resp = await llm.ainvoke([
                SM(content="You are a helpful AI assistant. Be friendly, concise, and natural."),
                HumanMessage(content=message),
            ])
            return str(resp.content).strip() or ""
        except Exception as e:
            logger.warning("LangChain quick chat failed: %s", e)
            return ""

    except Exception as e:
        logger.warning("Quick chat failed, falling back to full agent", exc_info=True)
        return ""'''

    # Replace the function
    if old_function in content:
        content = content.replace(old_function, new_function)

        # Write the updated content back
        with open('deploy/telegram_bot.py', 'w', encoding='utf-8') as f:
            f.write(content)

        print("[OK] Successfully updated _quick_chat function in deploy/telegram_bot.py")
        print("[OK] The function now uses direct HTTP requests for Ollama")
        print("[OK] This should fix the connection issue")

        return True
    else:
        print("[FAIL] Could not find the _quick_chat function to replace")
        return False

if __name__ == "__main__":
    fix_quick_chat()
