"""Prime the prompt + Tavily caches from bundled seeds at boot (Task 12.4).

Demo-day failsafe: if Gemini / Tavily are unreachable but
``DEMO_OFFLINE_CACHE=true`` is set, ``backend.llm.prompt_cache`` and the
``scout.sources.tavily`` cache serve hits from SQLite files. This helper
copies versioned ``*.sqlite.seed`` artefacts into the active cache paths on
first boot so the five scripted scenarios still resolve without a live API.

Idempotent — never overwrites an existing cache DB; never touches a target
when the env flag is off or the seed is missing. Both helpers share the
same truthy-set for the env flag and the same no-op semantics so the
systemd ExecStartPre hook can call both unconditionally.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import structlog

log = structlog.get_logger()

SEED_FILENAME = "prompt_cache.sqlite.seed"
TAVILY_SEED_FILENAME = "tavily_cache.sqlite.seed"
ENV_FLAG = "DEMO_OFFLINE_CACHE"
_TRUTHY = {"1", "true", "yes", "on"}


def _flag_enabled() -> bool:
    return os.environ.get(ENV_FLAG, "").strip().lower() in _TRUTHY


def _prime(seed: Path, target: Path, *, label: str) -> None:
    if not _flag_enabled():
        return

    if target.exists():
        log.info("cache_loader.skip_target_exists", label=label, target=str(target))
        return

    if not seed.is_file():
        log.warning("cache_loader.seed_missing", label=label, seed=str(seed))
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed, target)
    log.info("cache_loader.primed", label=label, seed=str(seed), target=str(target))


def prime_cache_if_offline(seed_dir: Path, target: Path) -> None:
    """Copy ``<seed_dir>/prompt_cache.sqlite.seed`` → ``<target>`` at boot."""
    _prime(Path(seed_dir) / SEED_FILENAME, Path(target), label="prompt_cache")


def prime_tavily_cache_if_offline(seed_dir: Path, target: Path) -> None:
    """Copy ``<seed_dir>/tavily_cache.sqlite.seed`` → ``<target>`` at boot."""
    _prime(Path(seed_dir) / TAVILY_SEED_FILENAME, Path(target), label="tavily_cache")
