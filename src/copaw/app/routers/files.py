# -*- coding: utf-8 -*-
"""File upload API for chat attachments.

Frontend uploads files here before sending messages.
The returned URL is embedded in the message as a file block.
CoPaw then downloads it to a local path and injects
"用户上传文件，已经下载到 {local_path}" into the message context
so skills can directly use the path.
"""
import os
import uuid
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from ...constant import WORKING_DIR

router = APIRouter(prefix="/files", tags=["files"])

# Upload directory: ~/.copaw/file_store/uploads/
UPLOAD_DIR = WORKING_DIR / "file_store" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Max file size: 50 MB
MAX_FILE_SIZE = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv",
    ".txt", ".md", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".zip", ".pptx", ".ppt",
}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file for use as a chat attachment.

    Returns a URL that the frontend embeds in the message as a file block.
    CoPaw automatically downloads the file to local storage when processing
    the message, making the local path available to skills via the message text.

    Response format (compatible with Ant Design Upload component):
        { "url": "http://host/api/files/download/{filename}", "name": "...", "size": ... }
    """
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{ext}' not allowed. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content)} bytes). Max: {MAX_FILE_SIZE} bytes",
        )

    # Generate unique filename preserving original name
    date_prefix = datetime.now().strftime("%Y%m%d")
    uid = str(uuid.uuid4())[:8]
    safe_name = (file.filename or "upload").replace("/", "_").replace("\\", "_")
    stored_name = f"{date_prefix}_{uid}_{safe_name}"

    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(content)

    # 返回本地绝对路径作为 url 字段。
    # CoPaw 的 _resolve_local_path 逻辑会识别绝对路径，直接使用本地文件，
    # 完全跳过 HTTP 下载（避免 Agent 处理消息时向自己发请求导致超时）。
    local_path = str(dest.resolve())

    # 同时保留 HTTP 下载地址，供外部访问使用
    copaw_api = os.environ.get("COPAW_API_BASE", "http://127.0.0.1:8088")
    download_url = f"{copaw_api}/api/files/download/{stored_name}"

    return {
        "url": local_path,          # 消息文件块使用本地路径，避免自请求超时
        "download_url": download_url,  # 供外部访问
        "name": file.filename,
        "stored_name": stored_name,
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
    }


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Serve an uploaded file by filename.

    CoPaw's message processor calls this URL to download the file
    to local storage, then tells the LLM the local path.
    """
    # Security: only allow simple filenames (no path traversal)
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
