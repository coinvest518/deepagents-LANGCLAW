e #!/usr/bin/env python3
"""
Test the fixed _quick_chat function with proper imports.
"""

import os
import sys

def test_fixed_quick_chat():
    """Test the fixed _quick_chat function."""

    # Set environment variables
    os.environ['OLLAMA_BASE_URL'] = 'http://13.222.51.51:11434'
    os.environ['OLLAMA_MODEL'] = 'llama3.2:1b'

    print("Testing fixed _quick_chat function...")
    print(f"OLLAMA_BASE_URL: {os.environ.get('OLLAMA_BASE_URL')}")
    print(f"OLLAMA_MODEL: {os.environ.get('OLLAMA_MODEL')}")

    # Test the fixed _quick_chat function
    async def _quick_chat_fixed(message: str) -> str:
        """Fixed version of _quick_chat with proper imports."""
        try:
            # Try the new LangChain imports first
            try:
                from langchain_core.chat_models import BaseChatModel
                from langchain_core.messages import HumanMessage, SystemMessage
                from langchain_ollama import ChatOllama

                # For Ollama, use ChatOllama directly
                if os.environ.get("OLLAMA_BASE_URL"):
                    llm = ChatOllama(
                        model=os.environ.get("OLLAMA_MODEL", "llama3.2:1b"),
                        base_url=os.environ.get("OLLAMA_BASE_URL")
                    )
                    messages = [
                        SystemMessage(content="You are a helpful AI assistant. Be friendly, concise, and natural."),
                        HumanMessage(content=message),
                    ]
                    resp = await llm.ainvoke(messages)
                    return str(resp.content).strip() or ""

            except ImportError:
                # Fallback to the original approach if new imports don't work
                from langchain.chat_models import init_chat_model
                from langchain_core.messages import HumanMessage
                from langchain_core.messages import SystemMessage as SM

                parts = "ollama:llama3.2:1b".split(":", 1)
                llm = init_chat_model(parts[1], model_provider=parts[0]) if len(parts) == 2 else init_chat_model("ollama:llama3.2:1b")
                resp = await llm.ainvoke([
                    SM(content="You are a helpful AI assistant. Be friendly, concise, and natural."),
                    HumanMessage(content=message),
                ])
                return str(resp.content).strip() or ""

        except Exception as e:
            print(f"Quick chat failed: {e}")
            return ""

    # Test the function
    import asyncio
    try:
        result = asyncio.run(_quick_chat_fixed("Hey hey"))
        if result:
            print(f"✓ Fixed _quick_chat succeeded!")
            print(f"Response: {result}")
        else:
            print("✗ Fixed _quick_chat returned empty string")
    except Exception as e:
        print(f"✗ Fixed _quick_chat failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fixed_quick_chat()
