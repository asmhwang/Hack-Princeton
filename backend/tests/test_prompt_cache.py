from __future__ import annotations

from pathlib import Path

import pytest

from backend.llm.prompt_cache import PromptCache


def test_put_get_roundtrip(tmp_path: Path) -> None:
    cache = PromptCache(tmp_path / "c.sqlite")
    cache.put("k1", "v1")
    assert cache.get("k1") == "v1"


def test_missing_key_returns_none(tmp_path: Path) -> None:
    cache = PromptCache(tmp_path / "c.sqlite")
    assert cache.get("nope") is None


def test_offline_flag_disables_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", "true")
    cache = PromptCache(tmp_path / "c.sqlite")
    assert cache.offline_mode is True
    cache.put("k1", "v1")
    assert cache.get("k1") is None
