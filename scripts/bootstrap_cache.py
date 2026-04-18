"""VM bootstrap hook — prime offline caches before the agent starts (Task 12.4).

Invoked via systemd ``ExecStartPre=`` on every supplai-*.service unit. When
``DEMO_OFFLINE_CACHE=true``, copies the bundled ``*.sqlite.seed`` artefacts
shipped under ``backend/llm/`` into the active cache paths that the agent
configs point to. No-op when the flag is off or a cache already exists.

Paths default to the layout matched by :class:`ScoutSettings` /
:class:`AnalystSettings` / :class:`StrategistSettings` (``/var/lib/supplai/``)
and can be overridden via env for development:

- ``SUPPLAI_PROMPT_CACHE_TARGET`` — active prompt-cache path.
- ``SUPPLAI_TAVILY_CACHE_TARGET`` — active Tavily-cache path.
- ``SUPPLAI_SEED_DIR`` — seed directory; defaults to the repo's
  ``backend/llm/`` directory next to this script.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from backend.llm.cache_loader import (
    prime_cache_if_offline,
    prime_tavily_cache_if_offline,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SEED_DIR = _REPO_ROOT / "backend" / "llm"
_DEFAULT_PROMPT_TARGET = Path("/var/lib/supplai/prompt_cache.sqlite")
_DEFAULT_TAVILY_TARGET = Path("/var/lib/supplai/scout-tavily-cache.sqlite")


def main() -> int:
    seed_dir = Path(os.environ.get("SUPPLAI_SEED_DIR", _DEFAULT_SEED_DIR))
    prompt_target = Path(os.environ.get("SUPPLAI_PROMPT_CACHE_TARGET", _DEFAULT_PROMPT_TARGET))
    tavily_target = Path(os.environ.get("SUPPLAI_TAVILY_CACHE_TARGET", _DEFAULT_TAVILY_TARGET))

    prime_cache_if_offline(seed_dir, prompt_target)
    prime_tavily_cache_if_offline(seed_dir, tavily_target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
