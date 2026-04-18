"""Scout classifier — thin wrapper over :meth:`LLMClient.structured`.

The classification prompt lives in ``prompts/classify.md``; this module is
only responsible for loading that prompt, appending the serialized raw
signal, and handing the pair to the LLM with a URL-keyed cache entry so
that re-scans don't re-hit the API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from backend.llm.client import LLMClient
from backend.schemas import SignalClassification

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "classify.md"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text()


async def classify_raw_signal(raw: dict[str, Any], llm: LLMClient) -> SignalClassification:
    """Classify one raw source result into a :class:`SignalClassification`."""
    prompt = _load_prompt() + "\n\nRAW SIGNAL:\n" + json.dumps(raw, indent=2)
    cache_key = f"classify::{raw.get('url', json.dumps(raw, sort_keys=True))}"
    parsed = await llm.structured(prompt, SignalClassification, cache_key=cache_key)
    return cast(SignalClassification, parsed)
