"""
model_router.py — Smart multi-model router with free-tier token budget tracking.

Automatically picks the best available model based on:
- Which API keys are present in the environment
- How much of each provider's free-tier quota has been used in the last 60s
- Task role: main agent vs subagent (different providers = no rate-limit competition)

No env vars needed. Reads keys present, manages budgets internally.

Usage:
    from model_router import router
    model_spec = router.pick("main")      # for main agent
    sub_specs  = router.pick_subagents(3) # for subagents — different providers
    router.record("mistralai", tokens=800) # call after each response
    print(router.status())
"""

import os
import time
import logging
import threading
from collections import defaultdict

logger = logging.getLogger("deepagents.model_router")

# ---------------------------------------------------------------------------
# Free-tier token-per-minute limits
# None = no known hard limit (treat as unlimited for budgeting)
# ---------------------------------------------------------------------------
FREE_TIER_TPM: dict[str, int | None] = {
    "mistralai":    50_000,   # mistral-large free tier (hits fast on complex tasks)
    "nvidia":      400_000,   # nvapi free tier — much larger quota
    "openrouter":     None,   # no hard token cap; ~20 req/min per model
    "huggingface":  30_000,   # HF inference API (Novita router)
    "cerebras":    600_000,   # Cerebras free tier (very fast inference)
    "anthropic":   100_000,   # claude free tier
    "openai":       40_000,   # gpt-4o tier-1
    "google_genai":  None,    # gemini flash free tier is very generous
}

# ---------------------------------------------------------------------------
# Ordered model list — priority order for tool-heavy tasks.
# The router tries these in sequence and picks the first with budget headroom.
# ---------------------------------------------------------------------------
_TOOL_MODELS: list[tuple[str, str, str]] = [
    # (provider_key, model_spec,                                  display_name)
    # Ranked by reliability: direct-API providers first (own rate limits),
    # then free-tier proxies (shared limits, can 429 easily).
    #
    # --- Direct API = own rate limit, most reliable ---
    ("mistralai",   "mistralai:mistral-large-latest",            "Mistral Large"),              # good native tools, 50k TPM
    ("nvidia",      "nvidia:meta/llama-3.3-70b-instruct",        "NVIDIA Llama-3.3-70B"),      # 400k TPM free
    #
    # --- Free-tier proxies (shared rate limits) ---
    ("openrouter",  "openrouter:mistralai/mistral-small-3.1-24b-instruct:free","OR Mistral Small 3.1"),    # can 429
    ("cerebras",    "cerebras:llama-3.3-70b",                    "Cerebras Llama-3.3-70B"),    # 600k TPM, very fast
    #
    # --- Fallback ---
    ("huggingface", "huggingface:Qwen/Qwen2.5-72B-Instruct",     "Qwen2.5-72B"),
    #
    # --- Direct API keys (if added later) ---
    ("anthropic",   "anthropic:claude-sonnet-4-6",               "Claude Sonnet 4.6"),
    ("openai",      "openai:gpt-4o",                             "GPT-4o"),
    ("google_genai","google_genai:gemini-2.0-flash",             "Gemini 2.0 Flash"),
]

# Env var that proves a provider key is present
_PROVIDER_KEY_ENV: dict[str, str] = {
    "mistralai":    "MISTRAL_API_KEY",
    "nvidia":       "NVIDIA_API_KEY",
    "openrouter":   "OPENROUTER_API_KEY",
    "huggingface":  "HUGGINGFACEHUB_API_TOKEN",
    "cerebras":     "CEREBRAS_API_KEY",
    "anthropic":    "ANTHROPIC_API_KEY",
    "openai":       "OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
}

# Switch to next provider when this fraction of the minute quota is used.
_SAFE_THRESHOLD = 0.80   # 80% used → look for fresher provider


class _TokenBudgetTracker:
    """Thread-safe sliding-window (60s) token usage tracker per provider."""

    WINDOW = 60  # seconds

    def __init__(self) -> None:
        self._usage: dict[str, list[tuple[float, int]]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, provider: str, tokens: int) -> None:
        """Call this after each LLM response with the total token count."""
        with self._lock:
            self._usage[provider].append((time.time(), tokens))

    def _used(self, provider: str) -> int:
        """Tokens used in the last 60s. Must be called under lock."""
        cutoff = time.time() - self.WINDOW
        entries = [(t, n) for t, n in self._usage[provider] if t > cutoff]
        self._usage[provider] = entries
        return sum(n for _, n in entries)

    def usage_pct(self, provider: str) -> float:
        """0–100 % of the free-tier quota used in the last 60s."""
        limit = FREE_TIER_TPM.get(provider)
        if not limit:
            return 0.0
        with self._lock:
            return min(100.0, self._used(provider) / limit * 100)

    def has_headroom(self, provider: str) -> bool:
        """True when this provider still has capacity for the next request."""
        limit = FREE_TIER_TPM.get(provider)
        if limit is None:
            return True
        with self._lock:
            return self._used(provider) < limit * _SAFE_THRESHOLD


