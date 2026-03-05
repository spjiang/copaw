#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generic Redis Stream push helper for LLM-orchestrated skills.

Called via execute_shell_command in SKILL.md files to push start/end/error
events without needing a dedicated Python script per skill.

Usage:
    python push_event.py <skill_name> <stage> <exec_id> [render_type] [message] [extra_json] [session_id] [user_id]

    skill_name  : e.g. "contract_draft", "contract_draft_llm"
    stage       : "start" | "end" | "error"
    exec_id     : current execution ID
    render_type : optional, e.g. "progress" | "contract_draft_task_end"  (default: "progress")
    message     : optional human-readable message for the bubble notification
    extra_json  : optional JSON string merged into output_data
    session_id  : optional, explicit session_id (preferred over env)
    user_id     : optional, explicit user_id (preferred over env)

Environment variables (loaded from parent process / .env):
    COPAW_SESSION_ID, COPAW_USER_ID, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD

Output (stdout): JSON  { "ok": true } | { "error": "..." }
"""
import json
import os
import sys
import uuid

_SHARED_DIR = __import__("pathlib").Path(__file__).parent
sys.path.insert(0, str(_SHARED_DIR.parent))

from shared.redis_push import redis_push
from shared.push import push


def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error":
              "usage: push_event.py <skill_name> <stage> <exec_id> "
              "[render_type] [message] [extra_json] [session_id] [user_id]"}))
        sys.exit(1)

    skill_name  = sys.argv[1]
    stage       = sys.argv[2]                          # start | end | error
    exec_id     = sys.argv[3]
    render_type = sys.argv[4] if len(sys.argv) > 4 else "progress"
    message     = sys.argv[5] if len(sys.argv) > 5 else ""
    extra_raw   = sys.argv[6] if len(sys.argv) > 6 else "{}"

    session_id = (
        os.environ.get("COPAW_SESSION_ID")
        or (sys.argv[7] if len(sys.argv) > 7 else "")
        or "unknown_session"
    )
    user_id = (
        (sys.argv[8] if len(sys.argv) > 8 else "")
        or os.environ.get("COPAW_USER_ID")
        or "unknown_user"
    )
    run_id     = str(uuid.uuid4())

    try:
        extra = json.loads(extra_raw) if extra_raw.strip() else {}
    except Exception:
        extra = {}

    # 弹窗通知（有 message 才推）
    if message:
        msg_type = "error" if stage == "error" else ("result" if stage == "end" else "progress")
        push(session_id, user_id, message, msg_type=msg_type)

    # Redis Stream push
    redis_push(
        session_id=session_id,
        skill_name=skill_name,
        stage=stage,
        render_type=render_type,
        input_data={"exec_id": exec_id},
        output_data=extra,
        exec_id=exec_id,
        run_id=run_id,
    )

    print(json.dumps({"ok": True, "skill_name": skill_name, "stage": stage},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
