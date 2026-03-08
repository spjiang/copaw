# -*- coding: utf-8 -*-
"""Contract params editing API for chat side panel."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/contract-params", tags=["contract-params"])


class ParamUpdateItem(BaseModel):
    path: str = Field(..., description="Parameter path from param_table.rows[].path")
    value: str = Field(default="", description="New value from frontend editor")


class ContractParamsUpdateRequest(BaseModel):
    params_file: str = Field(..., description="Temp params json file path")
    exec_id: str = Field(default="", description="Current contract draft exec_id")
    session_id: str = Field(default="", description="Current session id")
    user_id: str = Field(default="", description="Current user id")
    updates: list[ParamUpdateItem] = Field(default_factory=list)


def _pick_field_name(node: dict[str, Any], fallback: str = "") -> str:
    for key in ("field_name", "name", "label", "param_id", "key"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _ensure_allowed_params_file(raw_path: str) -> Path:
    if not raw_path.strip():
        raise HTTPException(status_code=400, detail="params_file is required")

    resolved = Path(raw_path).expanduser().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if (
        resolved.suffix != ".json"
        or not resolved.name.startswith("copaw_params_")
        or temp_root not in resolved.parents
    ):
        raise HTTPException(status_code=400, detail="params_file is not allowed")

    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"params file not found: {resolved}")
    return resolved


def _tokenize_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for name, index in re.findall(r"([^[.\]]+)|\[(\d+)\]", path):
        if name:
            tokens.append(name)
        elif index:
            tokens.append(int(index))
    return tokens


def _locate_field_node(node: Any, tokens: list[str | int]) -> dict[str, Any] | None:
    if not tokens:
        if isinstance(node, dict) and "value" in node:
            return node
        return None

    token = tokens[0]
    rest = tokens[1:]

    if isinstance(token, str):
        if isinstance(node, dict) and isinstance(node.get("params"), list):
            for item in node["params"]:
                if isinstance(item, dict) and _pick_field_name(item, "") == token:
                    found = _locate_field_node(item, rest)
                    if found is not None:
                        return found

        if isinstance(node, dict) and "value" in node and isinstance(node["value"], dict):
            child = node["value"].get(token)
            if child is not None:
                found = _locate_field_node(child, rest)
                if found is not None:
                    return found

        if isinstance(node, dict):
            child = node.get(token)
            if child is not None:
                found = _locate_field_node(child, rest)
                if found is not None:
                    return found

    if isinstance(token, int):
        if isinstance(node, dict) and "value" in node and isinstance(node["value"], list):
            if 0 <= token < len(node["value"]):
                found = _locate_field_node(node["value"][token], rest)
                if found is not None:
                    return found
        if isinstance(node, list) and 0 <= token < len(node):
            return _locate_field_node(node[token], rest)

    return None


def _coerce_value(raw_value: str, original_value: Any) -> Any:
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


def _apply_updates(schema: Any, updates: list[ParamUpdateItem]) -> list[str]:
    updated_paths: list[str] = []
    for item in updates:
        tokens = _tokenize_path(item.path)
        if not tokens:
            raise HTTPException(status_code=400, detail=f"invalid path: {item.path}")
        target = _locate_field_node(schema, tokens)
        if not isinstance(target, dict) or "value" not in target:
            raise HTTPException(status_code=400, detail=f"path not found: {item.path}")
        target["value"] = _coerce_value(item.value, target.get("value"))
        updated_paths.append(item.path)
    return updated_paths


def _resolve_push_params_script() -> Path:
    active_script = (
        Path.home()
        / ".copaw"
        / "active_skills"
        / "contract_draft"
        / "scripts"
        / "push_params.py"
    )
    if active_script.exists():
        return active_script

    repo_script = (
        Path(__file__).resolve().parents[4]
        / "src"
        / "copaw"
        / "agents"
        / "skills"
        / "contract_draft"
        / "scripts"
        / "push_params.py"
    )
    if repo_script.exists():
        return repo_script

    raise HTTPException(status_code=500, detail="push_params.py not found")


def _run_push_params(script_path: Path, params_file: Path, exec_id: str, session_id: str, user_id: str) -> dict[str, Any]:
    command = [
        sys.executable,
        str(script_path),
        str(params_file),
        exec_id or "",
        session_id or "",
        user_id or "",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "push_params failed").strip()
        raise HTTPException(status_code=500, detail=detail)

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return {"ok": True}

    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    return {"ok": True, "raw_output": stdout}


@router.post("/update")
async def update_contract_params(request: ContractParamsUpdateRequest) -> dict[str, Any]:
    if not request.updates:
        raise HTTPException(status_code=400, detail="updates is required")

    params_path = _ensure_allowed_params_file(request.params_file)

    try:
        payload = json.loads(params_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid params json: {exc}") from exc

    schema = payload.get("param_schema_json")
    if schema is None:
        schema = payload

    updated_paths = _apply_updates(schema, request.updates)
    if isinstance(payload, dict) and "param_schema_json" in payload:
        payload["param_schema_json"] = schema
    else:
        payload = schema

    params_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = _run_push_params(
        _resolve_push_params_script(),
        params_path,
        request.exec_id,
        request.session_id,
        request.user_id,
    )
    return {
        "ok": True,
        "updated_paths": updated_paths,
        "result": result,
    }
