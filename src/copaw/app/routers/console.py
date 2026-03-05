# -*- coding: utf-8 -*-
"""Console API: push messages for cron text bubbles on the frontend."""

from fastapi import APIRouter, Query
from pydantic import BaseModel


router = APIRouter(prefix="/console", tags=["console"])


@router.get("/push-messages")
async def get_push_messages(
    session_id: str | None = Query(None, description="Optional session id"),
):
    """
    Return pending push messages. Without session_id: recent messages
    (all sessions, last 60s), not consumed so every tab sees them.
    """
    from ..console_push_store import get_recent, take

    if session_id:
        messages = await take(session_id)
    else:
        messages = await get_recent()
    return {"messages": messages}


class InternalPushRequest(BaseModel):
    session_id: str
    user_id: str
    text: str
    msg_type: str = "progress"
    subscribe_id: str | None = None


@router.post("/internal-push")
async def internal_push(req: InternalPushRequest):
    """Internal endpoint for skill scripts (subprocesses) to push real-time messages.

    Skills scripts call this via HTTP loopback so their progress is visible
    in the chat frontend. subscribe_id = session_id + "_" + user_id.
    """
    from ..console_push_store import append

    label = {"progress": "⏳", "result": "✅", "error": "❌", "chain": "🔗"}.get(
        req.msg_type, "📌"
    )
    text = req.text if req.text.startswith(tuple("⏳✅❌🔗📌🤖📋📄🔍")) else f"{label} {req.text}"
    await append(req.session_id, text)
    return {"ok": True}
