# -*- coding: utf-8 -*-
"""Contract params editing API for chat side panel."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from copaw.agents.skills.contract_draft.scripts.param_schema_ops import (
    apply_updates,
    dump_params_payload,
    extract_schema,
    load_params_payload,
    replace_schema,
)

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
        payload = load_params_payload(params_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid params json: {exc}") from exc

    schema = extract_schema(payload)

    try:
        updated_paths = apply_updates(schema, request.updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = replace_schema(payload, schema)
    dump_params_payload(params_path, payload)

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
