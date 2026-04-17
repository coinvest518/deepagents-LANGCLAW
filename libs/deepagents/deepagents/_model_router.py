"""Smart multi-model router with free-tier token budget tracking.

Automatically picks the best available model based on:
- Which API keys are present in the environment
- How much of each provider's free-tier quota has been used in the last 60s
- Task type: general agentic, coding, swarm, reasoning, fast, research, composio
- Tool-calling reliability (models ranked by agentic quality, not just size)
- Provider diversity (subagents use different providers than main)

Usage::

    from deepagents._model_router import router
    model_spec = router.pick("main")
    sub_specs  = router.pick_subagents(3)
    task_spec  = router.pick_for_task("coding")
    router.record("nvidia", tokens=800)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict

logger = logging.getLogger("deepagents.model_router")

# ---------------------------------------------------------------------------
# Free-tier token-per-minute limits
# None = no known hard limit (treat as unlimited for budgeting)
# ---------------------------------------------------------------------------
FREE_TIER_TPM: dict[str, int | None] = {
    "openrouter": None,       # Free tier varies by model; best overall coverage
    "nvidia": None,           # NIM API — free credits, ~40 RPM, no hard TPM
    "moonshot": 100_000,      # Kimi K2.5 — 256K ctx, 300-step tool use
    "cloudflare": None,       # Workers AI — 10K+ neurons/day, edge-fast
    "cerebras": 600_000,      # Cerebras — fastest inference (Llama 4 Scout)
    "nebius": 200_000,        # Nebius AI Studio (near-free open models)
    "mistralai": 50_000,      # Mistral — 50k TPM, last resort (rate-limited)
    "huggingface": 30_000,    # HF inference API
    "anthropic": 100_000,
    "openai": 40_000,
    "google_genai": None,
}

# ---------------------------------------------------------------------------
# Env var that proves a provider key is present
# ---------------------------------------------------------------------------
PROVIDER_KEY_ENV: dict[str, str] = {
    "nvidia": "NVIDIA_API_KEY",
    "nebius": "NEBIUS_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "mistralai": "MISTRAL_API_KEY",
    "huggingface": "HUGGINGFACEHUB_API_TOKEN",
    "moonshot": "MOONSHOT_API_KEY",
    "cloudflare": "CLOUDFLARE_AI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
}

_SAFE_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# Model tiers — ranked by TOOL-CALLING RELIABILITY, not raw benchmarks.
# ---------------------------------------------------------------------------

# Main agent candidates — OpenRouter first (no EOL risk), NVIDIA last
MAIN_MODELS: list[tuple[str, str, str]] = [
    ("openrouter", "openrouter:deepseek/deepseek-chat-v3-0324:free", "DeepSeek V3.2 (OR free)"),
    ("openrouter", "openrouter:meta-llama/llama-4-maverick:free", "Llama 4 Maverick (OR free)"),
    ("openrouter", "openrouter:qwen/qwen3.5-72b-instruct:free", "Qwen3.5-72B (OR free)"),
    ("openrouter", "openrouter:qwen/qwen3-coder-480b-a35b-instruct:free", "Qwen3-Coder-480B (OR free)"),
    ("moonshot", "moonshot:kimi-k2.5", "Kimi K2.5 (Moonshot)"),
    ("cloudflare", "cloudflare:@cf/meta/llama-4-scout-instruct", "Llama 4 Scout (CF)"),
    ("cloudflare", "cloudflare:@cf/meta/llama-3.3-70b-instruct-fp8-fast", "Llama 3.3 70B (CF)"),
    ("cerebras", "cerebras:llama-4-scout-17b-16e-instruct", "Llama 4 Scout (Cerebras)"),
    ("nebius", "nebius:Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B (Nebius)"),
    ("nvidia", "nvidia:qwen/qwen3.5-397b-a17b", "Qwen3.5-397B (NVIDIA)"),
    ("nvidia", "nvidia:deepseek-ai/deepseek-v3.2", "DeepSeek V3.2 (NVIDIA)"),
    ("nvidia", "nvidia:nvidia/llama-3.3-nemotron-super-49b-v1", "Nemotron Super 49B (NVIDIA)"),
    ("mistralai", "mistralai:mistral-large-latest", "Mistral Large"),
    ("huggingface", "huggingface:Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B (HF)"),
]

# Subagent candidates — provider-diverse pool for parallel delegation
SUBAGENT_MODELS: list[tuple[str, str, str]] = [
    ("moonshot", "moonshot:kimi-k2.5", "Kimi K2.5 (Moonshot)"),
    ("cloudflare", "cloudflare:@cf/meta/llama-4-scout-instruct", "Llama 4 Scout (CF)"),
    ("cerebras", "cerebras:llama-4-scout-17b-16e-instruct", "Llama 4 Scout (Cerebras)"),
    ("openrouter", "openrouter:deepseek/deepseek-chat-v3-0324:free", "DeepSeek V3.2 (OR free)"),
    ("openrouter", "openrouter:meta-llama/llama-4-maverick:free", "Llama 4 Maverick (OR free)"),
    ("openrouter", "openrouter:qwen/qwen3.5-72b-instruct:free", "Qwen3.5-72B (OR free)"),
    ("cloudflare", "cloudflare:@cf/meta/llama-3.3-70b-instruct-fp8-fast", "Llama 3.3 70B (CF)"),
    ("nebius", "nebius:Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B (Nebius)"),
    ("nvidia", "nvidia:qwen/qwen3.5-397b-a17b", "Qwen3.5-397B (NVIDIA)"),
    ("nvidia", "nvidia:meta/llama-4-scout-17b-16e-instruct", "Llama 4 Scout (NVIDIA)"),
    ("mistralai", "mistralai:mistral-large-latest", "Mistral Large"),
    ("huggingface", "huggingface:Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B (HF)"),
]

# ---------------------------------------------------------------------------
# Task-based model routing — picks the best model for each task TYPE
# ---------------------------------------------------------------------------
TASK_MODELS: dict[str, list[tuple[str, str, str]]] = {
    "general_agentic": [
        ("openrouter", "openrouter:deepseek/deepseek-chat-v3-0324:free", "DeepSeek V3.2 (OR free)"),
        ("openrouter", "openrouter:meta-llama/llama-4-maverick:free", "Llama 4 Maverick (OR free)"),
        ("openrouter", "openrouter:qwen/qwen3.5-72b-instruct:free", "Qwen3.5-72B (OR free)"),
        ("moonshot", "moonshot:kimi-k2.5", "Kimi K2.5"),
        ("nvidia", "nvidia:qwen/qwen3.5-397b-a17b", "Qwen3.5-397B (NVIDIA)"),
    ],
    "coding": [
        ("openrouter", "openrouter:qwen/qwen3-coder-480b-a35b-instruct:free", "Qwen3-Coder-480B (OR free)"),
        ("nvidia", "nvidia:qwen/qwen3-coder-480b-a35b-instruct", "Qwen3-Coder-480B (NVIDIA)"),
        ("openrouter", "openrouter:deepseek/deepseek-chat-v3-0324:free", "DeepSeek V3.2 (OR free)"),
        ("nvidia", "nvidia:deepseek-ai/deepseek-v3.2", "DeepSeek V3.2 (NVIDIA)"),
    ],
    "long_chain_or_swarm": [
        ("moonshot", "moonshot:kimi-k2.5", "Kimi K2.5 (256K, 300-step swarm)"),
        ("cloudflare", "cloudflare:@cf/meta/llama-4-scout-instruct", "Llama 4 Scout (CF edge)"),
        ("openrouter", "openrouter:meta-llama/llama-4-maverick:free", "Llama 4 Maverick (1M ctx)"),
    ],
    "reasoning": [
        ("nvidia", "nvidia:qwen/qwen3.5-397b-a17b", "Qwen3.5-397B (NVIDIA)"),
        ("openrouter", "openrouter:qwen/qwen3.5-72b-instruct:free", "Qwen3.5-72B (OR free)"),
        ("moonshot", "moonshot:kimi-k2.5", "Kimi K2.5"),
    ],
    "fast_subagent": [
        ("cerebras", "cerebras:llama-4-scout-17b-16e-instruct", "Llama 4 Scout (Cerebras)"),
        ("cloudflare", "cloudflare:@cf/meta/llama-4-scout-instruct", "Llama 4 Scout (CF)"),
        ("cloudflare", "cloudflare:@cf/meta/llama-3.3-70b-instruct-fp8-fast", "Llama 3.3 70B (CF)"),
        ("openrouter", "openrouter:deepseek/deepseek-chat-v3-0324:free", "DeepSeek V3.2 (OR free)"),
    ],
    "research": [
        ("openrouter", "openrouter:meta-llama/llama-4-maverick:free", "Llama 4 Maverick (1M ctx)"),
        ("moonshot", "moonshot:kimi-k2.5", "Kimi K2.5 (256K)"),
        ("openrouter", "openrouter:qwen/qwen3.5-72b-instruct:free", "Qwen3.5-72B (OR free)"),
        ("nebius", "nebius:Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B (Nebius)"),
    ],
    "composio_worker": [
        ("cerebras", "cerebras:llama-4-scout-17b-16e-instruct", "Llama 4 Scout (Cerebras)"),
        ("cloudflare", "cloudflare:@cf/meta/llama-4-scout-instruct", "Llama 4 Scout (CF)"),
        ("openrouter", "openrouter:deepseek/deepseek-chat-v3-0324:free", "DeepSeek V3.2 (OR free)"),
    ],
}

# ---------------------------------------------------------------------------
# Full provider reference table — can be injected into system prompts
# ---------------------------------------------------------------------------
PROVIDER_REFERENCE = """## Available LLM Providers & Free-Tier Limits (April 2026)

