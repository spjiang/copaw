# -*- coding: utf-8 -*-
"""SSE endpoint for Redis Stream debug panel.

GET /api/redis/stream/{session_id}
  - Subscribes to the Redis Stream keyed by session_id
  - Streams each new message as Server-Sent Events to the browser
  - Used by the frontend debug panel to display skill execution results in real-time

Query params:
  last_id: Redis Stream ID to start reading from (default "$" = only new messages)
"""
import asyncio
import json
import os
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/redis", tags=["redis"])


def _redis_config():
    return {
        "host": os.environ.get("REDIS_HOST", "127.0.0.1"),
        "port": int(os.environ.get("REDIS_PORT", "6379")),
        "password": os.environ.get("REDIS_PASSWORD") or None,
        "db": int(os.environ.get("REDIS_DB", "0")),
    }


def _get_redis():
    # 每次调用时从 os.environ 读取，确保拿到 load_envs_into_environ() 注入后的值
    cfg = _redis_config()
    try:
        import redis as redis_lib
        r = redis_lib.Redis(
            host=cfg["host"], port=cfg["port"],
            password=cfg["password"], db=cfg["db"],
            socket_connect_timeout=2, socket_timeout=5,
            decode_responses=True,
        )
        r.ping()
        return r
    except Exception:
        return None


@router.get("/ping")
async def redis_ping():
    """Manual Redis connectivity test for debug panel."""
    cfg = _redis_config()
    try:
        import redis as redis_lib
        r = redis_lib.Redis(
            host=cfg["host"], port=cfg["port"],
            password=cfg["password"], db=cfg["db"],
            socket_connect_timeout=2, socket_timeout=5,
            decode_responses=True,
        )
        r.ping()
        return {"ok": True, "host": cfg["host"], "port": cfg["port"], "db": cfg["db"]}
    except Exception as e:
        return {
            "ok": False,
            "host": cfg["host"],
            "port": cfg["port"],
            "db": cfg["db"],
            "error": str(e),
        }


async def _stream_events(session_id: str, last_id: str) -> AsyncGenerator[str, None]:
    """Poll Redis Stream and yield SSE events."""
    r = _get_redis()
    if r is None:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Redis not available', 'session_id': session_id})}\n\n"
        return

    # Send a connected heartbeat
    yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

    ping_counter = 0
    while True:
        try:
            # Non-blocking xread (count=20, no block timeout)
            entries = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda lid=last_id: r.xread({session_id: lid}, count=20),
            )
            if entries:
                for _stream_key, messages in entries:
                    for msg_id, fields in messages:
                        last_id = msg_id
                        try:
                            data = json.loads(fields.get("data", "{}"))
                        except Exception:
                            data = fields
                        payload = json.dumps(
                            {"type": "skill_event", "id": msg_id, **data},
                            ensure_ascii=False,
                        )
                        yield f"data: {payload}\n\n"
                await asyncio.sleep(0.1)
            else:
                # No new messages — sleep then send periodic ping every ~10s
                await asyncio.sleep(1)
                ping_counter += 1
                if ping_counter >= 10:
                    ping_counter = 0
                    yield ": ping\n\n"

        except asyncio.CancelledError:
            break
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            await asyncio.sleep(2)


@router.get("/stream/{session_id}")
async def redis_stream(session_id: str, last_id: str = "$"):
    """SSE endpoint: subscribe to Redis Stream for a session."""
    return StreamingResponse(
        _stream_events(session_id, last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
