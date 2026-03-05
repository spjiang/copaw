#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Push contract template params extraction result to Redis Stream.

Usage:
    python push_params.py <params_json_file> [exec_id] [session_id]

Output (stdout): JSON  { "ok": true } | { "error": "..." }
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SKILL = "参数提取智能体"


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


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: push_params.py <params_json_file> [exec_id] [session_id]"}))
        sys.exit(1)

    params_file = Path(sys.argv[1])
    exec_id     = sys.argv[2] if len(sys.argv) > 2 else ""
    session_id  = (
        os.environ.get("COPAW_SESSION_ID")
        or (sys.argv[3] if len(sys.argv) > 3 else "")
        or "unknown_session"
    )
    user_id     = os.environ.get("COPAW_USER_ID") or "unknown_user"
    run_id      = str(uuid.uuid4())
    _input      = {"params_file": str(params_file), "exec_id": exec_id}

    _push_bubble(session_id, user_id, "🧩 正在推送模板参数到 Redis...")
    _rp(session_id, _SKILL, "start", "progress", input_data=_input, exec_id=exec_id, run_id=run_id)

    if not params_file.exists():
        err = f"params file not found: {params_file}"
        _rp(session_id, _SKILL, "error", "error",
            input_data=_input, output_data={"error": err},
            exec_id=exec_id, run_id=run_id)
        print(json.dumps({"error": err}))
        sys.exit(1)

    try:
        raw = params_file.read_text(encoding="utf-8").strip()
        # 兼容 LLM 有时会在 JSON 外面包裹 ```json ... ``` 代码块
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            ).strip()

        params_data = json.loads(raw)
    except Exception as e:
        _rp(session_id, _SKILL, "error", "error",
            input_data=_input, output_data={"error": f"JSON 解析失败：{e}"},
            exec_id=exec_id, run_id=run_id)
        print(json.dumps({"error": f"JSON parse error: {e}"}))
        sys.exit(1)

    param_count = len(params_data.get("params", []))
    _push_bubble(session_id, user_id,
                 f"✅ 合同参数提取完成，共 {param_count} 个参数项", "result")
    _rp(session_id, _SKILL, "end", "contract_template_params",
        input_data=_input, output_data=params_data,
        exec_id=exec_id, run_id=run_id)

    print(json.dumps({"ok": True, "param_count": param_count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
