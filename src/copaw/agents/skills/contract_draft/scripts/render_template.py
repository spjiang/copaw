#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a contract template through the external render API for contract_draft."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
from redis_push import push_end, push_error, push_start
from runtime_context import resolve_session_id, resolve_user_id
from smart_create_utils import get_file_url_from_smart_create_response

RENDER_API = os.environ.get("TEMPLATE_RENDER_API", "http://10.17.55.121:8012/render")
FREE_DRAFT_SAVE_API = os.environ.get(
    "FREE_DRAFT_SAVE_API",
    "http://10.17.96.197:8088/api/contracts/smart-create",
)


def _looks_like_docx_url(value: str) -> bool:
    path = urlparse(value).path.lower()
    return path.endswith(".docx")


def _upload_to_contract_system(docx_path: Path, user_id: str) -> str | None:
    """Upload docx to contract management system via smart-create API. Returns url or None."""
    with docx_path.open("rb") as fp:
        response = requests.post(
            FREE_DRAFT_SAVE_API,
            data={
                "user_id": user_id,
                "use_ai": "true",
                "corrections": "{}",
            },
            files={
                "file": (
                    docx_path.name,
                    fp,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            timeout=120,
        )
    if not response.ok:
        return None
    try:
        payload = response.json()
        return get_file_url_from_smart_create_response(payload)
    except Exception:
        return None


def _load_params_text(params_file: Path) -> tuple[str, dict[str, Any]]:
    raw = params_file.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("```")).strip()
    data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(f"params file must contain a JSON object, got: {type(data)}")

    schema = data.get("param_schema_json")
    render_context = schema if isinstance(schema, dict) else data
    if not isinstance(render_context, dict):
        raise ValueError("render context must be a JSON object")
    return json.dumps(render_context, ensure_ascii=False), render_context


def main():
    if len(sys.argv) < 3:
        print(
            json.dumps(
                {
                    "error": "usage: render_template.py <template_url> <params_json_file> "
                    "[exec_id] [session_id] [user_id]"
                }
            )
        )
        sys.exit(1)

    if requests is None:
        print(json.dumps({"error": "requests library not installed"}, ensure_ascii=False))
        sys.exit(1)

    start_time = time.time()
    template_url = sys.argv[1]
    params_file = Path(sys.argv[2])
    exec_id = sys.argv[3] if len(sys.argv) > 3 else ""
    session_id = resolve_session_id(sys.argv[4] if len(sys.argv) > 4 else "")
    user_id = resolve_user_id(sys.argv[5] if len(sys.argv) > 5 else "")
    run_id = str(uuid.uuid4())
    started_render_type = "template_render_started"
    finished_render_type = "template_render_finished"
    failed_render_type = "template_render_failed"
    input_data = {
        "template_url": template_url,
        "params_file": str(params_file),
        "render_mode": "final",
    }

    push_start(
        session_id=session_id,
        user_id=user_id,
        skill_name=SKILL_NAME,
        skill_label=SKILL_LABEL,
        event_name=get_event_name(started_render_type),
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
        render_type=started_render_type,
    )

    try:
        if not template_url.strip():
            raise RuntimeError("template_url is empty")
        if not _looks_like_docx_url(template_url):
            raise RuntimeError("template_url must be a .docx download url")
        if not params_file.exists():
            raise RuntimeError(f"params file not found: {params_file}")

        params_text, params_json = _load_params_text(params_file)
        response = requests.post(
            RENDER_API,
            json={"template_url": template_url, "text": params_text},
            timeout=120,
        )
        if not response.ok:
            raise RuntimeError(
                f"render api http {response.status_code}: {(response.text or '').strip()[:500]}"
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(f"render api returned non-json response: {response.text[:500]}") from exc
        if not payload.get("success"):
            raise RuntimeError(payload.get("message") or "render api returned success=false")

        render_url = payload.get("url", "")
        result_url = render_url
        cms_url = None
        try:
            resp = requests.get(render_url, timeout=60)
            if resp.ok:
                with tempfile.NamedTemporaryFile(
                    suffix=".docx", delete=False
                ) as tmp:
                    tmp.write(resp.content)
                    tmp_path = Path(tmp.name)
                try:
                    # 上传至合同管理系统，用于合同管理
                    cms_url = _upload_to_contract_system(tmp_path, user_id)
                    if cms_url:
                        result_url = cms_url
                finally:
                    tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        runtime_ms = int((time.time() - start_time) * 1000)
        result = {
            "template_url": template_url,
            "render_result_url": render_url,
            "result_url": result_url,
            "file_url": result_url,
            "message": payload.get("message", "ok"),
            "params_json": params_json,
            "render_mode": "final",
            "generation_mode": "template_render",
            "result_type": "docx",
        }
        if cms_url:
            result["cms_url"] = cms_url
        push_end(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name=get_event_name(finished_render_type),
            input_data=input_data,
            output_data=result,
            render_type=finished_render_type,
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(
            session_id,
            user_id,
            "✅ 合同生成成功",
            msg_type="result",
        )
        print(json.dumps({"success": True, **result}, ensure_ascii=False))
    except Exception as exc:
        runtime_ms = int((time.time() - start_time) * 1000)
        push_error(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name=get_event_name(failed_render_type),
            input_data=input_data,
            error_msg=str(exc),
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
            render_type=failed_render_type,
        )
        push(
            session_id,
            user_id,
            f"❌ 模板渲染失败：{exc}",
            msg_type="error",
        )
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
