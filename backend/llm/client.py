"""Gemini client with structured output, function-calling loop, and caching.

Three responsibilities:

1. :meth:`LLMClient.structured` — prompt → parsed Pydantic model, with exactly
   one validation-retry and SQLite short-circuit on cache hit.
2. :meth:`LLMClient.with_tools` — Gemini function-calling loop: model emits a
   function call → we invoke the matching Python callable → append the result
   and continue until the model returns a final response parsed through
   ``final_schema``. Hard-capped by ``max_iters``.
3. :meth:`LLMClient.cached_context` — memoizes Gemini ``caches.create`` for a
   shared prefix (Analyst reuses DB schema summary across calls).

Transport-level retries (5xx / connection resets) use tenacity; validation
retries are a single in-band retry inside ``structured``. The two layers are
intentionally kept separate: tenacity must NOT retry ValidationErrors.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import structlog
from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from backend.llm.prompt_cache import PromptCache

log = structlog.get_logger()


# Gemini model slug aliases. Keep this tiny — add more as agents need them.
_MODEL_ALIASES: dict[str, str] = {
    "flash": "gemini-flash-lite-latest",
    "pro": "gemini-flash-lite-latest",
}

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _gemini_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to a Gemini-compatible JSON-schema dict.

    Gemini's ``response_schema`` / tool-parameter parser rejects several fields
    that Pydantic v2 emits by default: ``additionalProperties``, ``title``,
    ``$defs``, ``anyOf`` (for nullable). Strip them recursively.
    """
    raw = schema.model_json_schema()
    return cast(dict[str, Any], _sanitize_schema(raw, defs=raw.get("$defs", {})))


_DROP_KEYS = frozenset(
    {
        "additionalProperties",
        "title",
        "$defs",
        "default",
        "prefixItems",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }
)


