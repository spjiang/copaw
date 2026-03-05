# -*- coding: utf-8 -*-
"""Redis Stream push utility for contract skill scripts.

每个子 skill 脚本调用此模块，在执行开始 / 结束 / 出错时向 Redis Stream
推送结构化 JSON 消息，供前端实时订阅渲染。

Stream key: session_id（每个会话独立的 stream）
Field     : "data" → JSON 字符串

JSON 结构:
{
  "session_id"  : "xxx",
  "exec_id"     : "xxx",
  "skill_name"  : "contract_template_match",
  "stage"       : "start" | "end" | "error",
  "render_type" : "progress" | "template_list" | "contract_draft" | "error",
  "input"       : {...},
  "output"      : {...},
  "timestamp"   : "2026-03-05T12:00:00.000Z",
  "runtime_ms"  : 1234
}

环境变量（在 .env 或系统环境中配置）：
  REDIS_HOST      - Redis 主机地址  (默认 127.0.0.1)
  REDIS_PORT      - Redis 端口      (默认 6379)
  REDIS_PASSWORD  - Redis 密码      (默认 空)
  REDIS_DB        - Redis 数据库编号 (默认 0)

若 Redis 未配置或连接失败，静默跳过，不影响 skill 正常执行。
"""
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Redis 连接（懒加载，进程内单例）
# ---------------------------------------------------------------------------

_redis_client = None
_redis_available: bool | None = None


def _get_client():
    global _redis_client, _redis_available
    if _redis_available is not None:
        return _redis_client if _redis_available else None

    host     = os.environ.get("REDIS_HOST", "127.0.0.1")
    port     = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD") or None
    db       = int(os.environ.get("REDIS_DB", "0"))

    try:
        import redis as redis_lib
        r = redis_lib.Redis(
            host=host, port=port, password=password, db=db,
            socket_connect_timeout=2, socket_timeout=3,
            decode_responses=True,
        )
        r.ping()
        _redis_client    = r
        _redis_available = True
        print(f"[redis_push] 已连接 Redis {host}:{port}", file=sys.stderr)
    except Exception as e:
        _redis_available = False
        print(f"[redis_push] Redis 不可用，跳过推送（{e}）", file=sys.stderr)

    return _redis_client if _redis_available else None


# ---------------------------------------------------------------------------
# 核心推送函数
# ---------------------------------------------------------------------------

def redis_push(
    session_id:  str,
    skill_name:  str,
    stage:       str,               # "start" | "end" | "error"
    render_type: str,               # "progress" | "template_list" | "contract_draft" | "error"
    input_data:  dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    exec_id:     str = "",
    run_id:      str = "",
    runtime_ms:  int = 0,
    maxlen:      int = 500,         # stream 最大长度，自动裁剪旧消息
) -> None:
    """向 Redis Stream（以 session_id 为 key）推送一条结构化 JSON 消息。

    失败时静默跳过，不会影响 skill 主流程。
    """
    r = _get_client()
    if r is None:
        return

    payload: dict[str, Any] = {
        "session_id":  session_id,
        "exec_id":     exec_id,
        "run_id":      run_id,
        "skill_name":  skill_name,
        "stage":       stage,
        "render_type": render_type,
        "input":       input_data  or {},
        "output":      output_data or {},
        "timestamp":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "runtime_ms":  runtime_ms,
    }

    try:
        r.xadd(session_id, {"data": json.dumps(payload, ensure_ascii=False)}, maxlen=maxlen)
        print(
            f"[redis_push] → {session_id}  skill={skill_name}  stage={stage}  render={render_type}",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"[redis_push] xadd 失败：{e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 便捷包装
# ---------------------------------------------------------------------------

def push_start(session_id: str, skill_name: str, input_data: dict,
               exec_id: str = "", run_id: str = "") -> None:
    """skill 开始执行时推送。"""
    redis_push(
        session_id=session_id,
        skill_name=skill_name,
        stage="start",
        render_type="progress",
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
    )


def push_end(
    session_id:  str,
    skill_name:  str,
    input_data:  dict,
    output_data: dict,
    render_type: str,
    exec_id:     str = "",
    run_id:      str = "",
    runtime_ms:  int = 0,
) -> None:
    """skill 成功完成时推送。"""
    redis_push(
        session_id=session_id,
        skill_name=skill_name,
        stage="end",
        render_type=render_type,
        input_data=input_data,
        output_data=output_data,
        exec_id=exec_id,
        run_id=run_id,
        runtime_ms=runtime_ms,
    )


def push_error(
    session_id: str,
    skill_name: str,
    input_data: dict,
    error_msg:  str,
    exec_id:    str = "",
    run_id:     str = "",
    runtime_ms: int = 0,
) -> None:
    """skill 出错时推送。"""
    redis_push(
        session_id=session_id,
        skill_name=skill_name,
        stage="error",
        render_type="error",
        input_data=input_data,
        output_data={"error": error_msg},
        exec_id=exec_id,
        run_id=run_id,
        runtime_ms=runtime_ms,
    )
