#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable generic event pusher used by contract SKILL.md files.

Usage:
    python push_event.py <skill_name> <stage> <exec_id> [render_type]
                         [message] [input_json] [output_json]
                         [session_id] [user_id] [run_id] [runtime_ms]

Backward compatibility:
    If only one JSON argument is passed, it is treated as `output_json`.
"""
import json
import os
import sys
import uuid

_SHARED_DIR = __import__("pathlib").Path(__file__).parent
sys.path.insert(0, str(_SHARED_DIR.parent))

from shared.redis_push import push_end, push_error, push_running, push_start
from shared.push import push


def main():
    if len(sys.argv) < 4:
        print(
            json.dumps(
                {
                    "error": "usage: push_event.py <skill_name> <stage> <exec_id> "
                    "[render_type] [message] [input_json] [output_json] "
                    "[session_id] [user_id] [run_id] [runtime_ms]"
                }
            )
        )
        sys.exit(1)

    skill_name = sys.argv[1]
    stage = sys.argv[2]
    exec_id = sys.argv[3]
    render_type = sys.argv[4] if len(sys.argv) > 4 else (
        "agent_start" if stage == "start" else "agent_end" if stage == "end" else "error"
    )
    message = sys.argv[5] if len(sys.argv) > 5 else ""

    input_raw = sys.argv[6] if len(sys.argv) > 6 else "{}"
    output_raw = sys.argv[7] if len(sys.argv) > 7 else "{}"

    session_id = (
        os.environ.get("COPAW_SESSION_ID")
        or (sys.argv[8] if len(sys.argv) > 8 else "")
        or "unknown_session"
    )
    user_id = (
        (sys.argv[9] if len(sys.argv) > 9 else "")
        or os.environ.get("COPAW_USER_ID")
        or "unknown_user"
    )
    run_id = (sys.argv[10] if len(sys.argv) > 10 else "") or str(uuid.uuid4())
    runtime_ms = int(sys.argv[11]) if len(sys.argv) > 11 and str(sys.argv[11]).strip() else 0

    def _loads(raw: str):
        try:
            return json.loads(raw) if raw and raw.strip() else {}
        except Exception:
            return {}

    # 兼容老接口：只传了一个 extra_json，放到 output_json
    if len(sys.argv) == 7:
        input_data = {"exec_id": exec_id}
        output_data = _loads(input_raw)
    else:
        input_data = _loads(input_raw)
        output_data = _loads(output_raw)

    if not isinstance(input_data, dict):
        input_data = {"value": input_data}
    if not isinstance(output_data, dict):
        output_data = {"value": output_data}

    input_data.setdefault("exec_id", exec_id)

    # 弹窗通知（有 message 才推）
    if message:
        msg_type = "error" if stage == "error" else ("result" if stage == "end" else "progress")
        push(session_id, user_id, message, msg_type=msg_type)

    if stage == "start":
        push_start(
            session_id=session_id,
            user_id=user_id,
            skill_name=skill_name,
            input_data=input_data,
            exec_id=exec_id,
            run_id=run_id,
            render_type=render_type,
        )
    elif stage == "running":
        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=skill_name,
            render_type=render_type,
            input_data=input_data,
            output_data=output_data,
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
    elif stage == "end":
        push_end(
            session_id=session_id,
            user_id=user_id,
            skill_name=skill_name,
            input_data=input_data,
            output_data=output_data,
            render_type=render_type,
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
    else:
        push_error(
            session_id=session_id,
            user_id=user_id,
            skill_name=skill_name,
            input_data=input_data,
            error_msg=output_data.get("error") or message or "unknown error",
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )

    print(
        json.dumps(
            {
                "ok": True,
                "skill_name": skill_name,
                "stage": stage,
                "render_type": render_type,
                "run_id": run_id,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
