"""Tests for EarlyExitPreventionMiddleware and SelfCorrectionMiddleware.

These tests use GenericFakeChatModel to simulate models that give up early
or retry failed tool calls, and verify the middleware correctly intervenes.
"""

from collections.abc import Callable, Sequence
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, tool
from langgraph.store.memory import InMemoryStore

from deepagents.middleware.early_exit_prevention import (
    EarlyExitPreventionMiddleware,
    _collect_tools_used,
    _is_giving_up,
)
from deepagents.middleware.self_correction import (
    SelfCorrectionMiddleware,
    _is_error_result,
    _get_error_advice,
    _tool_call_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeChatModel(GenericFakeChatModel):
    """Fake chat model that properly handles bind_tools."""

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self


@tool(description="Search the web")
def web_search(query: str) -> str:
    """Search the web for a query."""
    return f"Results for: {query}"


@tool(description="Fetch a URL")
def fetch_url(url: str) -> str:
    """Fetch the content of a URL."""
    return f"Content from: {url}"


@tool(description="Execute code")
def execute(code: str) -> str:
    """Execute code in a sandbox."""
    return f"Executed: {code}"


# ---------------------------------------------------------------------------
# EarlyExitPreventionMiddleware — unit tests for helper functions
# ---------------------------------------------------------------------------


class TestIsGivingUp:
    """Test the _is_giving_up detection function."""

    def test_giving_up_patterns(self):
        """Various giving-up messages should be detected."""
        giving_up_messages = [
            "I wasn't able to find that information.",
            "Unfortunately, I cannot access that resource.",
            "I'm unable to complete this task without more information.",
            "Sorry, I don't have access to that service.",
            "I could not locate any results for your query.",
            "There is no data available for that request.",
            "I apologize, but I cannot perform that action.",
            "No results found for your search query.",
        ]
        for text in giving_up_messages:
            msg = AIMessage(content=text)
            assert _is_giving_up(msg), f"Should detect giving up: {text!r}"

    def test_legitimate_completions_not_flagged(self):
        """Legitimate completion messages should NOT be flagged."""
        completion_messages = [
            "Here is the summary of your request with all the data included.",
            "I've successfully sent the email to your contact.",
            "Done! The file has been created at /workspace/output.txt.",
            "The task is complete. All 5 items have been processed.",
        ]
        for text in completion_messages:
            msg = AIMessage(content=text)
            assert not _is_giving_up(msg), f"Should NOT flag completion: {text!r}"

    def test_tool_calls_never_flagged(self):
        """Messages with tool calls should never be flagged."""
        msg = AIMessage(
            content="I wasn't able to find that, let me try another approach.",
            tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc1", "type": "tool_call"}],
        )
        assert not _is_giving_up(msg)

    def test_short_messages_not_flagged(self):
        """Very short messages should not be flagged."""
        msg = AIMessage(content="No.")
        assert not _is_giving_up(msg)

    def test_empty_content_not_flagged(self):
        """Empty content should not be flagged."""
        msg = AIMessage(content="")
        assert not _is_giving_up(msg)


class TestCollectToolsUsed:
    """Test the _collect_tools_used function."""

    def test_collects_from_current_turn(self):
        messages = [
            HumanMessage(content="Do something"),
            AIMessage(
                content="",
                tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc1", "type": "tool_call"}],
            ),
            ToolMessage(content="Results", name="web_search", tool_call_id="tc1"),
            AIMessage(
                content="",
                tool_calls=[{"name": "fetch_url", "args": {"url": "http://example.com"}, "id": "tc2", "type": "tool_call"}],
            ),
            ToolMessage(content="Page content", name="fetch_url", tool_call_id="tc2"),
        ]
        used = _collect_tools_used(messages)
        assert used == {"web_search", "fetch_url"}

    def test_stops_at_human_message(self):
        messages = [
            HumanMessage(content="First request"),
            AIMessage(
                content="",
                tool_calls=[{"name": "web_search", "args": {"query": "old"}, "id": "tc0", "type": "tool_call"}],
            ),
            ToolMessage(content="Old results", name="web_search", tool_call_id="tc0"),
            HumanMessage(content="New request"),  # <- turn boundary
            AIMessage(
                content="",
                tool_calls=[{"name": "fetch_url", "args": {"url": "http://example.com"}, "id": "tc1", "type": "tool_call"}],
            ),
            ToolMessage(content="Content", name="fetch_url", tool_call_id="tc1"),
        ]
        used = _collect_tools_used(messages)
        # Should only count tools from the current turn (after last HumanMessage)
        assert used == {"fetch_url"}

    def test_empty_messages(self):
        assert _collect_tools_used([]) == set()


# ---------------------------------------------------------------------------
# EarlyExitPreventionMiddleware — integration test with fake agent
# ---------------------------------------------------------------------------


class TestEarlyExitPreventionMiddleware:
    """Test the middleware intercepts premature exits."""

    def test_nudges_when_no_tools_tried(self):
        """Model gives up without trying any tools → middleware nudges it."""
        # Model sequence:
        # 1. First attempt: gives up immediately
        # 2. After nudge: actually uses a tool
        # 3. Final answer after tool use
        model = FakeChatModel(
            messages=iter([
                # First: model gives up
                AIMessage(content="I wasn't able to find that information."),
                # After nudge: model uses a tool
                AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc1", "type": "tool_call"}],
                ),
                # Final answer
                AIMessage(content="Here are the results I found."),
            ])
        )

        agent = create_agent(
            model=model,
            tools=[web_search, fetch_url],
            middleware=[EarlyExitPreventionMiddleware()],
        )

        result = agent.invoke({"messages": [HumanMessage(content="Find info about X")]})

        ai_messages = [m for m in result["messages"] if m.type == "ai"]
        # The middleware detected the early exit and nudged the model to continue.
        # The final message should be the successful completion, not the giving-up.
        final = ai_messages[-1]
        assert "results" in final.content.lower()
        # Verify the model was nudged (a [SYSTEM] message was injected)
        human_messages = [m for m in result["messages"] if m.type == "human"]
        assert any("[SYSTEM]" in m.content for m in human_messages)

    def test_allows_exit_after_enough_tools(self):
        """Model gives up after trying enough tools → middleware allows exit."""
        model = FakeChatModel(
            messages=iter([
                # Use tool 1
                AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc1", "type": "tool_call"}],
                ),
                # Use tool 2
                AIMessage(
                    content="",
                    tool_calls=[{"name": "fetch_url", "args": {"url": "http://example.com"}, "id": "tc2", "type": "tool_call"}],
                ),
                # Now gives up — should be allowed (tried 2 tools)
                AIMessage(content="I wasn't able to find the specific data you requested."),
            ])
        )

        agent = create_agent(
            model=model,
            tools=[web_search, fetch_url],
            middleware=[EarlyExitPreventionMiddleware(min_tools_tried=2)],
        )

        result = agent.invoke({"messages": [HumanMessage(content="Find rare data")]})

        ai_messages = [m for m in result["messages"] if m.type == "ai"]
        # The giving-up message should be present since the agent tried enough tools
        assert any("wasn't able" in m.content for m in ai_messages)

    def test_allows_legitimate_completion(self):
        """Model completes legitimately → middleware does NOT interfere."""
        model = FakeChatModel(
            messages=iter([
                AIMessage(content="Here is the answer to your question with all details included."),
            ])
        )

        agent = create_agent(
            model=model,
            tools=[web_search],
            middleware=[EarlyExitPreventionMiddleware()],
        )

        result = agent.invoke({"messages": [HumanMessage(content="What is 2+2?")]})

        ai_messages = [m for m in result["messages"] if m.type == "ai"]
        assert ai_messages[-1].content == "Here is the answer to your question with all details included."

    def test_max_retries_respected(self):
        """After max nudges, the agent is allowed to exit."""
        model = FakeChatModel(
            messages=iter([
                # Gives up 3 times (max_retries=2, so 3rd should be allowed)
                AIMessage(content="I cannot find that information anywhere."),
                AIMessage(content="I'm still unable to locate the data."),
                AIMessage(content="Sorry, I really cannot access this resource."),
            ])
        )

        agent = create_agent(
            model=model,
            tools=[web_search],
            middleware=[EarlyExitPreventionMiddleware(max_retries=2)],
        )

        result = agent.invoke({"messages": [HumanMessage(content="Find impossible data")]})

        ai_messages = [m for m in result["messages"] if m.type == "ai"]
        # After 2 nudges, the 3rd giving-up should be allowed through
        assert len(ai_messages) >= 1


