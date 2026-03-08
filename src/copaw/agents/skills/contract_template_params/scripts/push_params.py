#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize and push contract template params schema/result.

Usage:
    python push_params.py <params_json_file> [exec_id] [session_id] [user_id]
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_CUR_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _CUR_DIR.parent.parent
sys.path.insert(0, str(_SKILLS_DIR))

from shared.push import push
from shared.redis_push import push_end, push_error, push_running, push_start

SKILL_NAME = "contract_template_params"


def _clean_json_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("```")).strip()
    data = json.loads(raw)
    if isinstance(data, dict):
        return data
    raise ValueError("params json must be an object")


def _is_schema_dict_format(schema: Any) -> bool:
    """Detect {key: {desc, value}} format (from DB).

    Example:
        {
            "company_a": {"desc": "甲方公司名称", "value": ""},
            "contract_effect_year": {"desc": "合同生效年份", "value": "2025"}
        }
    """
    if not isinstance(schema, dict):
        return False
    if "params" in schema or "template_id" in schema:
        return False
    return any(
        isinstance(v, dict) and ("desc" in v or "value" in v)
        for v in schema.values()
    )


def _parse_schema_dict(schema: dict) -> list[dict]:
    """Convert {key: {desc, value}} → normalized params list."""
    result = []
    for idx, (key, meta) in enumerate(schema.items(), start=1):
        if not isinstance(meta, dict):
            continue
        desc = str(meta.get("desc") or key)
        raw_value = meta.get("value")
        # Handle nested list values (e.g. product_list table rows)
        if isinstance(raw_value, list):
            value = json.dumps(raw_value, ensure_ascii=False) if raw_value else None
            field_type = "table"
        else:
            value = raw_value if raw_value not in (None, "") else None
            field_type = "text"
        result.append({
            "param_id": f"p{idx:03d}",
            "label": desc,
            "field_name": key,
            "value": value,
            "required": True,
            "type": field_type,
            "placeholder": f"请填写{desc}",
            "options": None,
            "group": _infer_group(key),
        })
    return result


def _infer_group(key: str) -> str:
    """Infer display group from field key name."""
    mapping = {
        ("contract_effect", "contract_amount", "tax_rate", "payment", "installment", "delivery"): "合同条款",
        ("company_a",): "甲方信息",
        ("company_b", "party_b"): "乙方信息",
        ("receiver",): "收货信息",
        ("attachment",): "附件信息",
        ("product_list",): "产品清单",
        ("party_a",): "甲方信息",
    }
    for prefixes, group in mapping.items():
        if any(key.startswith(p) for p in prefixes):
            return group
    return "合同参数"


def _normalize_params(data: dict) -> dict:
    template_id = str(data.get("template_id") or "")
    template_url = str(data.get("template_url") or "")

    # ── 优先提取 param_schema_json ─────────────────────────────────────────
    schema = data.get("param_schema_json") or data.get("params_schema_json")

    # ── 格式1: {key: {desc, value}} 平铺字典（来自数据库）──────────────────
    if _is_schema_dict_format(schema):
        normalized = _parse_schema_dict(schema)
    # ── 格式2: 根对象本身就是平铺字典 ─────────────────────────────────────
    elif _is_schema_dict_format(data):
        normalized = _parse_schema_dict(data)
    # ── 格式3: {"params": [...]} 数组格式（旧版）──────────────────────────
    else:
        if not schema:
            if isinstance(data.get("params"), list):
                schema = {"params": data["params"]}
            else:
                schema = data
        params_list = schema.get("params") if isinstance(schema, dict) else []
        if not isinstance(params_list, list):
            params_list = []
        normalized = []
        for index, item in enumerate(params_list, start=1):
            if not isinstance(item, dict):
                continue
            normalized.append({
                "param_id": str(item.get("param_id") or f"p{index:03d}"),
                "label": item.get("label") or item.get("field_name") or f"字段{index}",
                "field_name": item.get("field_name") or item.get("label") or f"field_{index}",
                "value": item.get("value"),
                "required": bool(item.get("required", True)),
                "type": item.get("type") or "text",
                "placeholder": item.get("placeholder") or "",
                "options": item.get("options"),
                "group": item.get("group") or "合同参数",
            })

    # ── 格式4: filled_params_json 平铺 key-value（已填值回写场景）──────────
    if not normalized and isinstance(data.get("filled_params_json"), dict):
        for index, (key, value) in enumerate(data["filled_params_json"].items(), start=1):
            normalized.append({
                "param_id": f"p{index:03d}",
                "label": key,
                "field_name": key,
                "value": value,
                "required": True,
                "type": "text",
                "placeholder": "",
                "options": None,
                "group": "合同参数",
            })

    return {
        "template_id": template_id,
        "template_url": template_url,
        "param_schema_json": {"params": normalized},
        "params": normalized,
    }


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

    push(session_id, user_id, "🧩 正在整理合同模板参数...", msg_type="progress")
    push_start(
        session_id=session_id,
        user_id=user_id,
        skill_name=SKILL_NAME,
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
    )

    if not params_file.exists():
        error_message = f"params file not found: {params_file}"
        push_error(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            input_data=input_data,
            error_msg=error_message,
            exec_id=exec_id,
            run_id=run_id,
        )
        print(json.dumps({"error": error_message}, ensure_ascii=False))
        sys.exit(1)

    try:
        data = _clean_json_file(params_file)
        normalized = _normalize_params(data)
        params_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

        params = normalized.get("params", [])
        required_count = sum(1 for item in params if item.get("required"))
        filled_count = sum(1 for item in params if item.get("value") not in (None, ""))
        missing_fields = [item.get("field_name") for item in params if item.get("required") and item.get("value") in (None, "")]
        runtime_ms = int((time.time() - start_time) * 1000)

        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            render_type="template_params_required" if missing_fields else "template_params_completed",
            input_data=input_data,
            output_data={
                "template_id": normalized.get("template_id", ""),
                "template_url": normalized.get("template_url", ""),
                "required_param_count": required_count,
                "filled_param_count": filled_count,
                "missing_fields": missing_fields,
                "param_schema_json": normalized.get("param_schema_json", {}),
            },
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push_end(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            input_data=input_data,
            output_data={
                "template_id": normalized.get("template_id", ""),
                "template_url": normalized.get("template_url", ""),
                "param_schema_json": normalized.get("param_schema_json", {}),
                "required_param_count": required_count,
                "filled_param_count": filled_count,
                "missing_fields": missing_fields,
            },
            render_type="agent_end",
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(session_id, user_id, f"✅ 合同参数已整理，共 {len(params)} 项", msg_type="result")
        print(
            json.dumps(
                {
                    "ok": True,
                    "params_file": str(params_file),
                    "param_count": len(params),
                    "required_param_count": required_count,
                    "filled_param_count": filled_count,
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
