#!/usr/bin/env python3
"""
Test the _quick_chat function from telegram_bot.py to identify the issue.
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, '/app')

def test_quick_chat():
    """Test the _quick_chat function implementation."""

    # Set environment variables
    os.environ['OLLAMA_BASE_URL'] = 'http://13.222.51.51:11434'
    os.environ['OLLAMA_MODEL'] = 'llama3.2:1b'

    print("Testing _quick_chat function...")
    print(f"OLLAMA_BASE_URL: {os.environ.get('OLLAMA_BASE_URL')}")
    print(f"OLLAMA_MODEL: {os.environ.get('OLLAMA_MODEL')}")

    try:
        # Import the function from telegram_bot.py
        from deploy.telegram_bot import _quick_chat

        print("\nCalling _quick_chat with 'Hey hey'...")
        result = _quick_chat("Hey hey")

        if result:
            print(f"✓ _quick_chat succeeded!")
            print(f"Response: {result}")
        else:
            print("✗ _quick_chat returned empty string")

    except Exception as e:
        print(f"✗ _quick_chat failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_quick_chat()