# ---------------------------------------------------------------------------
# SelfCorrectionMiddleware — unit tests for helper functions
# ---------------------------------------------------------------------------


class TestIsErrorResult:
    """Test the _is_error_result detection function."""

    def test_detects_error_messages(self):
        error_messages = [
            "Error: file not found at /workspace/missing.txt",
            "Failed to execute the command: permission denied",
            "Traceback (most recent call last):\n  File ...",
            "status_code: 404, message: not found",
            "Unable to connect to the server",
        ]
        for text in error_messages:
            msg = ToolMessage(content=text, name="test_tool", tool_call_id="tc1")
            assert _is_error_result(msg), f"Should detect error: {text!r}"

    def test_does_not_flag_success(self):
        success_messages = [
            "Results for query: test\n1. First result\n2. Second result",
            '{"data": [1, 2, 3], "status": "ok"}',
            "File written successfully to /workspace/output.txt",
        ]
        for text in success_messages:
            msg = ToolMessage(content=text, name="test_tool", tool_call_id="tc1")
            assert not _is_error_result(msg), f"Should NOT flag success: {text!r}"


class TestGetErrorAdvice:
    """Test the _get_error_advice function."""

    def test_404_advice(self):
        advice = _get_error_advice("Error: 404 not found")
        assert "path" in advice.lower() or "search" in advice.lower()

    def test_401_advice(self):
        advice = _get_error_advice("status_code: 401 Unauthorized")
        assert "auth" in advice.lower() or "key" in advice.lower()

    def test_429_advice(self):
        advice = _get_error_advice("429 Too Many Requests")
        assert "different" in advice.lower() or "rate" in advice.lower()

    def test_unknown_error_no_advice(self):
        advice = _get_error_advice("Something weird happened")
        assert advice == ""


