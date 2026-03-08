#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a contract template through the external render API.

Usage:
    python render_template.py <template_url> <params_json_file> [exec_id] [session_id] [user_id]
"""

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
sys.path.insert(0, str(_SKILLS_DIR))

from shared.push import push
from shared.redis_push import push_end, push_error, push_running, push_start

RENDER_API = os.environ.get("TEMPLATE_RENDER_API", "http://10.17.55.121:8012/render")
SKILL_NAME = "contract_template_params"


def _is_schema_dict_format(obj: Any) -> bool:
    """Detect {key: {desc, value}} format (data from DB)."""
    if not isinstance(obj, dict):
        return False
    if "params" in obj or "template_id" in obj or "template_url" in obj:
        return False
    return any(isinstance(v, dict) and ("desc" in v or "value" in v) for v in obj.values())


def _schema_dict_to_flat(schema: dict) -> dict:
    """Convert {key: {desc, value}} → {key: value} flat dict for render API.

    Only includes keys where value is non-empty.
    List values (e.g. product_list) are kept as-is.
    """
    flat: dict = {}
    for key, meta in schema.items():
        if not isinstance(meta, dict):
            continue
        value = meta.get("value")
        if isinstance(value, list):
            # Keep list values (e.g. product_list table rows) as-is
            if value:
                flat[key] = value
        elif value not in (None, ""):
            flat[key] = value
    return flat


def _load_params_text(params_file: Path) -> tuple[str, dict]:
    """Load and parse params file, return (text_for_render_api, original_data).

    Supports three input formats:
      1. {key: {desc, value}}            — DB param_schema_json format (primary)
      2. {template_id, template_url,
          param_schema_json: {params:[]} } — normalized array format (legacy)
      3. {key: value}                    — already flat (pass-through)
    """
    raw = params_file.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("```")).strip()
    data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(f"params file must contain a JSON object, got: {type(data)}")

    # ── Format 1: {key: {desc, value}} ─────────────────────────────────────
    if _is_schema_dict_format(data):
        flat = _schema_dict_to_flat(data)
        return json.dumps(flat, ensure_ascii=False), data

    # ── Format 2: nested schema with param_schema_json or params list ──────
    schema = data.get("param_schema_json")
    if _is_schema_dict_format(schema):
        flat = _schema_dict_to_flat(schema)
        return json.dumps(flat, ensure_ascii=False), data

    if isinstance(schema, dict) and isinstance(schema.get("params"), list):
        flat = {}
        for item in schema["params"]:
            if not isinstance(item, dict):
                continue
            key = item.get("field_name") or item.get("label")
            value = item.get("value")
            if key and value not in (None, ""):
                flat[str(key)] = value
        return json.dumps(flat, ensure_ascii=False), data

    if isinstance(data.get("params"), list):
        flat = {}
        for item in data["params"]:
            if not isinstance(item, dict):
                continue
            key = item.get("field_name") or item.get("label")
            value = item.get("value")
            if key and value not in (None, ""):
                flat[str(key)] = value
        return json.dumps(flat, ensure_ascii=False), data

    # ── Format 3: already flat {key: value} ────────────────────────────────
    return json.dumps(data, ensure_ascii=False), data


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: render_template.py <template_url> <params_json_file> [exec_id] [session_id] [user_id]"}))
        sys.exit(1)

    if requests is None:
        print(json.dumps({"error": "requests library not installed"}, ensure_ascii=False))
        sys.exit(1)

    start_time = time.time()
    template_url = sys.argv[1]
    params_file = Path(sys.argv[2])
    exec_id = sys.argv[3] if len(sys.argv) > 3 else ""
    session_id = os.environ.get("COPAW_SESSION_ID") or (sys.argv[4] if len(sys.argv) > 4 else "") or "unknown_session"
    user_id = os.environ.get("COPAW_USER_ID") or (sys.argv[5] if len(sys.argv) > 5 else "") or "unknown_user"
    run_id = str(uuid.uuid4())
    input_data = {"template_url": template_url, "params_file": str(params_file)}

    push(session_id, user_id, "🧩 正在调用模板渲染接口...", msg_type="progress")
    push_start(
        session_id=session_id,
        user_id=user_id,
        skill_name=SKILL_NAME,
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
    )

    try:
        if not template_url.strip():
            raise RuntimeError("template_url is empty")
        if not params_file.exists():
            raise RuntimeError(f"params file not found: {params_file}")

        params_text, params_json = _load_params_text(params_file)
        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            render_type="template_render_started",
            input_data=input_data,
            output_data={"template_url": template_url},
            exec_id=exec_id,
            run_id=run_id,
        )

        response = requests.post(
            RENDER_API,
            json={"template_url": template_url, "text": params_text},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(payload.get("message") or "render api returned success=false")

        runtime_ms = int((time.time() - start_time) * 1000)
        result = {
            "template_url": template_url,
            "render_result_url": payload.get("url", ""),
            "message": payload.get("message", "ok"),
            "params_json": params_json,
        }
        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            render_type="template_render_success",
            input_data=input_data,
            output_data=result,
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push_end(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            input_data=input_data,
            output_data=result,
            render_type="agent_end",
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(session_id, user_id, "✅ 模板渲染成功", msg_type="result")
        print(json.dumps({"success": True, **result}, ensure_ascii=False))
    except Exception as exc:
        runtime_ms = int((time.time() - start_time) * 1000)
        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            render_type="template_render_failed",
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
            input_data=input_data,
            error_msg=str(exc),
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(session_id, user_id, f"❌ 模板渲染失败：{exc}", msg_type="error")
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
