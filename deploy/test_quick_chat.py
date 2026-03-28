#!/usr/bin/env python3
"""Test script for the Quick Chat module."""

import asyncio
import sys
from pathlib import Path

# Add the repo root to the path
_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

from quick_chat import handle_quick_chat, should_use_quick_chat

async def test_quick_chat():
    """Test the Quick Chat functionality."""
    print("Testing Quick Chat Module...")
    print("=" * 50)

    # Test 1: Casual greeting
    print("\n1. Testing casual greeting:")
    message = "Hello Musa, how are you today?"
    should_handle = should_use_quick_chat(message)
    print(f"Message: '{message}'")
    print(f"Should handle with Quick Chat: {should_handle}")

    if should_handle:
        reply, should_handoff = await handle_quick_chat(message)
        print(f"Reply: {reply[:100]}{'...' if len(reply) > 100 else ''}")
        print(f"Should handoff to main agent: {should_handoff}")

    # Test 2: Simple question
    print("\n2. Testing simple question:")
    message = "What's the weather like today?"
    should_handle = should_use_quick_chat(message)
    print(f"Message: '{message}'")
    print(f"Should handle with Quick Chat: {should_handle}")

    if should_handle:
        reply, should_handoff = await handle_quick_chat(message)
        print(f"Reply: {reply[:100]}{'...' if len(reply) > 100 else ''}")
        print(f"Should handoff to main agent: {should_handoff}")

    # Test 3: Task requiring main agent
    print("\n3. Testing task requiring main agent:")
    message = "Please send an email to john@example.com with the subject 'Meeting' and body 'Let's meet tomorrow.'"
    should_handle = should_use_quick_chat(message)
    print(f"Message: '{message}'")
    print(f"Should handle with Quick Chat: {should_handle}")

    if should_handle:
        reply, should_handoff = await handle_quick_chat(message)
        print(f"Reply: {reply[:100]}{'...' if len(reply) > 100 else ''}")
        print(f"Should handoff to main agent: {should_handoff}")

    # Test 4: Complex multi-step task
    print("\n4. Testing complex multi-step task:")
    message = "I need you to create a new GitHub repository called 'test-repo', add a README.md file, and push it to GitHub."
    should_handle = should_use_quick_chat(message)
    print(f"Message: '{message}'")
    print(f"Should handle with Quick Chat: {should_handle}")

    if should_handle:
        reply, should_handoff = await handle_quick_chat(message)
        print(f"Reply: {reply[:100]}{'...' if len(reply) > 100 else ''}")
        print(f"Should handoff to main agent: {should_handoff}")

    # Test 5: Memory lookup
    print("\n5. Testing memory lookup:")
    message = "What did we discuss in our last conversation?"
    should_handle = should_use_quick_chat(message)
    print(f"Message: '{message}'")
    print(f"Should handle with Quick Chat: {should_handle}")

    if should_handle:
        reply, should_handoff = await handle_quick_chat(message)
        print(f"Reply: {reply[:100]}{'...' if len(reply) > 100 else ''}")
        print(f"Should handoff to main agent: {should_handoff}")

    print("\n" + "=" * 50)
    print("Quick Chat test completed!")

if __name__ == "__main__":
    asyncio.run(test_quick_chat())
