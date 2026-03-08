#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared search utilities for contract template matching scripts."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

DEFAULT_TEMPLATE_FILE_BASE_URL = os.environ.get(
    "TEMPLATE_FILE_BASE_URL",
    "http://10.156.196.158:19000/copaw-files",
)
DEFAULT_TEMPLATE_SEARCH_API = os.environ.get(
    "TEMPLATE_SEARCH_API",
    "http://10.17.55.121:8012/search_template",
)

CONTRACT_TYPE_KEYWORDS = {
    "采购": ["采购", "购买", "采买", "委托采购", "设备采购", "软件采购", "甲方采购", "采购方"],
    "销售": ["销售", "出售", "供货", "软件销售", "产品销售", "乙方提供", "受托方", "提供服务"],
    "租赁": ["租赁", "出租", "承租", "房屋租赁"],
    "服务": ["服务", "技术服务", "实施服务", "运维服务", "咨询服务"],
    "开发": ["开发", "技术开发", "定制开发", "研发"],
}

CONTRACT_TYPE_ALIASES = {
    "purchase": "采购",
    "procurement": "采购",
    "buy": "采购",
    "sales": "销售",
    "sale": "销售",
    "sell": "销售",
    "lease": "租赁",
    "rental": "租赁",
    "service": "服务",
    "services": "服务",
    "development": "开发",
    "dev": "开发",
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def infer_contract_type(text: str) -> str:
    source = clean_text(text)
    if not source:
        return ""

    if re.search(r"软通智慧.{0,25}(乙方|受托方|提供方|服务方)", source):
        return "销售"
    if re.search(r"(乙方|受托方|提供方|服务方).{0,25}软通智慧", source):
        return "销售"
    if re.search(r"软通智慧.{0,25}(甲方|采购方|委托方)", source):
        return "采购"
    if re.search(r"(甲方|采购方|委托方).{0,25}软通智慧", source):
        return "采购"

    for contract_type, keywords in CONTRACT_TYPE_KEYWORDS.items():
        if any(keyword in source for keyword in keywords):
            return contract_type
    return ""


def normalize_contract_type(value: Any) -> str:
    raw = clean_text(str(value or "")).lower()
    if not raw:
        return ""
    if raw in CONTRACT_TYPE_ALIASES:
        return CONTRACT_TYPE_ALIASES[raw]
    for contract_type in CONTRACT_TYPE_KEYWORDS:
        if contract_type in raw:
            return contract_type
    return str(value or "").strip()


def normalize_filename(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r"^\d+[-_.\s]*", "", name)
    name = re.sub(r"^\d{6,14}_[0-9a-f]{8}_", "", name, flags=re.IGNORECASE)
    return name.strip()


def extract_keywords(text: str, filename: str = "", contract_type: str = "") -> list[str]:
    merged = " ".join(filter(None, [normalize_filename(filename), clean_text(text), contract_type]))
    keywords: list[str] = []

    if contract_type:
        keywords.append(contract_type)
        if not contract_type.endswith("合同"):
            keywords.append(f"{contract_type}合同")

    for _, type_keywords in CONTRACT_TYPE_KEYWORDS.items():
        for keyword in type_keywords:
            if keyword in merged and keyword not in keywords:
                keywords.append(keyword)

    patterns = [
        r"(软件采购)",
        r"(设备采购)",
        r"(产品销售)",
        r"(软件销售)",
        r"(房屋租赁)",
        r"(技术开发)",
        r"(技术服务)",
        r"(运维服务)",
        r"(咨询服务)",
        r"(系统集成)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, merged):
            if match not in keywords:
                keywords.append(match)

    if filename:
        name = normalize_filename(filename)
        if name and name not in keywords:
            keywords.append(name)

    compact = []
    seen = set()
    for keyword in keywords:
        kw = keyword.strip()
        if not kw or kw in seen:
            continue
        seen.add(kw)
        compact.append(kw)
    return compact[:10]


def build_template_url(file_path: str) -> str:
    if not file_path:
        return ""
    if re.match(r"^https?://", file_path):
        return file_path
    if os.path.isabs(file_path):
        return ""
    prefix = DEFAULT_TEMPLATE_FILE_BASE_URL.rstrip("/")
    if file_path.startswith("/"):
        return f"{prefix}{file_path}"
    return f"{prefix}/{file_path}"


def parse_param_schema_json(value: Any) -> Any:
    if value in (None, ""):
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw}
    return value


def parse_json_text(value: Any) -> Any:
    if value in (None, ""):
        return []
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return [raw]
    return value


def _normalize_api_template(row: dict[str, Any]) -> dict[str, Any]:
    title = row.get("title") or row.get("template_name") or row.get("name") or ""
    file_path = row.get("file_path") or row.get("template_path") or row.get("path") or ""
    template_url = row.get("template_url") or build_template_url(file_path)
    template_id = str(row.get("id") or row.get("template_id") or "")
    raw_contract_type = row.get("contract_type") or ""
    contract_type = normalize_contract_type(raw_contract_type) or infer_contract_type(title)
    category = row.get("category") or ""
    tags = parse_json_text(row.get("tags"))
    sub_tags = parse_json_text(row.get("sub_tags"))
    sub_type = row.get("sub_type") or (sub_tags[0] if isinstance(sub_tags, list) and sub_tags else "")
    param_schema_json = parse_param_schema_json(row.get("param_schema_json"))
    return {
        "template_id": template_id,
        "title": title,
        "template_name": title,
        "description": row.get("description") or "",
        "category": category,
        "tags": tags,
        "sub_tags": sub_tags,
        "version": row.get("version") or "",
        "usage_count": row.get("usage_count"),
        "variables_count": row.get("variables_count"),
        "status": row.get("status") or "",
        "starred": row.get("starred"),
        "file_id": row.get("file_id"),
        "template_type": row.get("template_type") or "",
        "raw_contract_type": raw_contract_type,
        "contract_type": contract_type,
        "sub_type": sub_type,
        "file_path": file_path,
        "template_url": template_url,
        "param_schema_json": param_schema_json,
    }


def _call_search_api(keyword: str, limit: int, offset: int = 0) -> dict[str, Any]:
    if not keyword.strip():
        return {"success": False, "rows": [], "total": 0}

    params = {
        "keyword": keyword,
        "limit": max(1, limit),
        "offset": max(0, offset),
    }

    if requests is not None:
        response = requests.get(
            DEFAULT_TEMPLATE_SEARCH_API,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    else:  # pragma: no cover
        from urllib.request import urlopen

        url = f"{DEFAULT_TEMPLATE_SEARCH_API}?{urllib.parse.urlencode(params)}"
        with urlopen(url, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

    if not isinstance(data, dict):
        raise ValueError("template search api returned invalid payload")
    return data


def _search_api_templates(keyword_list: list[str], contract_type: str, top_k: int) -> list[dict[str, Any]]:
    keywords = [kw.strip() for kw in keyword_list if kw and kw.strip()]
    if contract_type:
        contract_keyword = contract_type if contract_type.endswith("合同") else f"{contract_type}合同"
        if contract_keyword not in keywords:
            keywords.insert(0, contract_keyword)
    if not keywords:
        return []

    merged: dict[str, dict[str, Any]] = {}
    for keyword in keywords:
        try:
            payload = _call_search_api(keyword=keyword, limit=top_k, offset=0)
        except Exception:
            continue

        if payload.get("success") is not True:
            continue

        rows = payload.get("rows") or []
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized = _normalize_api_template(row)
            template_id = normalized.get("template_id") or normalized.get("file_path") or normalized.get("title")
            if not template_id:
                continue
            merged[str(template_id)] = normalized
            if len(merged) >= top_k:
                break
        if len(merged) >= top_k:
            break

    return list(merged.values())[:top_k]


def search_templates(
    query_text: str,
    keyword_list: list[str] | None = None,
    contract_type: str = "",
    top_k: int = 5,
) -> dict[str, Any]:
    """Search contract templates from template search API.

    Returns:
        {
            "total": int,
            "templates": [{ template_id, title, template_name, contract_type,
                             sub_type, file_path, template_url, param_schema_json }],
            "detected_contract_type": str,
            "keyword_list": [str],
            "source": "api" | "none"
        }
    """
    query = clean_text(query_text)
    detected_contract_type = contract_type or infer_contract_type(query)
    keywords = keyword_list or extract_keywords(query, contract_type=detected_contract_type)

    api_templates = _search_api_templates(keywords, detected_contract_type, top_k=top_k)
    return {
        "total": len(api_templates),
        "templates": api_templates,
        "detected_contract_type": detected_contract_type,
        "keyword_list": keywords,
        "source": "api" if api_templates else "none",
    }


def fetch_template_by_id(template_id: str) -> dict[str, Any]:
    """Fetch a single template record by ID when available.

    The current search API only exposes keyword search, so this helper falls
    back to a broad lookup and then filters in memory.
    """
    try:
        payload = _call_search_api(keyword=template_id, limit=50, offset=0)
        rows = payload.get("rows") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized = _normalize_api_template(row)
            if normalized.get("template_id") == str(template_id):
                return normalized
        return {"error": f"template {template_id} not found"}
    except Exception as exc:
        return {"error": str(exc)}
