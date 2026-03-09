#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for reading and updating contract param schema payloads."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIELD_SOURCE_KEY = "copaw_param_sources"
ATTACHMENT_REFS_KEY = "copaw_attachment_refs"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def clean_json_text(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("```")
        ).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("params json must be an object")
    return data


def load_params_payload(path: Path) -> dict[str, Any]:
    return clean_json_text(path.read_text(encoding="utf-8"))


def dump_params_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_schema(payload: dict[str, Any]) -> Any:
    if isinstance(payload, dict) and "param_schema_json" in payload:
        return payload.get("param_schema_json")
    return payload


def replace_schema(payload: dict[str, Any], schema: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and "param_schema_json" in payload:
        payload["param_schema_json"] = schema
        return payload
    return schema if isinstance(schema, dict) else payload


def ensure_payload_dict(payload: dict[str, Any]) -> dict[str, Any]:
    if "param_schema_json" in payload:
        return payload
    return {
        "param_schema_json": payload,
    }


def pick_field_name(node: dict[str, Any], fallback: str = "") -> str:
    for key in ("field_name", "name", "label", "param_id", "key"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def pick_desc(node: dict[str, Any]) -> str:
    for key in ("desc", "description", "remark", "help", "placeholder"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def tokenize_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for name, index in re.findall(r"([^[.\]]+)|\[(\d+)\]", path):
        if name:
            tokens.append(name)
        elif index:
            tokens.append(int(index))
    return tokens


def locate_field_node(node: Any, tokens: list[str | int]) -> dict[str, Any] | None:
    if not tokens:
        if isinstance(node, dict) and "value" in node:
            return node
        return None

    token = tokens[0]
    rest = tokens[1:]

    if isinstance(token, str):
        if isinstance(node, dict) and isinstance(node.get("params"), list):
            for item in node["params"]:
                if isinstance(item, dict) and pick_field_name(item, "") == token:
                    found = locate_field_node(item, rest)
                    if found is not None:
                        return found

        if isinstance(node, dict) and "value" in node and isinstance(node["value"], dict):
            child = node["value"].get(token)
            if child is not None:
                found = locate_field_node(child, rest)
                if found is not None:
                    return found

        if isinstance(node, dict):
            child = node.get(token)
            if child is not None:
                found = locate_field_node(child, rest)
                if found is not None:
                    return found

    if isinstance(token, int):
        if isinstance(node, dict) and "value" in node and isinstance(node["value"], list):
            if 0 <= token < len(node["value"]):
                found = locate_field_node(node["value"][token], rest)
                if found is not None:
                    return found
        if isinstance(node, list) and 0 <= token < len(node):
            return locate_field_node(node[token], rest)

    return None


def coerce_value(raw_value: str, original_value: Any) -> Any:
    text = raw_value.strip()
    if not text:
        return "" if isinstance(original_value, str) else None

    if isinstance(original_value, bool):
        if text.lower() in {"true", "1", "yes", "y", "是"}:
            return True
        if text.lower() in {"false", "0", "no", "n", "否"}:
            return False

    if isinstance(original_value, int) and not isinstance(original_value, bool):
        try:
            return int(text)
        except ValueError:
            return text

    if isinstance(original_value, float):
        try:
            return float(text)
        except ValueError:
            return text

    if isinstance(original_value, (dict, list)) or text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except Exception:
            return text

    return text


def apply_updates(schema: Any, updates: list[Any]) -> list[str]:
    updated_paths: list[str] = []
    for item in updates:
        path = getattr(item, "path", "")
        value = getattr(item, "value", "")
        tokens = tokenize_path(path)
        if not tokens:
            raise ValueError(f"invalid path: {path}")
        target = locate_field_node(schema, tokens)
        if not isinstance(target, dict) or "value" not in target:
            raise ValueError(f"path not found: {path}")
        target["value"] = coerce_value(value, target.get("value"))
        updated_paths.append(path)
    return updated_paths


def set_field_value(schema: Any, path: str, value: Any) -> bool:
    tokens = tokenize_path(path)
    if not tokens:
        return False
    target = locate_field_node(schema, tokens)
    if not isinstance(target, dict) or "value" not in target:
        return False
    target["value"] = value
    return True


def get_field_sources(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get(FIELD_SOURCE_KEY)
    if isinstance(raw, dict):
        return raw
    data: dict[str, dict[str, Any]] = {}
    payload[FIELD_SOURCE_KEY] = data
    return data


def mark_auto_path(
    payload: dict[str, Any],
    path: str,
    *,
    confidence: float,
    attachments: list[str],
    reason: str,
) -> None:
    sources = get_field_sources(payload)
    sources[path] = {
        "source": "attachment_auto",
        "updated_at": utc_now(),
        "confidence": confidence,
        "attachments": attachments,
        "reason": reason,
    }


def merge_attachment_refs(payload: dict[str, Any], refs: list[str]) -> list[str]:
    current = payload.get(ATTACHMENT_REFS_KEY)
    merged: list[str] = []
    if isinstance(current, list):
        for item in current:
            if isinstance(item, str) and item.strip() and item.strip() not in merged:
                merged.append(item.strip())
    for ref in refs:
        if isinstance(ref, str) and ref.strip() and ref.strip() not in merged:
            merged.append(ref.strip())
    payload[ATTACHMENT_REFS_KEY] = merged
    return merged


def collect_table_rows(schema: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def append_row(path: str, node: dict[str, Any], value: Any, group_name: str = "") -> None:
        field_name = pick_field_name(node, path.split(".")[-1] if path else "")
        required = node.get("required", True) is not False
        rows.append(
            {
                "path": path or field_name,
                "field_name": field_name or path,
                "group": group_name or "",
                "desc": pick_desc(node),
                "required": required,
                "value": value,
                "status": "missing" if required and is_blank(value) else "filled",
            }
        )

    def walk(node: Any, current_path: str = "", group_name: str = "") -> None:
        if isinstance(node, dict):
            if isinstance(node.get("params"), list):
                container_name = pick_field_name(node, group_name or current_path)
                for item in node["params"]:
                    if isinstance(item, dict):
                        item_name = pick_field_name(item, "")
                        next_path = (
                            f"{current_path}.{item_name}"
                            if current_path and item_name
                            else item_name or current_path
                        )
                        walk(item, next_path, container_name)
                return

            if "value" in node:
                field_name = pick_field_name(node, current_path.split(".")[-1] if current_path else "")
                path = current_path or field_name
                value = node.get("value")
                if isinstance(value, dict):
                    for child_key, child_value in value.items():
                        next_path = f"{path}.{child_key}" if path else str(child_key)
                        walk(child_value, next_path, group_name or field_name)
                    return
                if isinstance(value, list):
                    if not value:
                        append_row(path, node, value, group_name)
                        return
                    scalar_items = [item for item in value if not isinstance(item, (dict, list))]
                    if scalar_items:
                        append_row(path, node, value, group_name)
                    for index, item in enumerate(value):
                        if isinstance(item, (dict, list)):
                            next_path = f"{path}[{index}]" if path else f"[{index}]"
                            walk(item, next_path, group_name or field_name)
                    return
                append_row(path, node, value, group_name)
                return

            for key, value in node.items():
                if key == "params":
                    continue
                next_path = f"{current_path}.{key}" if current_path else str(key)
                walk(value, next_path, group_name)
            return

        if isinstance(node, list):
            for index, item in enumerate(node):
                next_path = f"{current_path}[{index}]" if current_path else f"[{index}]"
                walk(item, next_path, group_name)

    walk(schema)
    return rows
