#!/usr/bin/env python3
"""
Test what model is actually being selected by _pick_chat_model.
"""

import os

def test_model_selection():
    """Test model selection logic."""

    # Set environment variables
    os.environ['OLLAMA_BASE_URL'] = 'http://13.222.51.51:11434'
    os.environ['OLLAMA_MODEL'] = 'llama3.2:1b'

    print("Testing model selection...")
    print(f"OLLAMA_BASE_URL: {os.environ.get('OLLAMA_BASE_URL')}")
    print(f"OLLAMA_MODEL: {os.environ.get('OLLAMA_MODEL')}")

    # Test the logic from _pick_chat_model
    def _pick_chat_model() -> str:
        """Return the fastest available model for casual chat (no tools needed)."""
        if os.environ.get("OLLAMA_BASE_URL"):
            model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
            return f"ollama:{model}"
        if os.environ.get("CEREBRAS_API_KEY"):
            return "cerebras:llama3.1-8b"
        if os.environ.get("MISTRAL_API_KEY"):
            return "mistralai:mistral-small-latest"
        return "anthropic:claude-sonnet-4-6"  # fallback

    chat_model = _pick_chat_model()
    print(f"Selected chat model: {chat_model}")

    # Test the logic from _quick_chat
    def _is_casual(text: str) -> bool:
        """Return True if *text* is clearly casual chat."""
        import re
        _CASUAL_RE = re.compile(
            r"^(hi+|hey+|hello+|yo+|sup|what'?s\s*up|how\s*are\s*you|"
            r"good\s+(morning|night|evening|day|afternoon)|"
            r"thanks?(\s+you)?|ok+|okay|sure|cool|nice|great|lol+|haha+|"
            r"test(ing)?|ping|who\s+are\s+you|what\s+can\s+you\s+do)\s*[?!.]*$",
            re.IGNORECASE,
        )
        _TASK_WORDS = frozenset({
            "find", "search", "create", "make", "build", "write", "send",
            "get", "show", "list", "check", "update", "delete", "run", "open",
            "fetch", "read", "save", "add", "remove", "set", "deploy", "push",
        })

        stripped = text.strip()
        if not stripped:
            return False
        lower = stripped.lower()
        if any(w in lower.split() for w in _TASK_WORDS):
            return False
        if len(stripped) <= 15:
            return bool(_CASUAL_RE.match(stripped)) or "?" not in stripped
        return bool(_CASUAL_RE.match(stripped))

    message = "Hey hey"
    is_casual = _is_casual(message)
    print(f"Message '{message}' is casual: {is_casual}")

    # Check if fast path should activate
    MODEL = "anthropic:claude-sonnet-4-6"  # fallback from _pick_model
    should_use_fast_path = is_casual and chat_model != MODEL
    print(f"Should use fast path: {should_use_fast_path}")

    if should_use_fast_path:
        print(f"Fast path would use: {chat_model}")
        print("This means the issue is in the _quick_chat implementation, not model selection")
    else:
        print("Fast path would NOT activate - check model selection logic")

if __name__ == "__main__":
    test_model_selection()
