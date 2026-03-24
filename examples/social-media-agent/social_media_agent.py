#!/usr/bin/env python3
"""Social Media Agent.

End-to-end agent: research → Remotion video → post to social platforms.
Uses upload-post (primary) + Composio (fallback) for posting.

Usage:
    python social_media_agent.py "Make a 15-second TikTok about BTC price today"
    python social_media_agent.py "Post a text update about ETH on Twitter and LinkedIn"
    python social_media_agent.py "Create a YouTube video about AI agent trends"
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import yaml

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

EXAMPLE_DIR = Path(__file__).parent
SKILLS_ROOT = EXAMPLE_DIR / ".." / ".." / "libs" / "cli" / "deepagents_cli" / "built_in_skills"
WORKSPACE = EXAMPLE_DIR / "workspace"
console = Console()


# ── Tools ────────────────────────────────────────────────────────────────────

@tool
def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web for current prices, news, and trending topics.

    Args:
        query: Specific search query
        max_results: Number of results (default 5)

    Returns:
        Search results with titles, URLs, and excerpts.
    """
    try:
        from tavily import TavilyClient
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return {"error": "TAVILY_API_KEY not set — using SerpAPI fallback"}
        return TavilyClient(api_key=api_key).search(query, max_results=max_results)
    except ImportError:
        pass
    try:
        import requests
        serpapi_key = os.environ.get("SERPAPI_API_KEY") or os.environ.get("SERP_API_KEY")
        if not serpapi_key:
            return {"error": "No search API key set (TAVILY_API_KEY or SERPAPI_API_KEY)"}
        resp = requests.get(
            "https://serpapi.com/search",
            params={"q": query, "num": max_results, "api_key": serpapi_key},
            timeout=10,
        )
        return resp.json()
    except Exception as exc:
        return {"error": f"Search failed: {exc}"}


@tool
def execute_script(script: str, *args: str) -> str:  # noqa: ANN002
    """Run a built-in skill script and return its output.

    Args:
        script: Script path relative to built_in_skills/, e.g.
                "remotion/create_project.py" or "upload-post/post_video.py"
        *args:  CLI arguments to pass to the script.

    Returns:
        Combined stdout + stderr from the script.

    Examples:
        execute_script("remotion/create_project.py",
            "--title", "BTC Today", "--duration", "15", "--template", "tiktok")
        execute_script("remotion/render_video.py",
            "--project", "./remotion-projects/btc-today", "--out", "workspace/btc.mp4")
        execute_script("upload-post/post_video.py",
            "--file", "workspace/btc.mp4", "--title", "BTC hits $85K",
            "--platforms", "youtube", "facebook")
    """
    script_path = (SKILLS_ROOT / "scripts" / script).resolve()
    # Security: only allow scripts inside built_in_skills/
    if not str(script_path).startswith(str(SKILLS_ROOT.resolve())):
        return f"ERROR: Script must be inside built_in_skills/: {script}"
    if not script_path.exists():
        # Try as direct path from SKILLS_ROOT (without /scripts/ prefix)
        script_path = (SKILLS_ROOT / script).resolve()
    if not script_path.exists():
        return f"ERROR: Script not found: {script}"

    cmd = [sys.executable, str(script_path), *args]
    env = {**os.environ}
    # Add ffmpeg to PATH if winget-installed
    ffmpeg_dir = (
        Path.home()
        / "AppData/Local/Microsoft/WinGet/Packages"
        / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        / "ffmpeg-8.1-full_build/bin"
    )
    if ffmpeg_dir.exists():
        env["PATH"] = str(ffmpeg_dir) + os.pathsep + env.get("PATH", "")

    # Run from the agent's own directory so relative paths work
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(EXAMPLE_DIR),
        env=env,
        timeout=600,  # 10 min max for long renders
    )
    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr
    return output.strip() or f"(exit {result.returncode})"


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file (creates parent directories if needed).

    Args:
        file_path: Relative path from agent directory (e.g. workspace/caption.md)
        content: Text content to write

    Returns:
        Confirmation message with absolute path.
    """
    path = (EXAMPLE_DIR / file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Written: {path} ({len(content)} chars)"


@tool
def read_file(file_path: str) -> str:
    """Read a file and return its contents.

    Args:
        file_path: Relative path from agent directory or absolute path

    Returns:
        File contents as a string.
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = (EXAMPLE_DIR / file_path).resolve()
    if not path.exists():
        return f"ERROR: File not found: {path}"
    return path.read_text(encoding="utf-8")


# ── Agent factory ─────────────────────────────────────────────────────────────

