"""LLM transport + formatting layer shared by every suppl.ai agent.

Public API (frozen — downstream worktrees depend on this surface):

- :class:`LLMClient` — Gemini wrapper with structured output, tool calling,
  cached contexts, and an SQLite offline cache.
- :class:`LLMValidationError` — raised when Gemini output fails schema
  validation after the single structured-retry, and when offline cache misses.
- :class:`Tool` / :class:`ToolInvocation` — function-calling loop contracts.
"""

from __future__ import annotations

from backend.llm.client import LLMClient, LLMValidationError, Tool, ToolInvocation

__all__ = [
    "LLMClient",
    "LLMValidationError",
    "Tool",
    "ToolInvocation",
]
