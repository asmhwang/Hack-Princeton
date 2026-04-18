"""TDD for :mod:`backend.agents.scout.sources.tavily`.

Three concerns covered:

1. Happy path — ``search`` posts to the Tavily REST endpoint with the expected
   JSON body and returns the ``results`` list verbatim.
2. SQLite cache — successful responses persist to the cache DB and a
   subsequent call in ``DEMO_OFFLINE_CACHE`` mode returns the cached payload
   without touching the network.
3. Offline miss — when offline and the cache is cold, ``search`` returns an
   empty list instead of raising (demo-safe degradation).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from backend.agents.scout.sources.tavily import TavilyClient

_SAMPLE_RESULTS = [
    {"title": "Port strike escalates", "url": "https://example.com/a", "content": "..."},
    {"title": "Dockworker walkout", "url": "https://example.com/b", "content": "..."},
]


@pytest.mark.asyncio
async def test_search_posts_body_and_returns_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.delenv("DEMO_OFFLINE_CACHE", raising=False)

    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"results": _SAMPLE_RESULTS})

    transport = httpx.MockTransport(_handler)
    client = TavilyClient(cache_path=tmp_path / "tavily.sqlite", transport=transport)

    results = await client.search("port strike", topic="news", days=1)

    assert results == _SAMPLE_RESULTS
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["body"] == {
        "api_key": "test-key",
        "query": "port strike",
        "topic": "news",
        "days": 1,
        "max_results": 10,
        "include_answer": False,
    }


@pytest.mark.asyncio
async def test_cache_hit_in_offline_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.delenv("DEMO_OFFLINE_CACHE", raising=False)

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": _SAMPLE_RESULTS})

    client = TavilyClient(
        cache_path=tmp_path / "tavily.sqlite",
        transport=httpx.MockTransport(_handler),
    )
    # Warm cache via live call.
    await client.search("port strike", topic="news", days=1)

    # Flip offline mode and use a transport that would fail if hit.
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", "true")

    def _explode(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("network call issued in offline mode")

    offline_client = TavilyClient(
        cache_path=tmp_path / "tavily.sqlite",
        transport=httpx.MockTransport(_explode),
    )
    cached = await offline_client.search("port strike", topic="news", days=1)
    assert cached == _SAMPLE_RESULTS


@pytest.mark.asyncio
async def test_offline_cold_cache_returns_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", "true")

    def _explode(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("network call issued in offline mode")

    client = TavilyClient(
        cache_path=tmp_path / "tavily.sqlite",
        transport=httpx.MockTransport(_explode),
    )
    assert await client.search("never cached", topic="news", days=1) == []


@pytest.mark.asyncio
async def test_retries_on_transient_5xx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.delenv("DEMO_OFFLINE_CACHE", raising=False)

    calls = {"n": 0}

    def _handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"error": "upstream"})
        return httpx.Response(200, json={"results": _SAMPLE_RESULTS})

    client = TavilyClient(
        cache_path=tmp_path / "tavily.sqlite",
        transport=httpx.MockTransport(_handler),
    )
    results = await client.search("port strike", topic="news", days=1)
    assert results == _SAMPLE_RESULTS
    assert calls["n"] == 3
