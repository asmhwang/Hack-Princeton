from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from backend.llm.client import (
    LLMClient,
    LLMValidationError,
    Tool,
    ToolInvocation,
    _RawStep,
)


class _Out(BaseModel):
    n: int


@pytest.mark.asyncio
async def test_structured_returns_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="flash")

    async def fake(**_: Any) -> str:
        return '{"n":42}'

    monkeypatch.setattr(client, "_raw_structured", fake)
    out = await client.structured("prompt", _Out)
    assert out == _Out(n=42)


@pytest.mark.asyncio
async def test_structured_retries_once_on_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, Any]] = []

    async def fake(**k: Any) -> str:
        calls.append(k)
        return '{"n":"not-an-int"}' if len(calls) == 1 else '{"n":3}'

    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="flash")
    monkeypatch.setattr(client, "_raw_structured", fake)
    out = await client.structured("prompt", _Out)
    assert out == _Out(n=3)
    assert len(calls) == 2  # noqa: PLR2004 — exactly-one-retry rule


@pytest.mark.asyncio
async def test_structured_raises_after_second_validation_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake(**_: Any) -> str:
        return '{"n":"still-bad"}'

    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="flash")
    monkeypatch.setattr(client, "_raw_structured", fake)
    with pytest.raises(LLMValidationError):
        await client.structured("prompt", _Out)


@pytest.mark.asyncio
async def test_offline_cache_short_circuits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="flash")
    # prime the cache
    client._cache.put(client._cache_key("prompt", _Out), '{"n":7}')

    async def _should_not_call(**_: Any) -> str:
        raise AssertionError("api called")

    monkeypatch.setattr(client, "_raw_structured", _should_not_call)
    out = await client.structured("prompt", _Out)
    assert out == _Out(n=7)


# -----------------------------------------------------------------------------
# Tool-calling loop
# -----------------------------------------------------------------------------


class _AArgs(BaseModel):
    x: int


class _BArgs(BaseModel):
    y: int


class _Final(BaseModel):
    total: int


@pytest.mark.asyncio
async def test_with_tools_runs_loop_in_order_and_stops_at_final(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    invoked: list[tuple[str, dict[str, Any]]] = []

    async def tool_a(args: _AArgs) -> dict[str, Any]:
        invoked.append(("tool_a", args.model_dump()))
        return {"a_result": args.x * 10}

    async def tool_b(args: _BArgs) -> dict[str, Any]:
        invoked.append(("tool_b", args.model_dump()))
        return {"b_result": args.y + 1}

    tools = [
        Tool(name="tool_a", description="A", args_schema=_AArgs, callable=tool_a),
        Tool(name="tool_b", description="B", args_schema=_BArgs, callable=tool_b),
    ]

    steps: list[_RawStep] = [
        _RawStep(function_calls=[("tool_a", {"x": 2})], text=None),
        _RawStep(function_calls=[("tool_b", {"y": 5})], text=None),
        _RawStep(function_calls=None, text='{"total": 26}'),
    ]

    async def fake_generate(**_: Any) -> _RawStep:
        return steps.pop(0)

    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="pro")
    monkeypatch.setattr(client, "_raw_generate", fake_generate)

    result, trace = await client.with_tools("prompt", tools, final_schema=_Final)

    assert result == _Final(total=26)
    assert [(t.tool, t.args) for t in trace] == [
        ("tool_a", {"x": 2}),
        ("tool_b", {"y": 5}),
    ]
    assert trace[0].result == {"a_result": 20}
    assert trace[1].result == {"b_result": 6}
    assert invoked == [("tool_a", {"x": 2}), ("tool_b", {"y": 5})]


@pytest.mark.asyncio
async def test_with_tools_raises_on_max_iters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def tool_a(args: _AArgs) -> dict[str, Any]:
        return {"ok": True}

    tools = [Tool(name="tool_a", description="A", args_schema=_AArgs, callable=tool_a)]

    async def fake_generate(**_: Any) -> _RawStep:
        # model never stops calling the tool
        return _RawStep(function_calls=[("tool_a", {"x": 1})], text=None)

    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="pro")
    monkeypatch.setattr(client, "_raw_generate", fake_generate)

    with pytest.raises(LLMValidationError):
        await client.with_tools("prompt", tools, final_schema=_Final, max_iters=3)


@pytest.mark.asyncio
async def test_tool_invocation_model_shape() -> None:
    inv = ToolInvocation(tool="t", args={"x": 1}, result={"ok": True})
    assert inv.tool == "t"
    assert inv.args == {"x": 1}
    assert inv.result == {"ok": True}


@pytest.mark.asyncio
async def test_api_key_rotates_on_quota_exhausted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """On 429 RESOURCE_EXHAUSTED, LLMClient cycles to the next key and retries."""
    monkeypatch.setenv("GEMINI_API_KEYS", "key-A,key-B,key-C")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="flash")
    assert client._api_keys == ["key-A", "key-B", "key-C"]
    assert client._key_idx == 0

    calls: list[str | None] = []

    async def fake_once() -> str:
        calls.append(client._api_key)
        # First two keys report quota exhausted; third succeeds.
        if len(calls) < 3:  # noqa: PLR2004
            raise RuntimeError(
                "429 RESOURCE_EXHAUSTED. Quota exceeded for generate_content_free_tier_requests"
            )
        return "ok"

    out = await client._with_key_rotation(fake_once)
    assert out == "ok"
    assert calls == ["key-A", "key-B", "key-C"]
    assert client._key_idx == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_api_key_rotation_reraises_non_quota_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-quota errors propagate immediately without rotating."""
    monkeypatch.setenv("GEMINI_API_KEYS", "key-A,key-B")

    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="flash")

    async def always_fails() -> str:
        raise RuntimeError("400 INVALID_ARGUMENT something else entirely")

    with pytest.raises(RuntimeError, match="INVALID_ARGUMENT"):
        await client._with_key_rotation(always_fails)
    assert client._key_idx == 0  # no rotation


@pytest.mark.asyncio
async def test_api_key_rotation_exhausts_all_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When every configured key is quota-exhausted, last error propagates."""
    monkeypatch.setenv("GEMINI_API_KEYS", "key-A,key-B")

    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="flash")

    async def always_quota() -> str:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    with pytest.raises(RuntimeError, match="429"):
        await client._with_key_rotation(always_quota)
    # Should have attempted both keys before giving up.
    assert client._key_idx == 1
