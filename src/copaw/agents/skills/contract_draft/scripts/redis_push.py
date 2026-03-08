# -*- coding: utf-8 -*-
"""Portable Redis Stream push helper for contract_draft."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

_redis_client = None
_redis_available: bool | None = None


def _get_client():
    global _redis_client, _redis_available
    if _redis_available is not None:
        return _redis_client if _redis_available else None

    host = os.environ.get("REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD") or None
    db = int(os.environ.get("REDIS_DB", "0"))

    try:
        import redis as redis_lib

        client = redis_lib.Redis(
            host=host,
            port=port,
            password=password,
            db=db,
            socket_connect_timeout=2,
            socket_timeout=3,
            decode_responses=True,
        )
        client.ping()
        _redis_client = client
        _redis_available = True
        print(f"[redis_push] connected {host}:{port}", file=sys.stderr)
    except Exception as exc:
        _redis_available = False
        print(f"[redis_push] unavailable: {exc}", file=sys.stderr)

    return _redis_client if _redis_available else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def redis_push(
    session_id: str,
    skill_name: str,
    stage: str,
    render_type: str,
    skill_label: str = "",
    event_name: str = "",
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    exec_id: str = "",
    run_id: str = "",
    runtime_ms: int = 0,
    user_id: str = "",
    maxlen: int = 500,
) -> None:
    client = _get_client()
    if client is None:
        return

    payload: dict[str, Any] = {
        "session_id": session_id,
        "user_id": user_id or os.environ.get("COPAW_USER_ID", ""),
        "exec_id": exec_id,
        "run_id": run_id,
        "skill_name": skill_name,
        "skill_label": skill_label or skill_name,
        "stage": stage,
        "render_type": render_type,
        "event_name": event_name or render_type or stage,
        "input": input_data or {},
        "output": output_data or {},
        "timestamp": _utc_now(),
        "runtime_ms": runtime_ms,
    }

    try:
        client.xadd(
            session_id,
            {"data": json.dumps(payload, ensure_ascii=False)},
            maxlen=maxlen,
        )
        print(
            f"[redis_push] -> {session_id} skill={skill_name} stage={stage} render={render_type}",
            file=sys.stderr,
        )
    except Exception as exc:
        print(f"[redis_push] xadd failed: {exc}", file=sys.stderr)


def push_start(
    session_id: str,
    skill_name: str,
    input_data: dict[str, Any],
    exec_id: str = "",
    run_id: str = "",
    user_id: str = "",
    render_type: str = "agent_start",
    skill_label: str = "",
    event_name: str = "",
) -> None:
    redis_push(
        session_id=session_id,
        user_id=user_id,
        skill_name=skill_name,
        stage="start",
        render_type=render_type,
        skill_label=skill_label,
        event_name=event_name,
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
    )


def push_running(
    session_id: str,
    skill_name: str,
    render_type: str,
    skill_label: str = "",
    event_name: str = "",
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    exec_id: str = "",
    run_id: str = "",
    runtime_ms: int = 0,
    user_id: str = "",
) -> None:
    redis_push(
        session_id=session_id,
        user_id=user_id,
        skill_name=skill_name,
        stage="running",
        render_type=render_type,
        skill_label=skill_label,
        event_name=event_name,
        input_data=input_data,
        output_data=output_data,
        exec_id=exec_id,
        run_id=run_id,
        runtime_ms=runtime_ms,
    )


def push_end(
    session_id: str,
    skill_name: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    render_type: str = "agent_end",
    exec_id: str = "",
    run_id: str = "",
    runtime_ms: int = 0,
    user_id: str = "",
    skill_label: str = "",
    event_name: str = "",
) -> None:
    redis_push(
        session_id=session_id,
        user_id=user_id,
        skill_name=skill_name,
        stage="end",
        render_type=render_type,
        skill_label=skill_label,
        event_name=event_name,
        input_data=input_data,
        output_data=output_data,
        exec_id=exec_id,
        run_id=run_id,
        runtime_ms=runtime_ms,
    )


def push_error(
    session_id: str,
    skill_name: str,
    input_data: dict[str, Any],
    error_msg: str,
    exec_id: str = "",
    run_id: str = "",
    runtime_ms: int = 0,
    user_id: str = "",
    skill_label: str = "",
    event_name: str = "",
    render_type: str = "error",
) -> None:
    redis_push(
        session_id=session_id,
        user_id=user_id,
        skill_name=skill_name,
        stage="error",
        render_type=render_type,
        skill_label=skill_label,
        event_name=event_name,
        input_data=input_data,
        output_data={"error": error_msg},
        exec_id=exec_id,
        run_id=run_id,
        runtime_ms=runtime_ms,
    )
