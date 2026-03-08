#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable generic event pusher used by contract_draft SKILL.md."""

import json
import os
import sys
import uuid
from pathlib import Path

_CUR_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_CUR_DIR))

from event_meta import SKILL_LABEL, SKILL_NAME, get_event_name
from push import push
from redis_push import push_end, push_error, push_running, push_start


def main():
    if len(sys.argv) < 4:
        print(
            json.dumps(
                {
                    "error": "usage: push_event.py <skill_name> <stage> <exec_id> "
                    "[render_type] [message] [input_json] [output_json] "
                    "[session_id] [user_id] [run_id] [runtime_ms] "
                    "[skill_label] [event_name]"
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
    skill_label = (
        (sys.argv[12] if len(sys.argv) > 12 else "")
        or os.environ.get("COPAW_SKILL_LABEL")
        or (SKILL_LABEL if skill_name == SKILL_NAME else skill_name)
    )
    event_name = (sys.argv[13] if len(sys.argv) > 13 else "") or get_event_name(
        render_type=render_type,
        stage=stage,
        fallback=message,
    )

    def _loads(raw: str):
        try:
            return json.loads(raw) if raw and raw.strip() else {}
        except Exception:
            return {}

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

    if message:
        msg_type = "error" if stage == "error" else ("result" if stage == "end" else "progress")
        push(session_id, user_id, message, msg_type=msg_type)

    if stage == "start":
        push_start(
            session_id=session_id,
            user_id=user_id,
            skill_name=skill_name,
            skill_label=skill_label,
            event_name=event_name,
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
            skill_label=skill_label,
            event_name=event_name,
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
            skill_label=skill_label,
            event_name=event_name,
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
            skill_label=skill_label,
            event_name=event_name,
            input_data=input_data,
            error_msg=output_data.get("error") or message or "unknown error",
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
            render_type=render_type,
        )

    print(
        json.dumps(
            {
                "ok": True,
                "skill_name": skill_name,
                "skill_label": skill_label,
                "stage": stage,
                "render_type": render_type,
                "event_name": event_name,
                "run_id": run_id,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
