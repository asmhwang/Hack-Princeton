from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

_trace: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace() -> str:
    tid = uuid.uuid4().hex
    _trace.set(tid)
    return tid


def bind_trace(trace_id: str) -> None:
    _trace.set(trace_id)


def _inject_trace(_: object, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict["trace_id"] = _trace.get() or ""
    return event_dict


def configure(level: str = "INFO", json_logs: bool = True) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _inject_trace,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
    )
