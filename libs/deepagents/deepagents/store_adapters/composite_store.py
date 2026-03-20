"""Composite store that fans out reads/writes across a primary and secondary store.

Read strategy: primary first, fall back to secondary on miss.
Write strategy: write-through to both stores concurrently.
Search strategy: merge results from both stores, deduplicating by key.
  Primary (Mem0) provides semantic/natural-language search.
  Secondary (AstraDB) provides vector/hybrid search.

Both stores must expose the `StoreItem`-compatible interface used by
`AstraStore` and `Mem0Store` in this package.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CompositeStore:
    """Read-primary-fallback + write-through composite over two store adapters.

    Args:
        primary: Primary store (e.g. Mem0Store). Reads hit this first.
        secondary: Optional secondary store (e.g. AstraStore). Used as fallback
            on reads and as a write-through target alongside primary.
    """

    def __init__(self, primary: Any, secondary: Any | None = None) -> None:
        self.primary = primary
        self.secondary = secondary

    # ------------------------------------------------------------------
    # Sync interface
    # ------------------------------------------------------------------

    def get(self, namespace: tuple[str, ...], key: str) -> Any | None:
        """Return item from primary, falling back to secondary on miss."""
        if self.primary is not None:
            try:
                result = self.primary.get(namespace, key)
                if result is not None:
                    return result
            except Exception:
                logger.warning("CompositeStore primary.get failed", exc_info=True)
        if self.secondary is not None:
            try:
                return self.secondary.get(namespace, key)
            except Exception:
                logger.warning("CompositeStore secondary.get failed", exc_info=True)
        return None

    def put(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        """Write-through: write to primary then secondary, logging each failure."""
        if self.primary is not None:
            try:
                self.primary.put(namespace, key, value)
            except Exception:
                logger.warning("CompositeStore primary.put failed", exc_info=True)
        if self.secondary is not None:
            try:
                self.secondary.put(namespace, key, value)
            except Exception:
                logger.warning("CompositeStore secondary.put failed", exc_info=True)

    def search(self, namespace: tuple[str, ...], *args: Any, **kwargs: Any) -> list:
        """Merge search results from both stores, deduplicating by key.

        Primary results take precedence; secondary fills in any unseen keys.
        """
        results: list = []
        seen: set[str] = set()

        if self.primary is not None:
            try:
                for item in self.primary.search(namespace, *args, **kwargs) or []:
                    key = getattr(item, "key", None)
                    if key not in seen:
                        seen.add(key)
                        results.append(item)
            except Exception:
                logger.warning("CompositeStore primary.search failed", exc_info=True)

        if self.secondary is not None:
            try:
                for item in self.secondary.search(namespace, *args, **kwargs) or []:
                    key = getattr(item, "key", None)
                    if key not in seen:
                        seen.add(key)
                        results.append(item)
            except Exception:
                logger.warning("CompositeStore secondary.search failed", exc_info=True)

        return results

    # ------------------------------------------------------------------
    # Async interface
    # ------------------------------------------------------------------

    async def aget(self, namespace: tuple[str, ...], key: str) -> Any | None:
        """Async read: primary first, fallback to secondary."""
        if self.primary is not None:
            try:
                if hasattr(self.primary, "aget"):
                    result = await self.primary.aget(namespace, key)
                else:
                    result = await asyncio.to_thread(self.primary.get, namespace, key)
                if result is not None:
                    return result
            except Exception:
                logger.warning("CompositeStore primary.aget failed", exc_info=True)
        if self.secondary is not None:
            try:
                if hasattr(self.secondary, "aget"):
                    return await self.secondary.aget(namespace, key)
                return await asyncio.to_thread(self.secondary.get, namespace, key)
            except Exception:
                logger.warning("CompositeStore secondary.aget failed", exc_info=True)
        return None

    async def aput(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        """Async write-through: write to both stores concurrently."""
        tasks: list[Any] = []

        if self.primary is not None:
            if hasattr(self.primary, "aput"):
                tasks.append(self.primary.aput(namespace, key, value))
            else:
                tasks.append(asyncio.to_thread(self.primary.put, namespace, key, value))

        if self.secondary is not None:
            if hasattr(self.secondary, "aput"):
                tasks.append(self.secondary.aput(namespace, key, value))
            else:
                tasks.append(asyncio.to_thread(self.secondary.put, namespace, key, value))

        if not tasks:
            return

        store_names = []
        if self.primary is not None:
            store_names.append("primary")
        if self.secondary is not None:
            store_names.append("secondary")

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(store_names, results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "CompositeStore %s.aput failed: %s", name, result, exc_info=False
                )

    async def asearch(
        self, namespace: tuple[str, ...], *args: Any, **kwargs: Any
    ) -> list:
        """Async search: delegates to sync search via thread."""
        return await asyncio.to_thread(self.search, namespace, *args, **kwargs)