def _sanitize_schema(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"].rsplit("/", 1)[-1]
            resolved = defs.get(ref, {})
            return _sanitize_schema(resolved, defs)
        if "anyOf" in node:
            variants = [v for v in node["anyOf"] if v.get("type") != "null"]
            if len(variants) == 1:
                merged = {k: v for k, v in node.items() if k != "anyOf" and k not in _DROP_KEYS}
                merged.update(variants[0])
                return _sanitize_schema(merged, defs)
        # Tuples: prefixItems defines ordered element types. Gemini does not
        # support heterogeneous tuples; collapse to a single `items` entry when
        # all prefix elements share a type.
        if (
            "prefixItems" in node
            and "items" not in node
            and isinstance(node["prefixItems"], list)
            and node["prefixItems"]
        ):
            prefix_types = {p.get("type") for p in node["prefixItems"] if isinstance(p, dict)}
            if len(prefix_types) == 1 and None not in prefix_types:
                node = {**node, "items": {"type": next(iter(prefix_types))}}
        out: dict[str, Any] = {}
        for k, v in node.items():
            if k in _DROP_KEYS:
                continue
            if k == "properties" and isinstance(v, dict):
                # Property names are identifiers, not metadata — do not filter.
                out[k] = {pk: _sanitize_schema(pv, defs) for pk, pv in v.items()}
            else:
                out[k] = _sanitize_schema(v, defs)
        return out
    if isinstance(node, list):
        return [_sanitize_schema(v, defs) for v in node]
    return node


class LLMValidationError(RuntimeError):
    """Gemini output failed schema validation (after one retry) or offline miss."""


class Tool(BaseModel):
    """Function-calling tool contract handed to the Gemini loop.

    ``callable`` receives a validated instance of ``args_schema`` and returns a
    JSON-serializable dict that is fed back into the model as a
    ``function_response`` part. Tools are async because Analyst tools hit the
    DB; keeping the contract async means the sync case is just ``async def``.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str
    description: str
    args_schema: type[BaseModel]
    callable: Callable[[BaseModel], Awaitable[dict[str, Any]]]


class ToolInvocation(BaseModel):
    tool: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class _RawStep:
    """One turn of the function-calling loop as returned by the transport layer.

    Either ``function_calls`` is non-empty (model wants to run tools) OR
    ``text`` holds the final response body to be parsed via ``final_schema``.
    """

    function_calls: list[tuple[str, dict[str, Any]]] | None = None
    text: str | None = None


@dataclass
class _HistoryItem:
    role: str
    content: Any = None


@dataclass
class _LoopState:
    history: list[_HistoryItem] = field(default_factory=list)
    trace: list[ToolInvocation] = field(default_factory=list)


def _strip_fences(raw: str) -> str:
    """Gemini Flash occasionally wraps JSON in ```json ... ``` fences."""
    return _FENCE_RE.sub("", raw).strip()


def _schema_fingerprint(schema: type[BaseModel]) -> str:
    return hashlib.sha256(
        json.dumps(schema.model_json_schema(), sort_keys=True).encode()
    ).hexdigest()


class LLMClient:
    def __init__(
        self,
        *,
        cache_path: str | Path,
        model: str = "flash",
        api_key: str | None = None,
    ) -> None:
        self._model_alias = model
        self._model_name = _MODEL_ALIASES.get(model, model)
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._cache = PromptCache(cache_path)
        self._context_handles: dict[str, str] = {}
        # Defer SDK client construction — tests never need it, and importing
        # google.genai at module scope is already done for type references.
        self._client: Any | None = None

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    async def structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        cache_key: str | None = None,
    ) -> BaseModel:
        key = cache_key or self._cache_key(prompt, schema)

        cached = self._cache.get(key)
        if cached is not None:
            try:
                return schema.model_validate_json(_strip_fences(cached))
            except ValidationError:
                # Cached value is corrupt; fall through to a fresh call.
                log.warning("llm.cache.corrupt", key=key)

        if self._cache.offline_mode:
            raise LLMValidationError(f"offline: no cached response for key={key}")

        raw = await self._raw_structured(prompt=prompt, schema=schema)
        try:
            parsed = schema.model_validate_json(_strip_fences(raw))
        except ValidationError as err:
            retry_prompt = f"{prompt}\n\nYour previous output failed validation: {err}"
            raw = await self._raw_structured(prompt=retry_prompt, schema=schema)
            try:
                parsed = schema.model_validate_json(_strip_fences(raw))
            except ValidationError as err2:
                raise LLMValidationError(
                    f"schema={schema.__name__} failed after one retry: {err2}"
                ) from err2

        self._cache.put(key, raw)
        return parsed

    async def with_tools(
        self,
        prompt: str,
        tools: list[Tool],
        *,
        final_schema: type[BaseModel],
        cache_key: str | None = None,
        max_iters: int = 6,
    ) -> tuple[BaseModel, list[ToolInvocation]]:
        effective_key = cache_key or self._cache_key(prompt, final_schema)

        cached = self._cache.get(effective_key)
        if cached is not None:
            try:
                payload = json.loads(cached)
                final = final_schema.model_validate(payload["final"])
                trace = [ToolInvocation.model_validate(t) for t in payload.get("trace", [])]
                return final, trace
            except (ValidationError, ValueError, KeyError):
                log.warning("llm.cache.corrupt", key=effective_key)

        if self._cache.offline_mode:
            raise LLMValidationError(f"offline: no cached tool-loop output for key={effective_key}")

        by_name: dict[str, Tool] = {t.name: t for t in tools}
        state = _LoopState(history=[_HistoryItem(role="user", content=prompt)])

        for _ in range(max_iters):
            step = await self._raw_generate(
                history=state.history,
                tools=tools,
                final_schema=final_schema,
            )
            if step.function_calls:
                for name, args_dict in step.function_calls:
                    tool = by_name.get(name)
                    if tool is None:
                        raise LLMValidationError(f"model called unknown tool: {name}")
                    args_model = tool.args_schema.model_validate(args_dict)
                    result = await tool.callable(args_model)
                    state.trace.append(ToolInvocation(tool=name, args=args_dict, result=result))
                    state.history.append(
                        _HistoryItem(
                            role="tool",
                            content={"name": name, "args": args_dict, "result": result},
                        )
                    )
                continue
            if step.text is not None:
                try:
                    final = final_schema.model_validate_json(_strip_fences(step.text))
                except ValidationError as err:
                    raise LLMValidationError(
                        f"final_schema={final_schema.__name__} invalid: {err}"
                    ) from err
                self._cache.put(
                    effective_key,
                    json.dumps(
                        {
                            "final": final.model_dump(mode="json"),
                            "trace": [t.model_dump(mode="json") for t in state.trace],
                        }
                    ),
                )
                return final, state.trace
            raise LLMValidationError("model returned neither function_calls nor text")

        raise LLMValidationError(f"tool loop exceeded max_iters={max_iters}")

    async def cached_context(self, key: str, content: str) -> str:
        """Memoize a Gemini ``cached_content`` handle for a shared prefix.

        Returns an empty string (and logs a warning) when the upstream rejects
        the cache — typically because ``content`` is under the SDK's minimum
        size. Callers treat empty-string as "no shared cache, fall through".
        """
        if key in self._context_handles:
            return self._context_handles[key]
        try:
            handle = await self._create_cached_context(content)
        except Exception as err:  # SDK raises a grab-bag of errors
            log.warning("llm.cached_context.unavailable", key=key, error=str(err))
            return ""
        self._context_handles[key] = handle
        return handle

    # ------------------------------------------------------------------
    # Cache key
    # ------------------------------------------------------------------

    def _cache_key(self, prompt: str, schema: type[BaseModel]) -> str:
        material = f"{self._model_alias}::{prompt}::{_schema_fingerprint(schema)}"
        return hashlib.sha256(material.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Transport layer (mocked in tests)
    # ------------------------------------------------------------------

    async def _raw_structured(self, *, prompt: str, schema: type[BaseModel]) -> str:
        client = self._sdk_client()

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(6),
            wait=wait_exponential_jitter(initial=2, max=45),
            retry=retry_if_exception_type(Exception),  # transport-level only
            reraise=True,
        ):
            with attempt:
                resp = await client.aio.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=cast(Any, _gemini_schema(schema)),
                    ),
                )
                text = resp.text
                if text is None:
                    raise LLMValidationError("Gemini returned no text body")
                return str(text)
        raise LLMValidationError("unreachable: tenacity did not raise or return")

    async def _raw_generate(
        self,
        *,
        history: list[_HistoryItem],
        tools: list[Tool],
        final_schema: type[BaseModel],
    ) -> _RawStep:
        client = self._sdk_client()
        tool_decls: list[Any] = [
            genai_types.Tool(
                function_declarations=[
                    genai_types.FunctionDeclaration(
                        name=t.name,
                        description=t.description,
                        parameters=cast(Any, _gemini_schema(t.args_schema)),
                    )
                ]
            )
            for t in tools
        ]
        contents = _history_to_contents(history)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(6),
            wait=wait_exponential_jitter(initial=2, max=45),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                # Gemini rejects response_mime_type + response_schema when tools
                # are present ("Function calling with a response mime type: …
                # is unsupported"). Final-schema validation happens client-side
                # against the free-form text response in the parser layer.
                resp = await client.aio.models.generate_content(
                    model=self._model_name,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        tools=cast(Any, tool_decls),
                    ),
                )
                fn_calls = _extract_function_calls(resp)
                if fn_calls:
                    return _RawStep(function_calls=fn_calls, text=None)
                return _RawStep(function_calls=None, text=resp.text)
        raise LLMValidationError("unreachable: tenacity did not raise or return")

    async def _create_cached_context(self, content: str) -> str:
        client = self._sdk_client()
        cache = await client.aio.caches.create(
            model=self._model_name,
            config=genai_types.CreateCachedContentConfig(contents=[content]),
        )
        return str(cache.name)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _sdk_client(self) -> Any:
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client


def _history_to_contents(history: list[_HistoryItem]) -> list[Any]:
    """Map our internal history list to google-genai Content objects.

    Kept small and defensive — the SDK's exact Part/Content surface is in
    flux; tests bypass this path entirely by mocking ``_raw_generate``.
    """
    out: list[Any] = []
    for item in history:
        if item.role == "user":
            out.append(
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=str(item.content))],
                )
            )
        elif item.role == "tool":
            data = item.content or {}
            out.append(
                genai_types.Content(
                    role="tool",
                    parts=[
                        genai_types.Part.from_function_response(
                            name=data.get("name", "tool"),
                            response=data.get("result", {}),
                        )
                    ],
                )
            )
    return out


def _extract_function_calls(resp: Any) -> list[tuple[str, dict[str, Any]]]:
    """Best-effort extraction of function calls from a google-genai response.

    The SDK exposes ``response.function_calls`` on recent versions; older
    versions require walking ``candidates[0].content.parts``. We try the
    modern path first and fall back.
    """
    calls = getattr(resp, "function_calls", None)
    if calls:
        return [(c.name, dict(c.args or {})) for c in calls]
    candidates = getattr(resp, "candidates", None) or []
    out: list[tuple[str, dict[str, Any]]] = []
    for cand in candidates:
        parts = getattr(getattr(cand, "content", None), "parts", None) or []
        for part in parts:
            fn = getattr(part, "function_call", None)
            if fn is not None:
                out.append((fn.name, dict(fn.args or {})))
    return out