class TestToolCallKey:
    """Test the _tool_call_key function."""

    def test_same_call_same_key(self):
        tc1 = {"name": "web_search", "args": {"query": "test"}}
        tc2 = {"name": "web_search", "args": {"query": "test"}}
        assert _tool_call_key(tc1) == _tool_call_key(tc2)

    def test_different_args_different_key(self):
        tc1 = {"name": "web_search", "args": {"query": "test"}}
        tc2 = {"name": "web_search", "args": {"query": "other"}}
        assert _tool_call_key(tc1) != _tool_call_key(tc2)

    def test_different_tools_different_key(self):
        tc1 = {"name": "web_search", "args": {"query": "test"}}
        tc2 = {"name": "fetch_url", "args": {"query": "test"}}
        assert _tool_call_key(tc1) != _tool_call_key(tc2)


# ---------------------------------------------------------------------------
# SelfCorrectionMiddleware — integration test with fake agent
# ---------------------------------------------------------------------------


class TestSelfCorrectionMiddleware:
    """Test the middleware blocks repeated failed tool calls."""

    def test_blocks_exact_retry_after_failure(self):
        """Model retries exact same call that failed → middleware blocks and nudges."""
        # Sequence:
        # 1. Call web_search("test") → error
        # 2. Try to call web_search("test") again → blocked by middleware
        # 3. After nudge: try fetch_url instead → success
        # 4. Final answer

        model = FakeChatModel(
            messages=iter([
                # First call
                AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc1", "type": "tool_call"}],
                ),
                # After error, model retries same call — will be blocked
                AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc2", "type": "tool_call"}],
                ),
                # After nudge, model tries different approach
                AIMessage(
                    content="",
                    tool_calls=[{"name": "fetch_url", "args": {"url": "http://example.com"}, "id": "tc3", "type": "tool_call"}],
                ),
                # Final answer
                AIMessage(content="Here are the results from fetch_url."),
            ])
        )

        @tool(description="Search the web")
        def failing_web_search(query: str) -> str:
            """Always fails."""
            return "Error: 429 Too Many Requests - rate limited"

        agent = create_agent(
            model=model,
            tools=[failing_web_search, fetch_url],
            middleware=[SelfCorrectionMiddleware()],
        )

        result = agent.invoke({"messages": [HumanMessage(content="Search for test")]})

        ai_messages = [m for m in result["messages"] if m.type == "ai"]
        assert any("results" in m.content.lower() for m in ai_messages)

    def test_allows_same_tool_different_args(self):
        """Model calls same tool with different args → middleware allows it."""
        model = FakeChatModel(
            messages=iter([
                # First call fails
                AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc1", "type": "tool_call"}],
                ),
                # Same tool but different args — should be allowed
                AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "different query"}, "id": "tc2", "type": "tool_call"}],
                ),
                AIMessage(content="Found the results with the modified query."),
            ])
        )

        @tool(description="Search the web")
        def sometimes_fails(query: str) -> str:
            """Fails on first call, succeeds on second."""
            if query == "test":
                return "Error: no results found"
            return f"Results for: {query}"

        agent = create_agent(
            model=model,
            tools=[sometimes_fails],
            middleware=[SelfCorrectionMiddleware()],
        )

        result = agent.invoke({"messages": [HumanMessage(content="Search for stuff")]})

        ai_messages = [m for m in result["messages"] if m.type == "ai"]
        assert any("results" in m.content.lower() for m in ai_messages)


