"""Prime the prompt-cache SQLite from a bundled seed at boot (Task 12.4).

Demo-day failsafe: if Gemini is unreachable but ``DEMO_OFFLINE_CACHE=true`` is
set, ``backend.llm.prompt_cache`` serves hits from a SQLite file. This helper
copies a versioned ``*.sqlite.seed`` artefact into the active cache path on
first boot so the five scripted scenarios still resolve without a live API.

Idempotent — never overwrites an existing cache DB; never touches the target
when the env flag is off or the seed is missing.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import structlog

log = structlog.get_logger()

SEED_FILENAME = "prompt_cache.sqlite.seed"
ENV_FLAG = "DEMO_OFFLINE_CACHE"
_TRUTHY = {"1", "true", "yes", "on"}


def _flag_enabled() -> bool:
    return os.environ.get(ENV_FLAG, "").strip().lower() in _TRUTHY


def prime_cache_if_offline(seed_dir: Path, target: Path) -> None:
    """Copy ``<seed_dir>/prompt_cache.sqlite.seed`` → ``<target>`` at boot.

    No-op if the env flag is off, the seed is missing, or the target already
    exists. Creates the target's parent directory on demand.
    """
    if not _flag_enabled():
        return

    seed = Path(seed_dir) / SEED_FILENAME
    target = Path(target)

    if target.exists():
        log.info("cache_loader.skip_target_exists", target=str(target))
        return

    if not seed.is_file():
        log.warning("cache_loader.seed_missing", seed=str(seed))
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed, target)
    log.info("cache_loader.primed", seed=str(seed), target=str(target))
