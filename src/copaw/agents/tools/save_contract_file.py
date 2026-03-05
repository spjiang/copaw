# -*- coding: utf-8 -*-
"""Contract file storage tool.

Moves a generated contract .docx from a temp location to the permanent
contracts storage directory, returning the final path and access URL.
"""
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

logger = logging.getLogger(__name__)

STORAGE_BASE = Path(os.environ.get(
    "CONTRACT_STORAGE_DIR",
    str(Path.home() / ".copaw" / "contracts"),
))
COPAW_API = os.environ.get("COPAW_API_BASE", "http://127.0.0.1:8088")


async def save_contract_file(
    file_path: str,
    contract_type: str = "draft",
    exec_id: str = "",
    original_name: str = "",
    **kwargs: Any,
) -> ToolResponse:
    """Save a contract Word file to permanent storage.

    Args:
        file_path:      Source file path (temp or draft location).
        contract_type:  "draft" (起草) | "review" (审查) | "compare" (对比)
        exec_id:        Main execution ID for traceability.
        original_name:  Optional original filename override.

    Returns:
        JSON with saved_path and file_url.
    """
    src = Path(file_path)
    if not src.exists():
        return ToolResponse(
            content=[TextBlock(type="text", text=json.dumps({"error": f"file not found: {file_path}"}))]
        )

    # Build destination path: contracts/{type}/{YYYY}/{MM}/{exec_id_prefix}_{filename}
    now = datetime.now()
    dest_dir = STORAGE_BASE / contract_type / now.strftime("%Y") / now.strftime("%m")
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = original_name or src.name
    prefix = exec_id[:8] if exec_id else now.strftime("%H%M%S")
    dest_name = f"{prefix}_{filename}" if not filename.startswith(prefix) else filename
    dest_path = dest_dir / dest_name

    # Avoid overwrite
    counter = 1
    while dest_path.exists():
        stem = dest_name.rsplit(".", 1)[0]
        ext = dest_name.rsplit(".", 1)[-1] if "." in dest_name else ""
        dest_path = dest_dir / f"{stem}_{counter}.{ext}"
        counter += 1

    shutil.copy2(str(src), str(dest_path))
    file_size = dest_path.stat().st_size

    # Build relative URL for frontend access
    rel = dest_path.relative_to(STORAGE_BASE.parent)
    file_url = f"{COPAW_API}/files/{rel}"

    result = {
        "saved_path": str(dest_path),
        "file_url": file_url,
        "file_size": file_size,
        "filename": dest_name,
    }
    logger.info("save_contract_file: saved to %s (%d bytes)", dest_path, file_size)
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(result, ensure_ascii=False))]
    )
