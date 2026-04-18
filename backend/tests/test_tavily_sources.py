"""Coverage for the four Tavily-backed Scout source modules.

Each of news/policy/logistics/macro exposes:

- ``QUERIES``: a non-empty list of query strings drawn from
  ``tavily_queries.md`` (judging artifact).
- ``SOURCE_NAME``: the ``signals.source_name`` stamped on each row.
- ``SOURCE_CATEGORY``: literal matching :data:`SourceCategory`.
- ``CADENCE_SECONDS``: cadence the Scout main loop will schedule this source
  on — must line up with the values called out in the master plan (news 60,
  policy 900, logistics 600, macro 1800).
- ``poll_once(db_session, llm, bus, client)``: coroutine that issues one
  fan-out of all queries and pipes every result through
  :func:`ingest_tavily_result`.

The tests mock the Tavily client and the LLM so no DB / network is needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.agents.scout.sources import logistics, macro, news, policy

_MODULES = [
    (news, "news", 60),
    (policy, "policy", 900),
    (logistics, "logistics", 600),
    (macro, "macro", 1800),
]
_EXPECTED_QUERIES_PER_MODULE = 20


class _StubClient:
    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str, int]] = []

    async def search(self, query: str, *, topic: str, days: int = 1) -> list[dict[str, Any]]:
        self.calls.append((query, topic, days))
        return self.payload


class _IngestRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], str, str]] = []

    async def record(
        self,
        raw: dict[str, Any],
        *,
        source_category: str,
        source_name: str,
        **_kwargs: Any,
    ) -> None:
        self.calls.append((raw, source_category, source_name))


class _FlakyRecorder:
    """Raises on the first call, succeeds thereafter — used to show error isolation."""

    def __init__(self) -> None:
        self.attempts = 0

    async def record(self, *_args: Any, **_kwargs: Any) -> None:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("simulated classifier blow-up")


def test_each_module_declares_required_constants() -> None:
    for module, category, cadence in _MODULES:
        assert module.QUERIES, f"{module.__name__} QUERIES empty"
        assert category == module.SOURCE_CATEGORY
        assert f"tavily.{category}" == module.SOURCE_NAME
        assert cadence == module.CADENCE_SECONDS


def test_queries_length_matches_library() -> None:
    # tavily_queries.md documents 20 queries per category — keep the code in
    # lockstep so the judging artifact does not drift from runtime behavior.
    for module, _category, _cadence in _MODULES:
        assert len(module.QUERIES) == _EXPECTED_QUERIES_PER_MODULE, (
            f"{module.__name__} has {len(module.QUERIES)} queries, "
            f"expected {_EXPECTED_QUERIES_PER_MODULE}"
        )


@pytest.mark.asyncio
async def test_poll_once_fan_outs_every_query(monkeypatch: pytest.MonkeyPatch) -> None:
    for module, category, _cadence in _MODULES:
        stub_client = _StubClient(
            payload=[{"title": "Sample", "url": "https://example.com/x", "content": "..."}]
        )
        recorder = _IngestRecorder()
        monkeypatch.setattr(module, "ingest_tavily_result", recorder.record)

        await module.poll_once(
            db_session=None,
            llm=None,
            bus=None,
            client=stub_client,
        )

        assert len(stub_client.calls) == len(module.QUERIES)
        assert len(recorder.calls) == len(module.QUERIES)
        assert all(src == category for _raw, src, _name in recorder.calls)


@pytest.mark.asyncio
async def test_poll_once_continues_past_per_result_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One failing ingest must not stop the remaining queries from polling."""
    stub_client = _StubClient(
        payload=[{"title": "Sample", "url": "https://example.com/x", "content": "..."}]
    )
    recorder = _FlakyRecorder()
    monkeypatch.setattr(news, "ingest_tavily_result", recorder.record)

    await news.poll_once(
        db_session=None,
        llm=None,
        bus=None,
        client=stub_client,
    )

    assert len(stub_client.calls) == len(news.QUERIES)
    assert recorder.attempts == len(news.QUERIES)