def load_subagents(config_path: Path) -> list:
    """Load subagent definitions from YAML and wire up tools."""
    available_tools = {
        "web_search": web_search,
        "execute_script": execute_script,
        "write_file": write_file,
        "read_file": read_file,
    }
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    subagents = []
    for name, spec in config.items():
        subagent = {
            "name": name,
            "description": spec["description"],
            "system_prompt": spec["system_prompt"],
        }
        if "model" in spec:
            subagent["model"] = spec["model"]
        if "tools" in spec:
            subagent["tools"] = [available_tools[t] for t in spec["tools"]]
        subagents.append(subagent)
    return subagents


def create_social_agent():
    """Create the social media agent wired with all tools and subagents."""
    WORKSPACE.mkdir(exist_ok=True)
    return create_deep_agent(
        memory=["./AGENTS.md"],
        skills=["./skills/"],
        tools=[web_search, execute_script, write_file, read_file],
        subagents=load_subagents(EXAMPLE_DIR / "subagents.yaml"),
        backend=FilesystemBackend(root_dir=EXAMPLE_DIR),
    )


# ── Display ───────────────────────────────────────────────────────────────────

class AgentDisplay:
    """Rich terminal display for agent progress."""

    def __init__(self) -> None:
        self.printed_count = 0
        self.spinner = Spinner("dots", text="Thinking...")

    def update_status(self, status: str) -> None:
        """Update spinner text."""
        self.spinner = Spinner("dots", text=status)

    def print_message(self, msg: object) -> None:
        """Print a message with formatting."""
        if isinstance(msg, HumanMessage):
            console.print(Panel(str(msg.content), title="You", border_style="blue"))

        elif isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, list):
                text_parts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = "\n".join(text_parts)
            if content and content.strip():
                console.print(Panel(Markdown(content), title="Agent", border_style="green"))
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.get("name", "unknown")
                    args = tc.get("args", {})
                    if name == "task":
                        desc = args.get("description", "working...")
                        console.print(f"  [bold magenta]>> Delegating:[/] {desc[:70]}...")
                        self.update_status(f"Subagent: {desc[:40]}...")
                    elif name == "execute_script":
                        script = args.get("script", "")
                        rest = list(args.values())[1:]
                        console.print(f"  [bold cyan]>> Script:[/] {script} {' '.join(str(a) for a in rest)[:50]}")
                        self.update_status(f"Running {script}...")
                    elif name == "web_search":
                        q = args.get("query", "")
                        console.print(f"  [bold blue]>> Search:[/] {q[:60]}...")
                        self.update_status(f"Searching: {q[:30]}...")
                    elif name == "write_file":
                        console.print(f"  [bold yellow]>> Writing:[/] {args.get('file_path', '')}")
                    elif name == "read_file":
                        console.print(f"  [dim]>> Reading:[/] {args.get('file_path', '')}")

        elif isinstance(msg, ToolMessage):
            name = getattr(msg, "name", "")
            content = str(msg.content)
            if name == "execute_script":
                if "error" in content.lower() or "exit 1" in content:
                    console.print(f"  [red]✗ Script failed:[/] {content[:120]}")
                else:
                    # Show last meaningful line (e.g. "Render complete: ... 0.2 MB")
                    last = [ln for ln in content.splitlines() if ln.strip()]
                    console.print(f"  [green]✓[/] {last[-1] if last else 'done'}")
            elif name == "task":
                console.print("  [green]✓ Subagent complete[/]")
            elif name == "web_search":
                console.print("  [green]✓ Search results received[/]")
            elif name == "write_file":
                console.print(f"  [green]✓ {content}[/]")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    """Run the social media agent."""
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = (
            "Research the current BTC price, create a 15-second TikTok-format video "
            "showing the price, and post it to YouTube and Facebook."
        )

    console.print()
    console.print("[bold blue]Social Media Agent[/]")
    console.print(f"[dim]Task: {task}[/]")
    console.print()

    agent = create_social_agent()
    display = AgentDisplay()

    with Live(
        display.spinner, console=console, refresh_per_second=10, transient=True
    ) as live:
        async for chunk in agent.astream(
            {"messages": [("user", task)]},
            config={"configurable": {"thread_id": "social-media-demo"}},
            stream_mode="values",
        ):
            if "messages" in chunk:
                messages = chunk["messages"]
                if len(messages) > display.printed_count:
                    live.stop()
                    for msg in messages[display.printed_count:]:
                        display.print_message(msg)
                    display.printed_count = len(messages)
                    live.start()
                    live.update(display.spinner)

    console.print()
    console.print("[bold green]✓ Done![/]")
    console.print(f"[dim]Outputs saved to: {WORKSPACE}[/]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/]")