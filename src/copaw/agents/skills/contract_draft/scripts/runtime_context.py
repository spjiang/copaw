#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime context helpers for cross-platform compatibility."""

from __future__ import annotations

import os


def _first_non_empty(*values: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def resolve_session_id(fallback: str = "", default: str = "unknown_session") -> str:
    return _first_non_empty(
        os.environ.get("COPAW_SESSION_ID", ""),
        os.environ.get("SESSION_ID", ""),
        os.environ.get("session_id", ""),
        fallback,
        default,
    )


def resolve_user_id(fallback: str = "", default: str = "unknown_user") -> str:
    return _first_non_empty(
        os.environ.get("COPAW_USER_ID", ""),
        os.environ.get("USER_ID", ""),
        os.environ.get("user_id", ""),
        fallback,
        default,
    )


def resolve_input_file_urls(fallback: str = "") -> str:
    return _first_non_empty(
        os.environ.get("COPAW_INPUT_FILE_URLS", ""),
        os.environ.get("INPUT_FILE_URLS", ""),
        os.environ.get("input_file_urls", ""),
        fallback,
    )
