#!/usr/bin/env python3
"""Install example agents from the examples/ folder into ~/.deepagents/.

Reads each example's AGENTS.md / prompts, skills, and subagent definitions,
then writes them to ~/.deepagents/{name}/ so they appear in `deepagents list`
and can be selected with `deepagents -a <name>`.

Usage:
    python scripts/install_example_agents.py            # install all
    python scripts/install_example_agents.py --list     # preview only
    python scripts/install_example_agents.py researcher sql-agent  # specific agents
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
DEEPAGENTS_HOME = Path.home() / ".deepagents"

# ---------------------------------------------------------------------------
# Agent definitions
# Each entry maps to one ~/.deepagents/{name}/ directory.
# ---------------------------------------------------------------------------

AGENTS: list[dict] = [
    # ── Deep Research agent ─────────────────────────────────────────────────
    {
        "name": "researcher",
        "agents_md_source": None,  # built from prompts.py
        "agents_md_content": """\
# Deep Research Agent

You are a deep research assistant. You conduct thorough, multi-source research
by delegating to specialised sub-agents and synthesising their findings into
comprehensive, well-cited reports.

## Workflow

1. **Plan** — Use `write_todos` to break the research into focused tasks.
2. **Save the request** — Write the user's question to `/research_request.md`.
3. **Research** — Delegate ALL research to sub-agents via `task()`. Never
   conduct web searches yourself.
4. **Synthesise** — Review findings, consolidate citations (each unique URL
   gets one number across all sub-agent outputs).
5. **Write Report** — Produce a comprehensive final report to
   `/final_report.md`.
6. **Verify** — Re-read `/research_request.md` and confirm every aspect is
   addressed.

## Research Planning Guidelines

- Batch similar tasks into a single sub-agent call.
- Simple fact-finding → 1 sub-agent.
- Comparisons or multi-faceted topics → multiple parallel sub-agents (max 3
  concurrent).
- Each sub-agent researches one specific aspect.

## Report Structure

**For comparisons:** Intro → Overview A → Overview B → Comparison → Conclusion
**For lists/rankings:** Simply list items with detail.
**For summaries:** Overview → Key concepts → Conclusion

### Formatting
- Use `##` for sections, `###` for subsections.
- Write in paragraphs — be text-heavy, not just bullets.
- No self-referential language ("I found…").
- Cite inline: `[1][2]` — assign each unique URL one number.
- End with `### Sources` listing each numbered source.

## Citation Format

```
Some important finding [1]. Another key insight [2].

### Sources
[1] Source Title: https://example.com/paper
[2] Industry Analysis: https://example.com/analysis
```
""",
        "skills": [],
        "subagents": [
            {
                "name": "web-researcher",
                "description": (
                    "Searches the web for information on a specific topic. "
                    "Always use this sub-agent for web research — never search yourself. "
                    "Pass one focused research question per call; it returns structured findings with citations."
                ),
                "model": "anthropic:claude-haiku-4-5-20251001",
                "system_prompt": """\
You are a research assistant. Your job is to find accurate, well-sourced
information on the topic you are given.

## Tools
- `web_search` — search the web for current information
- `fetch_url` — fetch a specific URL for more detail

## Process
1. Read the question carefully.
2. Start with 1-2 broad searches.
3. Follow up with narrower queries to fill gaps.
4. Stop when you can answer comprehensively (max 5 searches).

## Hard Limits
- Simple queries: 2-3 search calls maximum.
- Complex queries: up to 5 search calls maximum.
- Stop immediately when you have 3+ relevant sources.

## Response Format
Return structured findings with inline citations:

```
## Key Findings

Context engineering is critical for AI agents [1]. Performance can improve
by 40% with proper context management [2].

### Sources
[1] Guide Title: https://example.com/guide
[2] Study Title: https://example.com/study
```
""",
            }
        ],
    },

    # ── Content Writer agent ─────────────────────────────────────────────────
    {
        "name": "content-writer",
        "agents_md_source": EXAMPLES_DIR / "content-builder-agent" / "AGENTS.md",
        "skills": [
            {
                "name": "blog-post",
                "source": EXAMPLES_DIR / "content-builder-agent" / "skills" / "blog-post" / "SKILL.md",
            },
            {
                "name": "social-media",
                "source": EXAMPLES_DIR / "content-builder-agent" / "skills" / "social-media" / "SKILL.md",
            },
        ],
        "subagents": [
            {
                "name": "researcher",
                "description": (
                    "ALWAYS use this first to research any topic before writing content. "
                    "Searches the web for current information, statistics, and sources. "
                    "Tell it the topic AND the file path to save results, e.g. "
                    "'Research renewable energy and save to research/renewable-energy.md'."
                ),
                "model": "anthropic:claude-haiku-4-5-20251001",
                "system_prompt": """\
