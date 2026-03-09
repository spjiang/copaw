#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upload free-draft docx to smart-create1 and push result events."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

_CUR_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _CUR_DIR.parent.parent
sys.path.insert(0, str(_CUR_DIR))
sys.path.insert(0, str(_SKILLS_DIR))

from event_meta import SKILL_LABEL, SKILL_NAME, get_event_name
from push import push
from redis_push import push_end, push_error, push_running, push_start
from runtime_context import resolve_session_id, resolve_user_id
from smart_create_utils import get_file_url_from_smart_create_response

FREE_DRAFT_SAVE_API = os.environ.get(
    "FREE_DRAFT_SAVE_API",
    "http://10.17.96.197:8088/api/contracts/smart-create1",
)


def _load_corrections(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("corrections_json must be a JSON object")
    return value


def main() -> None:
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "error": "usage: free_draft_save.py <docx_file> [exec_id] [session_id] "
                    "[user_id] [draft_entry_reason] [corrections_json] [use_ai]"
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    if requests is None:
        print(json.dumps({"error": "requests library not installed"}, ensure_ascii=False))
        sys.exit(1)

    start_time = time.time()
    docx_file = Path(sys.argv[1]).expanduser().resolve()
    exec_id = sys.argv[2] if len(sys.argv) > 2 else ""
    session_id = resolve_session_id(sys.argv[3] if len(sys.argv) > 3 else "")
    user_id = resolve_user_id(sys.argv[4] if len(sys.argv) > 4 else "")
    draft_entry_reason = (sys.argv[5] if len(sys.argv) > 5 else "").strip() or "manual_or_unknown"
    corrections_json = sys.argv[6] if len(sys.argv) > 6 else ""
    use_ai = (sys.argv[7] if len(sys.argv) > 7 else "false").strip().lower() or "false"
    run_id = str(uuid.uuid4())

    input_data = {
        "docx_file": str(docx_file),
        "draft_entry_reason": draft_entry_reason,
        "use_ai": use_ai,
    }

    push_start(
        session_id=session_id,
        user_id=user_id,
        skill_name=SKILL_NAME,
        skill_label=SKILL_LABEL,
        event_name="开始保存自由起草合同",
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
        render_type="llm_draft_started",
    )

    try:
        if not docx_file.exists():
            raise RuntimeError(f"docx file not found: {docx_file}")
        if docx_file.suffix.lower() != ".docx":
            raise RuntimeError("free draft save only accepts a .docx file")
        corrections = _load_corrections(corrections_json)

        push(
            session_id,
            user_id,
            "📝 正在保存自由起草合同...",
            msg_type="progress",
        )

        with docx_file.open("rb") as fp:
            response = requests.post(
                FREE_DRAFT_SAVE_API,
                data={
                    "user_id": user_id,
                    "use_ai": "true" if use_ai == "true" else "false",
                    "corrections": json.dumps(corrections, ensure_ascii=False),
                },
                files={
                    "file": (
                        docx_file.name,
                        fp,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
                timeout=120,
            )

        if not response.ok:
            raise RuntimeError(
                f"free draft save api http {response.status_code}: {(response.text or '').strip()[:500]}"
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(
                f"free draft save api returned non-json response: {response.text[:500]}"
            ) from exc

        result_url = get_file_url_from_smart_create_response(payload)
        if not result_url:
            raise RuntimeError("free draft save api 返回格式异常，无法解析文件下载地址")

        runtime_ms = int((time.time() - start_time) * 1000)
        result = {
            "url": result_url,
            "result_url": result_url,
            "render_result_url": result_url,
            "file_url": result_url,
            "filename": docx_file.name,
            "render_mode": "final",
            "generation_mode": "llm_draft",
            "result_type": "docx",
            "draft_entry_reason": draft_entry_reason,
            "corrections": corrections,
            "source_api": FREE_DRAFT_SAVE_API,
        }

        push_end(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name=get_event_name("llm_draft_finished"),
            input_data=input_data,
            output_data=result,
            render_type="llm_draft_finished",
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(session_id, user_id, f"✅ 自由起草合同已保存：{docx_file.name}", msg_type="result")
        print(json.dumps({"success": True, **result}, ensure_ascii=False))
    except Exception as exc:
        runtime_ms = int((time.time() - start_time) * 1000)
        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name=get_event_name("llm_draft_failed"),
            render_type="llm_draft_failed",
            input_data=input_data,
            output_data={"error_message": str(exc)},
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push_error(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name="自由起草模板保存失败",
            input_data=input_data,
            error_msg=str(exc),
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(session_id, user_id, f"❌ 自由起草模板保存失败：{exc}", msg_type="error")
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
