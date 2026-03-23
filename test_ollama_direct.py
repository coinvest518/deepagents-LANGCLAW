#!/usr/bin/env python3
"""
Test Ollama connection using the same logic as _quick_chat function.
"""

import os
import sys

def test_ollama_direct():
    """Test Ollama using the same approach as _quick_chat."""

    # Set environment variables
    os.environ['OLLAMA_BASE_URL'] = 'http://13.222.51.51:11434'
    os.environ['OLLAMA_MODEL'] = 'llama3.2:1b'

    print("Testing Ollama direct connection...")
    print(f"OLLAMA_BASE_URL: {os.environ.get('OLLAMA_BASE_URL')}")
    print(f"OLLAMA_MODEL: {os.environ.get('OLLAMA_MODEL')}")

    try:
        # Import langchain components
        from langchain.chat_models import init_chat_model
        from langchain_core.messages import HumanMessage
        from langchain_core.messages import SystemMessage as SM

        # Get model spec
        parts = os.environ.get('OLLAMA_MODEL', 'llama3.2:1b').split(':', 1)
        if len(parts) == 2:
            model_provider = parts[0]
            model_name = parts[1]
        else:
            model_provider = 'ollama'
            model_name = parts[0]

        print(f"Model provider: {model_provider}")
        print(f"Model name: {model_name}")

        # Initialize the model
        print("Initializing chat model...")
        llm = init_chat_model(model_name, model_provider=model_provider)

        # Test the chat
        print("Sending test message...")
        messages = [
            SM(content="You are a helpful AI assistant. Be friendly, concise, and natural."),
            HumanMessage(content="Hey hey"),
        ]

        response = llm.invoke(messages)
        print(f"✓ Success! Response: {response.content}")

    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ollama_direct()