You are a research assistant. You have access to `web_search` and `write_file` tools.

## Your Tools
- `web_search(query, max_results=5)` — search the web
- `write_file(file_path, content)` — save your findings

## Your Process
1. Use `web_search` to find information on the topic.
2. Make 2-3 targeted searches with specific queries.
3. Gather key statistics, quotes, and examples.
4. Save findings to the file path specified in your task.

## Important
- The user will tell you WHERE to save the file — use that exact path.
- Always include source URLs in your findings.
- Keep findings concise but informative.
""",
            }
        ],
    },

    # ── Text-to-SQL agent ────────────────────────────────────────────────────
    {
        "name": "sql-agent",
        "agents_md_source": EXAMPLES_DIR / "text-to-sql-agent" / "AGENTS.md",
        "skills": [
            {
                "name": "query-writing",
                "source": EXAMPLES_DIR / "text-to-sql-agent" / "skills" / "query-writing" / "SKILL.md",
            },
            {
                "name": "schema-exploration",
                "source": EXAMPLES_DIR / "text-to-sql-agent" / "skills" / "schema-exploration" / "SKILL.md",
            },
        ],
        "subagents": [],
    },

    # ── NVIDIA Deep Agent ────────────────────────────────────────────────────
    {
        "name": "nvidia-researcher",
        "agents_md_source": EXAMPLES_DIR / "nvidia_deep_agent" / "src" / "AGENTS.md",
        "skills": [
            {
                "name": "cudf-analytics",
                "source": EXAMPLES_DIR / "nvidia_deep_agent" / "skills" / "cudf-analytics" / "SKILL.md",
            },
            {
                "name": "cuml-machine-learning",
                "source": EXAMPLES_DIR / "nvidia_deep_agent" / "skills" / "cuml-machine-learning" / "SKILL.md",
            },
            {
                "name": "data-visualization",
                "source": EXAMPLES_DIR / "nvidia_deep_agent" / "skills" / "data-visualization" / "SKILL.md",
            },
            {
                "name": "gpu-document-processing",
                "source": EXAMPLES_DIR / "nvidia_deep_agent" / "skills" / "gpu-document-processing" / "SKILL.md",
            },
        ],
        "subagents": [
            {
                "name": "researcher-agent",
                "description": (
                    "Gathers and synthesises information via web search. "
                    "Give one focused research topic at a time."
                ),
                "model": "anthropic:claude-haiku-4-5-20251001",
                "system_prompt": """\
You are a research assistant. Search the web and return structured findings
with citations. Use `web_search` and `fetch_url`.

Process:
1. 1-2 broad searches first.
2. Up to 3 follow-up searches to fill gaps.
3. Return findings with inline [1][2] citations and a Sources section.
""",
            },
            {
                "name": "data-processor-agent",
                "description": (
                    "Handles data analysis, machine learning, and document processing using "
                    "GPU-accelerated NVIDIA tools. Delegate CSV analysis, dataset profiling, "
                    "anomaly detection, ML model training, chart creation, or bulk document "
                    "extraction to this agent. Give it a clear task description."
                ),
                "model": "anthropic:claude-sonnet-4-6",
                "system_prompt": """\
You are a GPU-accelerated data processing agent with access to NVIDIA cuDF,
cuML, and related libraries. You write and execute Python code for:
- Data analysis and profiling with cuDF (GPU-accelerated pandas)
- Machine learning with cuML (GPU-accelerated scikit-learn)
- Data visualisation
- Document processing

