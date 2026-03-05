#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contract template search script.

Queries the local template API with the user's query text + optional contract_type
to find the most similar real contract templates.

Usage:
    python template_match.py <session_id> <user_id> <exec_id> <query_text> [contract_type]

contract_type: "采购" | "销售" | "" (auto-detect from query)
"""
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 内联 Redis push（不依赖 shared 导入）
# ---------------------------------------------------------------------------
def _rp(session_id, skill_name, stage, render_type,
        input_data=None, output_data=None,
        exec_id="", run_id="", runtime_ms=0):
    try:
        import redis as _r
        _cli = _r.Redis(
            host=os.environ.get("REDIS_HOST", "127.0.0.1"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            password=os.environ.get("REDIS_PASSWORD") or None,
            db=int(os.environ.get("REDIS_DB", "0")),
            socket_connect_timeout=2, socket_timeout=3, decode_responses=True,
        )
        _cli.ping()
        _payload = {
            "session_id": session_id, "exec_id": exec_id, "run_id": run_id,
            "skill_name": skill_name, "stage": stage, "render_type": render_type,
            "input": input_data or {}, "output": output_data or {},
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "runtime_ms": runtime_ms,
        }
        _cli.xadd(session_id, {"data": json.dumps(_payload, ensure_ascii=False)}, maxlen=500)
        print(f"[redis] → {session_id} skill={skill_name} stage={stage}", file=sys.stderr)
    except Exception as _e:
        print(f"[redis] skip: {_e}", file=sys.stderr)


def _push_bubble(session_id, user_id, msg, msg_type="progress"):
    try:
        import urllib.request as _ur
        _body = json.dumps({
            "session_id": session_id, "user_id": user_id,
            "text": msg, "msg_type": msg_type,
            "subscribe_id": f"{session_id}_{user_id}",
        }).encode()
        _req = _ur.Request(
            "http://127.0.0.1:8088/api/console/internal-push",
            data=_body, headers={"Content-Type": "application/json"}, method="POST",
        )
        _ur.urlopen(_req, timeout=3)
    except Exception:
        pass


try:
    import requests
except ImportError:
    requests = None  # type: ignore

TEMPLATE_API = os.environ.get("TEMPLATE_API_BASE", "http://localhost:9000")


def search_templates(query: str, contract_type: str = "", top_k: int = 5) -> dict:
    if requests is None:
        raise RuntimeError("requests library not installed")
    resp = requests.post(
        f"{TEMPLATE_API}/api/template/vector-search",
        json={"query": query, "contract_type": contract_type, "top_k": top_k},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    if len(sys.argv) < 5:
        print(json.dumps({"error": "usage: template_match.py session_id user_id exec_id query_text [contract_type]"}))
        sys.exit(1)

    
    session_id  = (
        os.environ.get("COPAW_SESSION_ID")
        or (sys.argv[1] if len(sys.argv) > 1 else "")
        or "unknown_session"
    )

    user_id       = os.environ.get("COPAW_USER_ID") or "unknown_user"
    exec_id       = sys.argv[3]
    query_text    = sys.argv[4]
    contract_type = sys.argv[5] if len(sys.argv) > 5 else ""

    run_id     = str(uuid.uuid4())
    start_time = time.time()

    _skill = "合同模板匹配"
    _input = {"query": query_text, "contract_type": contract_type, "session_id": session_id}

    type_hint = f"（{contract_type}合同）" if contract_type else ""
    _push_bubble(session_id, user_id, f"🔍 正在检索匹配合同模板{type_hint}...")
    _rp(session_id, _skill, "start", "progress", input_data=_input, exec_id=exec_id, run_id=run_id)

    try:
        result = search_templates(query_text, contract_type=contract_type)
        runtime = int((time.time() - start_time) * 1000)

        total = result.get("total", 0)
        detected = result.get("detected_contract_type", "")
        type_msg = f"（{detected}合同）" if detected else ""
        _push_bubble(
            session_id, user_id,
            f"✅ 找到 {total} 份相似模板{type_msg}" if total > 0 else "ℹ️ 未找到匹配模板，将直接起草",
            "result" if total > 0 else "progress",
        )

        _render = "template_list" if total > 0 else "progress"
        _rp(session_id, _skill, "end", _render,
            input_data=_input, output_data=result,
            exec_id=exec_id, run_id=run_id, runtime_ms=runtime)

        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        runtime = int((time.time() - start_time) * 1000)
        _push_bubble(session_id, user_id, f"❌ 模板检索失败：{e}", "error")
        _rp(session_id, _skill, "error", "error",
            input_data=_input, output_data={"error": str(e)},
            exec_id=exec_id, run_id=run_id, runtime_ms=runtime)
        print(json.dumps({"templates": [], "total": 0, "error": str(e)}))


if __name__ == "__main__":
    main()
