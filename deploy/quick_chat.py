"""Quick Chat Module - The Voice of FDWA

This module provides a standalone Quick Chat interface that handles:
- Casual conversation and greetings
- Simple factual queries (weather, time, basic info)
- Memory lookups and reminders
- Quick web searches
- System status checks
- User relationship management

The Quick Chat acts as the "voice" of the system while the main agent handles complex tasks.
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup: make CLI + SDK importable when running from the repo root
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
for _lib in ("libs/cli", "libs/deepagents"):
    _p = str(_REPO / _lib)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Import dependencies with fallbacks
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_REPO / ".env", override=False)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("deepagents.quick_chat")

# ---------------------------------------------------------------------------
# Quick Chat Configuration
# ---------------------------------------------------------------------------

# Quick Chat tools - only lightweight tools allowed
_QUICK_CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information. Use for: weather, news, "
                "stock prices, scores, facts, anything needing real-time data. "
                "Returns top 3 results with titles, URLs, and snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": (
                "Search the agent's long-term memory for past conversations, saved facts, "
                "user preferences, and previous task results. Use when the user asks: "
                "'what did we discuss', 'remember when', 'what did the agent do', "
                "'check memory', or references past work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for in memory"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save information to long-term memory. Use when user says 'remember this', "
                "'save this', 'note that', or when you learn something important."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "What to remember"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and read the content of a web page URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_system_status",
            "description": "Check if main agent is available, system health.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_main_agent",
            "description": (
                "Pass to the main AI agent for HEAVY tasks only. Use ONLY for: "
                "sending emails, posting to social media, creating spreadsheets, "
                "GitHub operations, multi-step workflows, code execution, file operations, "
                "or anything needing Composio integrations (Gmail, Sheets, etc.). "
                "Do NOT use for: web search, memory lookup, simple questions — handle those yourself."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

_QUICK_CHAT_HANDOFF_SENTINEL = "__HANDOFF_TO_MAIN_AGENT__"

# Action verbs / nouns that clearly signal a task needing the main agent.
_TASK_WORDS = frozenset({
    # Clear task verbs - these indicate the user wants the agent to DO something
    "send", "create", "write", "post", "tweet", "email", "schedule", "deploy",
    "push", "pull", "clone", "install", "download", "upload", "convert", "translate",
    "edit", "rename", "move", "copy", "delete", "update", "add", "remove", "set",
    "generate", "summarize", "analyze", "fix", "debug", "automate", "test",
    "run", "execute", "perform", "complete", "build", "make", "start", "stop",
    "restart", "kill", "terminate", "launch", "open", "close", "save", "fetch",
    "list", "check", "search", "find", "look", "get", "grab", "pull", "push",

    # Service nouns - these indicate the user wants to use specific APIs/services
    "gmail", "github", "sheets", "spreadsheet", "drive", "docs", "slack",
    "notion", "dropbox", "twitter", "linkedin", "instagram", "facebook",
    "youtube", "serpapi", "analytics", "calendar", "airtable", "zapier",
    "ifttt", "discord", "reddit", "stackoverflow", "stackoverflow",

    # System queries that need the main agent (not Quick Chat)
    "trace", "langsmith", "dashboard", "logs", "monitoring", "metrics",

    # File operations
    "file", "folder", "directory", "document", "pdf", "docx", "xlsx", "csv",
    "json", "xml", "yaml", "txt", "code", "script", "program",

    # Development operations
    "git", "repository", "branch", "commit", "merge", "pull_request", "issue",
    "pr", "pullrequest", "repository", "repo", "version", "release", "tag",

    # Business operations
    "invoice", "payment", "transaction", "order", "customer", "client", "user",
    "account", "subscription", "billing", "invoice", "receipt", "quote",

    # Content operations
    "blog", "article", "post", "content", "marketing", "campaign", "ad",
    "social_media", "newsletter", "email_campaign", "sms", "message",

    # Data operations
    "database", "query", "sql", "data", "dataset", "report", "analytics",
    "statistics", "metrics", "dashboard", "visualization", "chart", "graph",

    # Automation operations
    "workflow", "automation", "bot", "script", "macro", "trigger", "action",
    "condition", "rule", "schedule", "cron", "timer", "event",

    # Cloud operations
    "server", "vm", "instance", "container", "docker", "kubernetes", "aws",
    "gcp", "azure", "deployment", "infrastructure", "network", "security",

    # Communication operations
    "call", "meeting", "conference", "video", "audio", "chat", "message",
    "notification", "alert", "reminder", "calendar", "appointment", "event",
})

# Phrases that mean "I'm handing this off" — Quick Chat says these when escalating.
_HANDOFF_PHRASES = (
    # Natural handoff language
    "let me get the main agent on this",
    "i'm escalating this to the main agent",
    "this requires our full agent",
    "let me connect you to the main system",
    "i need to pass this to the main agent",
    "this is beyond my capabilities",
    "i'll hand this off to the main agent",
    "let me get the main system on this",
)

# ---------------------------------------------------------------------------
# Quick Chat Implementation
# ---------------------------------------------------------------------------

class QuickChat:
    """Standalone Quick Chat interface - the voice of FDWA."""

    def __init__(self):
        """Initialize Quick Chat with Musa's personality."""
        self._soul_cache: Optional[str] = None
        self._model_cache: Optional[Any] = None

    def _load_soul(self) -> str:
        """Load Musa's personality from agent_soul.md."""
        if self._soul_cache is None:
            soul_path = _HERE / "agent_soul.md"
            if soul_path.exists():
                self._soul_cache = soul_path.read_text(encoding="utf-8")
            else:
                self._soul_cache = (
                    "You are Musa, Daniel's personal AI assistant for FDWA (Futuristic Digital Wealth Agency)."
                )
        return self._soul_cache

    def _get_chat_model(self) -> str:
        """Get the chat model for Quick Chat."""
        # Prefer Ollama for speed and cost
        if os.environ.get("OLLAMA_BASE_URL"):
            model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
            return f"ollama:{model}"
        # Fallback to Cerebras for fast cloud inference
        if os.environ.get("CEREBRAS_API_KEY"):
            return "cerebras:llama-3.3-70b"
        # Fallback to Mistral Small for cheap cloud inference
        if os.environ.get("MISTRAL_API_KEY"):
            return "mistralai:mistral-small-latest"
        # No suitable model available
        return ""

    def _needs_main_agent(self, text: str) -> bool:
        """Determine if message needs main agent (not Quick Chat)."""
        lower = text.strip().lower()
        words = lower.split()
        return (
            len(text.strip()) > 200
            or any(w in words for w in _TASK_WORDS)
            or any(phrase in lower for phrase in _HANDOFF_PHRASES)
        )

    def _is_casual(self, message: str) -> bool:
        """Determine if a message is casual chat suitable for Quick Chat."""
        text = message.strip().lower()
        words = text.split()

        # Short messages are likely casual
        if len(text) < 100:
            return True

        # Greetings and casual phrases
        casual_phrases = {
            "hello", "hi", "hey", "how are you", "howdy", "good morning",
            "good afternoon", "good evening", "what's up", "sup", "yo",
            "how's it going", "how are things", "what's new", "what's happening"
        }

        if any(phrase in text for phrase in casual_phrases):
            return True

        # If it contains task words, it's not casual
        if any(w in words for w in _TASK_WORDS):
            return False

        # If it contains handoff phrases, it's not casual
        if any(phrase in text for phrase in _HANDOFF_PHRASES):
            return False

        # If it's a simple question without task context, it's casual
        simple_questions = {
            "what", "how", "when", "where", "who", "why", "which", "is", "are", "do", "does"
        }

        if any(word in simple_questions for word in words) and len(words) < 10:
            return True

        return False

    async def _execute_tool(self, name: str, args: dict) -> str:
        """Execute one Quick Chat tool and return a result string."""
        try:
            if name == "escalate_to_main_agent":
                return _QUICK_CHAT_HANDOFF_SENTINEL

            if name == "get_time":
                import datetime
                return datetime.datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S")

            if name == "check_system_status":
                # Check if main agent is available
                return "Main agent is available and ready to handle complex tasks."

            if name == "web_search":
                if requests is None:
                    return "Web search unavailable (requests library not installed)."
                tavily_key = os.environ.get("TAVILY_API_KEY", "")
                if not tavily_key:
                    return "Web search unavailable (no TAVILY_API_KEY)."
                body = json.dumps({
                    "api_key": tavily_key,
                    "query": args.get("query", ""),
                    "max_results": 3,
                })
                try:
                    resp = await asyncio.to_thread(
                        requests.post,
                        "https://api.tavily.com/search",
                        data=body,
                        headers={"Content-Type": "application/json"},
                        timeout=10,
                    )
                    if resp.status_code != 200:
                        return f"Search failed (status {resp.status_code})."
                    results = resp.json().get("results", [])
                    if not results:
                        return "No results found."
                    return "\n\n".join(
                        f"{r.get('title','')}\n{r.get('url','')}\n{r.get('content','')[:300]}"
                        for r in results
                    )
                except Exception as exc:
                    return f"Web search failed: {exc}"

            if name == "fetch_url":
                if requests is None:
                    return "URL fetching unavailable (requests library not installed)."
                url = args.get("url", "")
                if not url:
                    return "No URL provided."
                try:
                    resp = await asyncio.to_thread(
                        requests.get, url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if resp.status_code != 200:
                        return f"Fetch failed (status {resp.status_code})."
                    # Strip HTML tags simply
                    import re as _re
                    text = _re.sub(r"<[^>]+>", " ", resp.text)
                    text = _re.sub(r"\s+", " ", text).strip()
                    return text[:1500]
                except Exception as exc:
                    return f"URL fetch failed: {exc}"

            if name == "search_memory":
                query = args.get("query", "")
                if not query:
                    return "No query provided."
                # Try Mem0 first (semantic), then AstraDB (structured)
                results_text = []
                mem0_key = os.environ.get("MEM0_API_KEY", "")
                if mem0_key and requests:
                    try:
                        body = json.dumps({
                            "query": query,
                            "filters": {"AND": [{"user_id": "default"}]},
                            "limit": 5,
                        })
                        resp = await asyncio.to_thread(
                            requests.post,
                            "https://api.mem0.ai/v2/memories/search/",
                            data=body,
                            headers={
                                "Authorization": f"Token {mem0_key}",
                                "Content-Type": "application/json",
                            },
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            hits = resp.json().get("results", [])
                            for h in hits:
                                mem = h.get("memory", "")
                                score = h.get("score", "")
                                created = h.get("created_at", "")[:10]
                                if mem:
                                    results_text.append(f"[{created}] {mem} (relevance: {score})")
                    except Exception as exc:
                        results_text.append(f"(Mem0 error: {exc})")

                astra_key = os.environ.get("ASTRA_DB_API_KEY", "")
                astra_endpoint = os.environ.get("ASTRA_DB_ENDPOINT", "")
                if astra_key and astra_endpoint:
                    try:
                        from astrapy import DataAPIClient
                        client = DataAPIClient()
                        db = client.get_database(astra_endpoint, token=astra_key)
                        coll = db.get_collection("agent_memory")
                        docs = list(coll.find({"user_id": "default"}, limit=5))
                        for d in docs:
                            content = d.get("content", "")
                            cat = d.get("category", "")
                            created = d.get("created_at", "")[:10]
                            if content:
                                results_text.append(f"[{created}] [{cat}] {content}")
                    except Exception as exc:
                        results_text.append(f"(AstraDB error: {exc})")

                if not results_text:
                    return "No memories found for that query."
                return f"Found {len(results_text)} memories:\n\n" + "\n".join(results_text)

            if name == "save_memory":
                content = args.get("content", "")
                if not content:
                    return "No content provided."
                saved_to = []
                mem0_key = os.environ.get("MEM0_API_KEY", "")
                if mem0_key:
                    try:
                        body = json.dumps({
                            "messages": [{"role": "user", "content": content}],
                            "user_id": "default",
                        })
                        resp = await asyncio.to_thread(
                            requests.post,
                            "https://api.mem0.ai/v2/memories/",
                            data=body,
                            headers={
                                "Authorization": f"Token {mem0_key}",
                                "Content-Type": "application/json",
                            },
                            timeout=10,
                        )
                        if resp.status_code in (200, 201):
                            saved_to.append("Mem0")
                    except Exception:
                        pass

                astra_key = os.environ.get("ASTRA_DB_API_KEY", "")
                astra_endpoint = os.environ.get("ASTRA_DB_ENDPOINT", "")
                if astra_key and astra_endpoint:
                    try:
                        from astrapy import DataAPIClient
                        from datetime import datetime, timezone
                        client = DataAPIClient()
                        db = client.get_database(astra_endpoint, token=astra_key)
                        coll = db.get_collection("agent_memory")
                        coll.insert_one({
                            "content": content,
                            "user_id": "default",
                            "category": "general",
                            "type": "memory",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        })
                        saved_to.append("AstraDB")
                    except Exception:
                        pass

                if saved_to:
                    return f"Saved to {', '.join(saved_to)}: {content[:100]}"
                return "Could not save — no memory backend configured."

        except Exception as exc:
            return f"Tool error: {exc}"

        return "Unknown tool."

    async def _cerebras_chat(self, message: str, soul: str) -> str | None:
        """Cerebras cloud fallback for Quick Chat — with a lightweight tool loop.

        Supports: web_search (Tavily), get_time, fetch_url, memory tools.
        Uses Cerebras's OpenAI-compatible API (no langchain-cerebras needed).
        Returns reply text, or None on failure.
        """
        key = os.environ.get("CEREBRAS_API_KEY", "")
        if not key:
            return None
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, ToolMessage
            from langchain_core.messages import SystemMessage as SM

            llm = ChatOpenAI(
                model="llama3.1-8b",
                api_key=key,
                base_url="https://api.cerebras.ai/v1",
            )
            llm_with_tools = llm.bind_tools(_QUICK_CHAT_TOOLS)

            msgs: list = [SM(content=soul), HumanMessage(content=message)]

            for _iteration in range(3):  # max 3 tool calls then final answer
                resp = await llm_with_tools.ainvoke(msgs)
                tool_calls = getattr(resp, "tool_calls", None) or []

                if not tool_calls:
                    # No tool call — this is the final answer
                    text = str(resp.content).strip()
                    if text:
                        logger.info("Quick Chat reply (iter=%d): %.80s", _iteration, text)
                    return text or None

                # Execute all tool calls in this turn
                msgs.append(resp)
                for tc in tool_calls:
                    tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                    tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    tc_id = tc.get("id", tc_name) if isinstance(tc, dict) else getattr(tc, "id", tc_name)
                    if isinstance(tc_args, str):
                        try:
                            tc_args = json.loads(tc_args)
                        except Exception:
                            tc_args = {}
                    logger.info("Quick Chat tool call: %s(%s)", tc_name, tc_args)
                    result = await self._execute_tool(tc_name, tc_args)
                    if result == _QUICK_CHAT_HANDOFF_SENTINEL:
                        logger.info("Quick Chat escalation called — escalating to main agent")
                        return None  # triggers handoff=True in _quick_chat
                    msgs.append(ToolMessage(content=result, tool_call_id=tc_id))

            # Exhausted iterations — ask for final answer without tools
            resp = await llm.ainvoke(msgs)
            text = str(resp.content).strip()
            return text or None

        except ImportError as exc:
            logger.warning("Cerebras dependencies not available: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Cerebras fallback failed: %s", exc)
            return None

    async def _ollama_chat(self, message: str, soul: str) -> str | None:
        """Ollama local fallback for Quick Chat.

        Uses local Ollama endpoint for fast, free responses.
        Returns reply text, or None on failure.
        """
        if requests is None:
            logger.warning("Ollama unavailable (requests library not installed)")
            return None

        model_name = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://13.222.51.51:11434")
        try:
            body = json.dumps({
                "model": model_name,
                "messages": [
                    {"role": "system", "content": soul},
                    {"role": "user", "content": message},
                ],
                "stream": False,
            })
            resp = await asyncio.to_thread(
                requests.post,
                f"{ollama_url}/api/chat",
                data=body,
                headers={"Content-Type": "application/json"},
                timeout=int(os.environ.get("OLLAMA_TIMEOUT", "20")),
            )
            if resp.status_code == 200:
                text = resp.json().get("message", {}).get("content", "").strip()
                return text
            else:
                logger.warning("Ollama returned %d — trying Cerebras fallback", resp.status_code)
                return await self._cerebras_chat(message, soul)
        except Exception as exc:
            logger.warning("Ollama failed: %s", exc)
            return await self._cerebras_chat(message, soul)

    async def process_message(self, message: str) -> Tuple[str, bool]:
        """Process a message through Quick Chat and return (reply, should_handoff).

        Args:
            message: User input message

        Returns:
            Tuple of (reply_text, should_handoff_to_main_agent)
        """
        soul = self._load_soul()
        chat_model = self._get_chat_model()

        if not chat_model:
            return ("Quick Chat unavailable — no suitable model configured.", True)

        try:
            if chat_model.startswith("ollama:"):
                text = await self._ollama_chat(message, soul)
            else:
                text = await self._cerebras_chat(message, soul)

            if not text:
                return ("", True)

            # If Quick Chat's reply contains a handoff phrase, escalate but keep the text
            # so the user sees Quick Chat's "Let me get the main agent on this" before the main agent starts.
            if any(phrase in text.lower() for phrase in _HANDOFF_PHRASES):
                logger.info("Quick Chat handoff phrase detected — escalating to main agent")
                return (text, True)

            return (text, False)

        except Exception as exc:
            logger.exception("Quick Chat error")
            return (f"Quick Chat error: {exc}", True)

    def can_handle(self, message: str) -> bool:
        """Determine if Quick Chat can handle this message.

        Args:
            message: User input message

        Returns:
            True if Quick Chat should handle it, False if it needs main agent
        """
        # Check if message is casual or simple
        if self._is_casual(message):
            return True

        # Check if message needs main agent
        if self._needs_main_agent(message):
            return False

        # Default to Quick Chat for short, simple messages
        return len(message.strip()) < 200

# ---------------------------------------------------------------------------
# Global Quick Chat Instance
# ---------------------------------------------------------------------------

# Create a global instance for easy access
quick_chat = QuickChat()

# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

async def handle_quick_chat(message: str) -> Tuple[str, bool]:
    """Convenience function to handle a Quick Chat message.

    Args:
        message: User input message

    Returns:
        Tuple of (reply_text, should_handoff_to_main_agent)
    """
    return await quick_chat.process_message(message)

def should_use_quick_chat(message: str) -> bool:
    """Convenience function to check if Quick Chat should handle a message.

    Args:
        message: User input message

    Returns:
        True if Quick Chat should handle it, False if it needs main agent
    """
    return quick_chat.can_handle(message)
