# -*- coding: utf-8 -*-
"""WebSocket push utility for contract_draft scripts."""

import os
import sys

COPAW_API = os.environ.get("COPAW_API_BASE", "http://127.0.0.1:8088")

_endpoint_available: bool | None = None


def _check_endpoint() -> bool:
    global _endpoint_available
    if _endpoint_available is not None:
        return _endpoint_available
    try:
        import requests

        r = requests.options(
            f"{COPAW_API}/api/console/internal-push",
            timeout=2,
        )
        _endpoint_available = r.status_code != 404
    except Exception:
        _endpoint_available = False
    return _endpoint_available


def push(
    session_id: str,
    user_id: str,
    text: str,
    msg_type: str = "progress",
) -> None:
    label = {"progress": "⏳", "result": "✅", "error": "❌", "chain": "🔗"}.get(
        msg_type, "📌"
    )
    display = text if text.startswith(tuple("⏳✅❌🔗📌🤖📋📄🔍📊")) else f"{label} {text}"

    print(f"[push] {display}", file=sys.stderr)

    if not _check_endpoint():
        return

    try:
        import requests

        requests.post(
            f"{COPAW_API}/api/console/internal-push",
            json={
                "subscribe_id": f"{session_id}_{user_id}",
                "session_id": session_id,
                "user_id": user_id,
                "text": display,
                "msg_type": msg_type,
            },
            timeout=3,
        )
    except Exception:
        pass