class ModelRouter:
    """
    Stateful router that selects the best model for main agent and subagents.

    Typical use:
        router = ModelRouter()

        # At server startup — pick main model
        main_model = router.pick("main")

        # Before spawning subagents — pick n different providers
        sub_models = router.pick_subagents(n=3)

        # After each LLM call — record token usage
        router.record(provider, total_tokens)

        # Health check / dashboard
        print(router.status())
    """

    def __init__(self) -> None:
        self._tracker = _TokenBudgetTracker()
        self._last_main: str = ""     # track which provider main agent used

    def _available(self) -> list[tuple[str, str, str]]:
        """All models whose API key is present, in priority order."""
        return [
            (prov, spec, name)
            for prov, spec, name in _TOOL_MODELS
            if os.environ.get(_PROVIDER_KEY_ENV.get(prov, ""))
        ]

    def pick(self, role: str = "main") -> str:
        """
        Pick the best model spec for *role*.

        role="main"     → highest-priority provider with headroom
        role="subagent" → prefer providers different from the main agent,
                          sorted by least-used first
        """
        candidates = self._available()
        if not candidates:
            return ""

        # Separate into those with headroom vs those near limit
        with_room = [(p, s, n) for p, s, n in candidates if self._tracker.has_headroom(p)]
        if not with_room:
            # All providers near limit — pick the freshest one anyway
            chosen = min(candidates, key=lambda x: self._tracker.usage_pct(x[0]))
            logger.warning(
                "All providers near free-tier limit. Using %s (%.0f%% used)",
                chosen[2], self._tracker.usage_pct(chosen[0])
            )
            spec = chosen[1]
        elif role == "subagent":
            # For subagents: prefer a different provider than the main agent
            fresh = sorted(with_room, key=lambda x: self._tracker.usage_pct(x[0]))
            # Deprioritise same provider as main agent
            different = [m for m in fresh if m[1] != self._last_main] or fresh
            spec = different[0][1]
        else:
            spec = with_room[0][1]

        if role == "main":
            self._last_main = spec
            prov = next((p for p, s, _ in candidates if s == spec), "?")
            logger.info("ModelRouter: main=%s (%.0f%% used)", spec, self._tracker.usage_pct(prov))

        return spec

    def pick_subagents(self, n: int = 3) -> list[str]:
        """
        Return n model specs for subagents, maximising provider diversity.

        Each subagent gets a different provider where possible, so they
        draw from different token-per-minute buckets simultaneously.
        """
        candidates = self._available()
        if not candidates:
            return []

        result: list[str] = []
        seen_providers: set[str] = {self._last_main.split(":")[0] if ":" in self._last_main else ""}

        # Sort by usage % so freshest providers are assigned first
        sorted_cands = sorted(
            candidates,
            key=lambda x: self._tracker.usage_pct(x[0])
        )

        for prov, spec, name in sorted_cands:
            if prov not in seen_providers:
                result.append(spec)
                seen_providers.add(prov)
                logger.info(
                    "ModelRouter: subagent[%d]=%s (%.0f%% used)",
                    len(result) - 1, spec, self._tracker.usage_pct(prov)
                )
            if len(result) >= n:
                break

        # Fill remaining slots with round-robin if we ran out of unique providers
        while len(result) < n:
            idx = len(result) % len(candidates)
            result.append(candidates[idx][1])

        return result

    def record(self, provider_or_spec: str, tokens: int) -> None:
        """
        Record token usage after a model call.

        Accepts either the provider key ("mistralai") or a full spec
        ("mistralai:mistral-large-latest") — both work.
        """
        provider = provider_or_spec.split(":")[0]
        self._tracker.record(provider, tokens)

    def status(self) -> dict[str, dict]:
        """Return current usage for all configured providers."""
        result: dict[str, dict] = {}
        for prov, spec, name in self._available():
            result[name] = {
                "spec":         spec,
                "usage_pct":    round(self._tracker.usage_pct(prov), 1),
                "limit_tpm":    FREE_TIER_TPM.get(prov),
                "has_headroom": self._tracker.has_headroom(prov),
            }
        return result


# Singleton — import and use everywhere
router = ModelRouter()