Always check your skill files for code patterns before writing new code.
Write clean, well-commented Python. Report results clearly.
""",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _subagent_md(subagent: dict) -> str:
    """Render a subagent AGENTS.md with YAML frontmatter."""
    model_line = f'model: "{subagent["model"]}"' if subagent.get("model") else ""
    frontmatter_lines = [
        "---",
        f'name: "{subagent["name"]}"',
        f'description: >',
        *[f"    {line}" for line in subagent["description"].splitlines()],
    ]
    if model_line:
        frontmatter_lines.append(model_line)
    frontmatter_lines.append("---")
    return "\n".join(frontmatter_lines) + "\n\n" + subagent["system_prompt"]


def install_agent(agent: dict, *, dry_run: bool = False, force: bool = False) -> None:
    name = agent["name"]
    agent_dir = DEEPAGENTS_HOME / name
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Installing: {name}")
    print(f"  -> {agent_dir}")

    if not dry_run:
        agent_dir.mkdir(parents=True, exist_ok=True)

    # ── AGENTS.md ──────────────────────────────────────────────────────────
    agents_md_path = agent_dir / "AGENTS.md"
    source = agent.get("agents_md_source")
    content = agent.get("agents_md_content")

    if agents_md_path.exists() and not force:
        print(f"  [skip] AGENTS.md already exists (use --force to overwrite)")
    elif source and Path(source).exists():
        print(f"  [copy] AGENTS.md <- {Path(source).relative_to(REPO_ROOT)}")
        if not dry_run:
            _copy_file(Path(source), agents_md_path)
    elif content:
        print(f"  [write] AGENTS.md (generated)")
        if not dry_run:
            _write_file(agents_md_path, content)
    else:
        print(f"  [warn] No AGENTS.md source found for {name!r}")

    # ── Skills ─────────────────────────────────────────────────────────────
    for skill in agent.get("skills", []):
        skill_src = Path(skill["source"])
        skill_dst = agent_dir / "skills" / skill["name"] / "SKILL.md"
        if skill_dst.exists() and not force:
            print(f"  [skip] skills/{skill['name']}/SKILL.md already exists")
        elif skill_src.exists():
            print(f"  [copy] skills/{skill['name']}/SKILL.md <- {skill_src.relative_to(REPO_ROOT)}")
            if not dry_run:
                _copy_file(skill_src, skill_dst)
        else:
            print(f"  [warn] Skill source not found: {skill_src}")

    # ── Subagents ──────────────────────────────────────────────────────────
    for subagent in agent.get("subagents", []):
        subagent_dst = agent_dir / "agents" / subagent["name"] / "AGENTS.md"
        if subagent_dst.exists() and not force:
            print(f"  [skip] agents/{subagent['name']}/AGENTS.md already exists")
        else:
            print(f"  [write] agents/{subagent['name']}/AGENTS.md")
            if not dry_run:
                _write_file(subagent_dst, _subagent_md(subagent))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install example agents into ~/.deepagents/"
    )
    parser.add_argument(
        "agents",
        nargs="*",
        help="Agent names to install. Omit to install all.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available agents without installing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be installed without writing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    args = parser.parse_args()

    available = {a["name"]: a for a in AGENTS}

    if args.list:
        print("Available example agents:")
        for name, agent in available.items():
            n_skills = len(agent.get("skills", []))
            n_subagents = len(agent.get("subagents", []))
            parts = []
            if n_skills:
                parts.append(f"{n_skills} skill{'s' if n_skills != 1 else ''}")
            if n_subagents:
                parts.append(f"{n_subagents} subagent{'s' if n_subagents != 1 else ''}")
            detail = f"  ({', '.join(parts)})" if parts else ""
            print(f"  deepagents -a {name}{detail}")
        return

    selected = args.agents if args.agents else list(available.keys())

    unknown = [n for n in selected if n not in available]
    if unknown:
        print(f"Unknown agent(s): {', '.join(unknown)}")
        print(f"Available: {', '.join(available)}")
        sys.exit(1)

    print(f"Installing {len(selected)} agent(s) into {DEEPAGENTS_HOME}/")
    for name in selected:
        install_agent(available[name], dry_run=args.dry_run, force=args.force)

    if not args.dry_run:
        print(f"\nDone! Run 'deepagents list' to see installed agents.")
        print("Use them with:  deepagents -a <name>")
    else:
        print("\n[DRY RUN] No files were written.")


if __name__ == "__main__":
    main()
