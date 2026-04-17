"""
model_router.py - Thin deployment re-export of the SDK model router.

The full implementation now lives in the SDK at
`libs/deepagents/deepagents/_model_router.py` so it is available everywhere
(graph.py, subagents, CLI, deploy scripts) without circular imports.

This file re-exports the public API for backward compatibility with existing
deploy scripts (telegram_bot.py, local_dashboard_server.py, etc.).

Usage:
    from model_router import router
    model_spec = router.pick("main")
    sub_specs  = router.pick_subagents(3)
    task_spec  = router.pick_for_task("coding")
    router.record("nvidia", tokens=800)
    print(router.status())
"""

# Re-export everything from the SDK module
from deepagents._model_router import (  # noqa: F401
    FREE_TIER_TPM,
    MAIN_MODELS,
    ModelRouter,
    PROVIDER_KEY_ENV,
    PROVIDER_REFERENCE,
    SUBAGENT_MODELS,
    TASK_MODELS,
    router,
)
