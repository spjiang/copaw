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
from runtime_context import resolve_session_id, resolve_user_id

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


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _pick_field_name(node: dict, fallback: str = "") -> str:
    for key in ("field_name", "name", "label", "param_id", "key"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _append_missing(missing: list[str], field_name: str) -> None:
    name = (field_name or "").strip()
    if name and name not in missing:
        missing.append(name)


def _pick_desc(node: dict) -> str:
    for key in ("desc", "description", "remark", "help", "placeholder"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _format_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _collect_table_rows(schema) -> list[dict]:
    rows: list[dict] = []

    def _append_row(path: str, node: dict, value, group_name: str = "") -> None:
        field_name = _pick_field_name(node, path.split(".")[-1] if path else "")
        required = node.get("required", True) is not False
        status = "missing" if required and _is_blank(value) else "filled"
        rows.append(
            {
                "path": path or field_name,
                "field_name": field_name or path,
                "group": group_name or "",
                "desc": _pick_desc(node),
                "required": required,
                "value": value,
                "display_value": _format_value(value),
                "status": status,
            }
        )

    def _walk(node, current_path: str = "", group_name: str = "") -> None:
        if isinstance(node, dict):
            if isinstance(node.get("params"), list):
                container_name = _pick_field_name(node, group_name or current_path)
                for item in node["params"]:
                    if isinstance(item, dict):
                        item_name = _pick_field_name(item, "")
                        next_path = (
                            f"{current_path}.{item_name}" if current_path and item_name else item_name or current_path
                        )
                        _walk(item, next_path, container_name)
                return

            if "value" in node:
                field_name = _pick_field_name(node, current_path.split(".")[-1] if current_path else "")
                path = current_path or field_name
                value = node.get("value")
                if isinstance(value, dict):
                    for child_key, child_value in value.items():
                        next_path = f"{path}.{child_key}" if path else str(child_key)
                        _walk(child_value, next_path, group_name or field_name)
                    return
                if isinstance(value, list):
                    if not value:
                        _append_row(path, node, value, group_name)
                        return
                    scalar_items = [item for item in value if not isinstance(item, (dict, list))]
                    if scalar_items:
                        _append_row(path, node, value, group_name)
                    for index, item in enumerate(value):
                        if isinstance(item, (dict, list)):
                            next_path = f"{path}[{index}]" if path else f"[{index}]"
                            _walk(item, next_path, group_name or field_name)
                    return
                _append_row(path, node, value, group_name)
                return

            for key, value in node.items():
                if key == "params":
                    continue
                next_path = f"{current_path}.{key}" if current_path else str(key)
                _walk(value, next_path, group_name)
            return

        if isinstance(node, list):
            for index, item in enumerate(node):
                next_path = f"{current_path}[{index}]" if current_path else f"[{index}]"
                _walk(item, next_path, group_name)

    _walk(schema)
    return rows


def _build_param_table(field_rows: list[dict], missing_fields: list[str]) -> dict:
    filled_count = sum(1 for row in field_rows if row.get("status") == "filled")
    missing_count = sum(1 for row in field_rows if row.get("status") == "missing")
    rows = []
    for row in field_rows:
        desc = (row.get("desc") or "").strip()
        fn = (row.get("field_name") or row.get("path") or "").strip()
        param_display = desc if desc else (fn or "-")
        rows.append({**row, "param_display": param_display})
    return {
        "columns": [
            {"key": "param_display", "title": "参数"},
            {"key": "display_value", "title": "当前值"},
            {"key": "status", "title": "状态"},
        ],
        "rows": rows,
        "summary": {
            "total_fields": len(field_rows),
            "filled_fields": filled_count,
            "missing_fields_count": missing_count,
            "missing_fields": missing_fields,
        },
    }


def _markdown_cell(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text.replace("|", "\\|").replace("\n", "<br/>")


def _row_status_label(row: dict) -> str:
    if row.get("status") == "filled":
        return "已填写"
    if row.get("required", True):
        return "待填写"
    return "可选"


def _build_param_table_markdown(field_rows: list[dict], summary: dict) -> str:
    total_fields = int(summary.get("total_fields") or len(field_rows))
    filled_fields = int(summary.get("filled_fields") or 0)
    missing_count = int(summary.get("missing_fields_count") or 0)
    missing_fields = summary.get("missing_fields") or []

    lines = [
        f"已填写 **{filled_fields}** / **{total_fields}** 项，待补 **{missing_count}** 项。",
        "",
        "| 参数 | 当前值 | 状态 |",
        "| --- | --- | --- |",
    ]

    for row in field_rows:
        desc = _markdown_cell(row.get("desc") or "") or ""
        field_name = _markdown_cell(row.get("field_name") or row.get("path") or "") or ""
        # 优先使用中文 desc，避免向用户暴露英文参数 key
        display_name = desc if desc else (field_name or "-")
        display_value = _markdown_cell(row.get("display_value") or "未填写") or "未填写"
        status = _row_status_label(row)
        lines.append(f"| {display_name} | {display_value} | {status} |")

    if missing_fields:
        path_to_desc = {}
        for row in field_rows:
            d = (row.get("desc") or "").strip()
            if not d:
                continue
            for k in (row.get("path"), row.get("field_name")):
                if k:
                    path_to_desc[k] = d
            p = row.get("path") or ""
            if "." in p:
                path_to_desc[p.split(".")[-1]] = d
        display_missing = []
        for m in missing_fields:
            m = str(m).strip()
            if not m:
                continue
            display_missing.append(path_to_desc.get(m) or path_to_desc.get(m.split(".")[-1] if "." in m else m) or m)
        if display_missing:
            lines.extend(["", "当前仍缺少：", "、".join(display_missing)])

    return "\n".join(lines)


def _collect_missing_fields(schema, prefix: str = "") -> list[str]:
    missing: list[str] = []

    def _walk(node, current_prefix: str = "") -> None:
        if isinstance(node, dict):
            if isinstance(node.get("params"), list):
                for item in node["params"]:
                    item_name = current_prefix
                    if isinstance(item, dict):
                        item_name = _pick_field_name(item, current_prefix)
                    _walk(item, item_name)
                return

            if "value" in node:
                field_name = _pick_field_name(node, current_prefix)
                field_value = node.get("value")
                required = node.get("required", True)

                if isinstance(field_value, list):
                    if _is_blank(field_value) and required is not False:
                        _append_missing(missing, field_name)
                    for index, item in enumerate(field_value):
                        nested_name = f"{field_name}[{index}]" if field_name else f"[{index}]"
                        _walk(item, nested_name)
                    return

                if isinstance(field_value, dict):
                    if not field_value and required is not False:
                        _append_missing(missing, field_name)
                    _walk(field_value, field_name)
                    return

                if _is_blank(field_value) and required is not False:
                    _append_missing(missing, field_name)
                return

            if "required" in node and "value" not in node:
                if node.get("required", True) is not False:
                    _append_missing(missing, _pick_field_name(node, current_prefix))

            for key, value in node.items():
                if key == "params":
                    continue
                next_prefix = current_prefix
                if isinstance(key, str):
                    next_prefix = f"{current_prefix}.{key}" if current_prefix else key
                _walk(value, next_prefix)
            return

        if isinstance(node, list):
            for index, item in enumerate(node):
                nested_name = f"{current_prefix}[{index}]" if current_prefix else f"[{index}]"
                _walk(item, nested_name)

    _walk(schema, prefix)
    return missing


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: push_params.py <params_json_file> [exec_id] [session_id] [user_id]"}))
        sys.exit(1)

    start_time = time.time()
    params_file = Path(sys.argv[1])
    exec_id = sys.argv[2] if len(sys.argv) > 2 else ""
    session_id = resolve_session_id(sys.argv[3] if len(sys.argv) > 3 else "")
    user_id = resolve_user_id(sys.argv[4] if len(sys.argv) > 4 else "")
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
        field_rows = _collect_table_rows(payload.get("param_schema_json"))
        payload["missing_fields"] = missing_fields
        payload["param_table"] = _build_param_table(field_rows, missing_fields)
        payload["param_table_markdown"] = _build_param_table_markdown(
            field_rows,
            payload["param_table"].get("summary", {}),
        )
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
                    "param_table": payload.get("param_table"),
                    "param_table_markdown": payload.get("param_table_markdown", ""),
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