| Provider | Free Tier | Rate Limit | Best Agentic Models | Context | Best For |
|---|---|---|---|---|---|
| **OpenRouter** | 50-1K req/day (varies per model) | ~20 req/min per model | DeepSeek V3.2, Llama 4 Maverick, Qwen3.5-72B, Qwen3-Coder-480B | 128K-1M+ | Primary routing — cleanest free tool-calling ecosystem |
| **Moonshot AI** | 100K TPM | Moderate | Kimi K2.5 (native 100-sub-agent swarm, 300 tool steps) | 256K-1M | Long-running multi-step tasks, agent swarms |
| **Cloudflare Workers AI** | 10K+ neurons/day | Generous | Llama 4 Scout, Llama 3.3-70B, Qwen3 variants | 256K | Edge-fast sub-agents, parallel delegation |
| **Cerebras** | 600K TPM | ~40 RPM | Llama 4 Scout 17B | 128K | Fastest inference — ideal for fast subagents |
| **NVIDIA NIM** | Free credits (~40 RPM) | ~40 RPM | Qwen3.5-397B, DeepSeek V3.2, Nemotron Super 49B, Qwen3-Coder-480B | 128K-262K | Reasoning-heavy tasks, coding (limited RPM) |
| **Nebius AI Studio** | Near-free low volume | Moderate | Qwen/Llama/DeepSeek families | Varies | Cost-effective overflow for agent loops |
| **Mistral** | 50K TPM | 50K TPM hard cap | Mistral Large | 128K | Use sparingly — rate-limits fast |
| **Hugging Face** | Generous free tier | Moderate | Qwen2.5-72B, Gemma 3 | Varies | Last-resort fallback |