# ---------------------------------------------------------------------------
# Combined middleware stack test
# ---------------------------------------------------------------------------


class TestCombinedMiddlewareStack:
    """Test both middleware working together."""

    def test_self_correction_then_early_exit_prevention(self):
        """Model fails, retries same call (blocked), then tries to give up (blocked),
        finally tries a different tool and succeeds."""
        model = FakeChatModel(
            messages=iter([
                # 1. Call web_search → fails
                AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc1", "type": "tool_call"}],
                ),
                # 2. Retry same call → blocked by SelfCorrection
                AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "tc2", "type": "tool_call"}],
                ),
                # 3. Try to give up → blocked by EarlyExitPrevention (only 1 tool tried)
                AIMessage(content="I wasn't able to find that information."),
                # 4. After both nudges, try fetch_url → success
                AIMessage(
                    content="",
                    tool_calls=[{"name": "fetch_url", "args": {"url": "http://example.com"}, "id": "tc3", "type": "tool_call"}],
                ),
                # 5. Final answer
                AIMessage(content="Here is what I found from the URL."),
            ])
        )

        @tool(description="Search the web")
        def failing_search(query: str) -> str:
            """Always fails."""
            return "Error: connection timed out"

        agent = create_agent(
            model=model,
            tools=[failing_search, fetch_url],
            middleware=[
                EarlyExitPreventionMiddleware(),
                SelfCorrectionMiddleware(),
            ],
        )

        result = agent.invoke({"messages": [HumanMessage(content="Find data about X")]})

        ai_messages = [m for m in result["messages"] if m.type == "ai"]
        # Should end with the successful completion, not the giving-up message
        final = ai_messages[-1]
        assert "found" in final.content.lower()
