"""TDD: offline prompt-cache loader (Task 12.4).

``prime_cache_if_offline(seed_dir, target)`` copies the seed SQLite into the
active cache path at boot when ``DEMO_OFFLINE_CACHE=true`` and the target does
not already exist. Idempotent: never overwrites an existing cache. No-op if
the env flag is absent or falsy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.llm.cache_loader import prime_cache_if_offline

_SEED_NAME = "prompt_cache.sqlite.seed"


def _make_seed(seed_dir: Path, payload: bytes = b"payload") -> None:
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / _SEED_NAME).write_bytes(payload)


def test_copies_seed_when_offline_and_target_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", "true")
    seed = tmp_path / "seeds"
    _make_seed(seed, b"payload")
    target = tmp_path / "cache.sqlite"

    prime_cache_if_offline(seed, target)

    assert target.read_bytes() == b"payload"


def test_noop_when_env_flag_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_OFFLINE_CACHE", raising=False)
    seed = tmp_path / "seeds"
    _make_seed(seed)
    target = tmp_path / "cache.sqlite"

    prime_cache_if_offline(seed, target)

    assert not target.exists()


@pytest.mark.parametrize("val", ["false", "0", "no", ""])
def test_noop_when_env_flag_falsy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, val: str
) -> None:
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", val)
    seed = tmp_path / "seeds"
    _make_seed(seed)
    target = tmp_path / "cache.sqlite"

    prime_cache_if_offline(seed, target)

    assert not target.exists()


def test_noop_when_target_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", "true")
    seed = tmp_path / "seeds"
    _make_seed(seed, b"new-seed")
    target = tmp_path / "cache.sqlite"
    target.write_bytes(b"existing")

    prime_cache_if_offline(seed, target)

    # Existing cache must NOT be overwritten
    assert target.read_bytes() == b"existing"


def test_noop_when_seed_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", "true")
    seed = tmp_path / "seeds"
    seed.mkdir()
    target = tmp_path / "cache.sqlite"

    # no seed file present → no-op, no exception
    prime_cache_if_offline(seed, target)

    assert not target.exists()


def test_creates_target_parent_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", "true")
    seed = tmp_path / "seeds"
    _make_seed(seed, b"bytes")
    target = tmp_path / "nested" / "dir" / "cache.sqlite"

    prime_cache_if_offline(seed, target)

    assert target.read_bytes() == b"bytes"