### Task Delegation Guide
- **Coding tasks** → Qwen3-Coder-480B (OpenRouter/NVIDIA)
- **Fast parallel subagents** → Cerebras Llama 4 Scout or Cloudflare
- **Long multi-step workflows** → Moonshot Kimi K2.5 (300 tool steps, 256K ctx)
- **Deep research** → Llama 4 Maverick via OpenRouter (1M ctx)
- **Bulk Composio API calls** → Cerebras/Cloudflare (fast, high throughput)
- **Reasoning/math/planning** → NVIDIA Qwen3.5-397B or Qwen3.5-72B"""


# ---------------------------------------------------------------------------
# Token budget tracker
# ---------------------------------------------------------------------------

class _TokenBudgetTracker:
    """Thread-safe sliding-window (60s) token usage tracker per provider."""

    WINDOW = 60

    def __init__(self) -> None:
        self._usage: dict[str, list[tuple[float, int]]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, provider: str, tokens: int) -> None:
        with self._lock:
            self._usage[provider].append((time.time(), tokens))

    def _used(self, provider: str) -> int:
        cutoff = time.time() - self.WINDOW
        entries = [(t, n) for t, n in self._usage[provider] if t > cutoff]
        self._usage[provider] = entries
        return sum(n for _, n in entries)

    def usage_pct(self, provider: str) -> float:
        limit = FREE_TIER_TPM.get(provider)
        if not limit:
            return 0.0
        with self._lock:
            return min(100.0, self._used(provider) / limit * 100)

    def has_headroom(self, provider: str) -> bool:
        limit = FREE_TIER_TPM.get(provider)
        if limit is None:
            return True
        with self._lock:
            return self._used(provider) < limit * _SAFE_THRESHOLD


# ---------------------------------------------------------------------------
# Main router class
# ---------------------------------------------------------------------------

class ModelRouter:
    """Stateful router that selects the best model for main agent and subagents.

    Picks models based on:
    - Tool-calling quality (Qwen3 > DeepSeek V3 > Mistral > Nemotron)
    - Rate-limit headroom (avoids providers near their TPM cap)
    - Provider diversity (subagents use different providers than main)
    """

    def __init__(self) -> None:
        self._tracker = _TokenBudgetTracker()
        self._last_main: str = ""
        self._last_main_provider: str = ""

    def _available(self, model_list: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """All models from list whose API key is present."""
        return [
            (prov, spec, name)
            for prov, spec, name in model_list
            if os.environ.get(PROVIDER_KEY_ENV.get(prov, ""))
        ]

    def pick(self, role: str = "main") -> str:
        """Pick the best model spec for a role.

        Args:
            role: Either 'main' or 'subagent'.

        Returns:
            Model spec string, or empty string if no keys available.
        """
        if role == "subagent":
            candidates = self._available(SUBAGENT_MODELS)
        else:
            candidates = self._available(MAIN_MODELS)

        if not candidates:
            return ""

        with_room = [(p, s, n) for p, s, n in candidates if self._tracker.has_headroom(p)]
        if not with_room:
            chosen = min(candidates, key=lambda x: self._tracker.usage_pct(x[0]))
            logger.warning(
                "All providers near free-tier limit. Using %s (%.0f%% used)",
                chosen[2], self._tracker.usage_pct(chosen[0]),
            )
            spec = chosen[1]
        elif role == "subagent":
            fresh = sorted(with_room, key=lambda x: self._tracker.usage_pct(x[0]))
            different = [m for m in fresh if m[0] != self._last_main_provider] or fresh
            spec = different[0][1]
        else:
            spec = with_room[0][1]

        if role == "main":
            self._last_main = spec
            self._last_main_provider = spec.split(":")[0]
            prov = next((p for p, s, _ in candidates if s == spec), "?")
            logger.info("ModelRouter: main=%s (%.0f%% used)", spec, self._tracker.usage_pct(prov))

        return spec

    def pick_subagents(self, n: int = 3) -> list[str]:
        """Return n model specs for subagents, maximising provider diversity.

        Args:
            n: Number of subagent specs to return.

        Returns:
            List of model spec strings.
        """
        candidates = self._available(SUBAGENT_MODELS)
        if not candidates:
            return []

        result: list[str] = []
        seen_providers: set[str] = {self._last_main_provider}
        sorted_cands = sorted(candidates, key=lambda x: self._tracker.usage_pct(x[0]))

        for prov, spec, name in sorted_cands:
            if prov not in seen_providers:
                result.append(spec)
                seen_providers.add(prov)
                logger.info(
                    "ModelRouter: subagent[%d]=%s (%.0f%% used)",
                    len(result) - 1, spec, self._tracker.usage_pct(prov),
                )
            if len(result) >= n:
                break

        while len(result) < n:
            idx = len(result) % len(candidates)
            result.append(candidates[idx][1])

        return result

    def pick_for_task(self, task_type: str) -> str:
        """Pick the best model for a specific task type.

        Uses TASK_MODELS registry. Falls back to general_agentic if task_type
        is unknown.

        Args:
            task_type: One of 'general_agentic', 'coding', 'long_chain_or_swarm',
                       'reasoning', 'fast_subagent', 'research', 'composio_worker'.

        Returns:
            Model spec string (e.g. 'openrouter:qwen/qwen3-coder-480b:free').
        """
        candidates_raw = TASK_MODELS.get(task_type, TASK_MODELS["general_agentic"])
        candidates = self._available(candidates_raw)

        if not candidates:
            candidates = self._available(MAIN_MODELS)

        if not candidates:
            return ""

        with_room = [(p, s, n) for p, s, n in candidates if self._tracker.has_headroom(p)]
        if with_room:
            different = [m for m in with_room if m[0] != self._last_main_provider]
            pick = different[0] if different else with_room[0]
        else:
            pick = min(candidates, key=lambda x: self._tracker.usage_pct(x[0]))

        logger.info(
            "ModelRouter: task=%s → %s (%.0f%% used)",
            task_type, pick[1], self._tracker.usage_pct(pick[0]),
        )
        return pick[1]

    def record(self, provider_or_spec: str, tokens: int) -> None:
        """Record token usage for rate-limit tracking.

        Args:
            provider_or_spec: Provider name or full spec string.
            tokens: Number of tokens used.
        """
        provider = provider_or_spec.split(":")[0]
        self._tracker.record(provider, tokens)

    def status(self) -> dict[str, dict]:
        """Return current status of all available providers.

        Returns:
            Dict mapping display name to status info.
        """
        result: dict[str, dict] = {}
        for prov, spec, name in self._available(MAIN_MODELS):
            result[name] = {
                "spec": spec,
                "usage_pct": round(self._tracker.usage_pct(prov), 1),
                "limit_tpm": FREE_TIER_TPM.get(prov),
                "has_headroom": self._tracker.has_headroom(prov),
            }
        return result


# Singleton — importable from anywhere in the SDK
router = ModelRouter()
