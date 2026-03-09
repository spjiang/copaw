#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse smart-create API response to extract file download URL."""

from __future__ import annotations

import os
from typing import Any


def get_file_url_from_smart_create_response(payload: dict[str, Any]) -> str | None:
    """
    Parse smart-create API response to get full file download URL.

    New format: response has `current_version.object_name`, concatenate with
    MINIO_FILE_PREFIX (env: Minio_file_prefix) for full URL.

    Fallback: if simple `url` field exists, return it.
    """
    prefix = (
        os.environ.get("Minio_file_prefix")
        or os.environ.get("MINIO_FILE_PREFIX")
        or ""
    ).strip()
    cv = payload.get("current_version")
    if isinstance(cv, dict):
        obj = (cv.get("object_name") or "").strip()
        if obj and prefix:
            return (prefix.rstrip("/") + "/" + obj.lstrip("/")).strip()
    url = (payload.get("url") or "").strip()
    return url if url else None
