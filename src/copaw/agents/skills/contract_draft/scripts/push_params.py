#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Push raw contract template params schema for contract_draft."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
_CUR_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _CUR_DIR.parent.parent
sys.path.insert(0, str(_CUR_DIR))
sys.path.insert(0, str(_SKILLS_DIR))

from event_meta import SKILL_LABEL, SKILL_NAME, get_event_name
from push import push
from redis_push import push_end, push_error, push_running, push_start

def _clean_json_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("```")).strip()
    data = json.loads(raw)
    if isinstance(data, dict):
        return data
    raise ValueError("params json must be an object")


def _extract_payload(data: dict) -> dict:
    template_id = str(data.get("template_id") or "")
    template_url = str(data.get("template_url") or "")
    schema = data.get("param_schema_json")
    if schema is None:
        schema = data
    return {
        "template_id": template_id,
        "template_url": template_url,
        "param_schema_json": schema,
    }


def _collect_missing_fields(schema) -> list[str]:
    missing: list[str] = []
    if not isinstance(schema, dict):
        return missing

    for key, value in schema.items():
        if isinstance(value, dict) and "value" in value:
            field_value = value.get("value")
            if field_value in (None, ""):
                missing.append(str(key))
            elif isinstance(field_value, list):
                for item in field_value:
                    if isinstance(item, dict):
                        missing.extend(_collect_missing_fields(item))
        elif isinstance(value, dict):
            missing.extend(_collect_missing_fields(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    missing.extend(_collect_missing_fields(item))

    return missing


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: push_params.py <params_json_file> [exec_id] [session_id] [user_id]"}))
        sys.exit(1)

    start_time = time.time()
    params_file = Path(sys.argv[1])
    exec_id = sys.argv[2] if len(sys.argv) > 2 else ""
    session_id = os.environ.get("COPAW_SESSION_ID") or (sys.argv[3] if len(sys.argv) > 3 else "") or "unknown_session"
    user_id = os.environ.get("COPAW_USER_ID") or (sys.argv[4] if len(sys.argv) > 4 else "") or "unknown_user"
    run_id = str(uuid.uuid4())
    input_data = {"params_file": str(params_file), "exec_id": exec_id}

    push_start(
        session_id=session_id,
        user_id=user_id,
        skill_name=SKILL_NAME,
        skill_label=SKILL_LABEL,
        event_name=get_event_name("template_params_started"),
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
        render_type="template_params_started",
    )

    if not params_file.exists():
        error_message = f"params file not found: {params_file}"
        push_error(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name="模板参数文件不存在",
            input_data=input_data,
            error_msg=error_message,
            exec_id=exec_id,
            run_id=run_id,
        )
        print(json.dumps({"error": error_message}, ensure_ascii=False))
        sys.exit(1)

    try:
        data = _clean_json_file(params_file)
        payload = _extract_payload(data)
        missing_fields = _collect_missing_fields(payload.get("param_schema_json"))
        runtime_ms = int((time.time() - start_time) * 1000)

        push_end(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name=get_event_name("template_params_finished"),
            input_data=input_data,
            output_data=payload,
            render_type="template_params_finished",
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name=get_event_name(
                "template_params_required" if missing_fields else "template_params_completed"
            ),
            render_type="template_params_required" if missing_fields else "template_params_completed",
            input_data=input_data,
            output_data=payload,
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(session_id, user_id, "✅ 模板参数结构已读取", msg_type="result")
        print(
            json.dumps(
                {
                    "ok": True,
                    "params_file": str(params_file),
                    "template_id": payload.get("template_id", ""),
                    "template_url": payload.get("template_url", ""),
                    "param_schema_json": payload.get("param_schema_json"),
                    "missing_fields": missing_fields,
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        runtime_ms = int((time.time() - start_time) * 1000)
        push(session_id, user_id, f"❌ 合同参数处理失败：{exc}", msg_type="error")
        push_error(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name="模板参数处理失败",
            input_data=input_data,
            error_msg=str(exc),
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
