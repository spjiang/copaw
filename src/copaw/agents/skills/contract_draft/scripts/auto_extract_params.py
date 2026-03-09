#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto extract contract params from uploaded project materials."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

_CUR_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _CUR_DIR.parent.parent
sys.path.insert(0, str(_CUR_DIR))
sys.path.insert(0, str(_SKILLS_DIR))

from attachment_utils import SUPPORTED_EXTS, extract_text, materialize_file_ref, resolve_file_refs
from event_meta import SKILL_LABEL, SKILL_NAME, get_event_name
from param_schema_ops import (
    collect_table_rows,
    dump_params_payload,
    extract_schema,
    is_blank,
    load_params_payload,
    mark_auto_path,
    merge_attachment_refs,
    replace_schema,
    set_field_value,
)
from push import push
from redis_push import push_end, push_error, push_running, push_start
from runtime_context import resolve_input_file_urls, resolve_session_id, resolve_user_id

try:
    from copaw.providers import get_active_llm_config
except Exception:  # pragma: no cover
    get_active_llm_config = None  # type: ignore


LLM_CONFIDENCE_THRESHOLD = 0.85
MAX_LLM_TEXT_CHARS = 50000


def _normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[\s_\-:/：|（）()【】\[\]，,。；;]+", "", text)


def _contains_all(text: str, *keywords: str) -> bool:
    return all(keyword in text for keyword in keywords if keyword)


def _contains_any(text: str, *keywords: str) -> bool:
    return any(keyword in text for keyword in keywords if keyword)


def _extract_first(patterns: list[str], text: str, flags: int = re.S) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return ""


def _extract_sentence(text: str, keywords: tuple[str, ...]) -> str:
    for line in text.splitlines():
        line = line.strip(" \t-*")
        if not line:
            continue
        if all(keyword in line for keyword in keywords if keyword):
            return line
    return ""


def _extract_section(text: str, role: str) -> str:
    patterns = [
        rf"(?:\*\*)?{role}[:：](.*?)(?=(?:\n\s*(?:\*\*)?[甲乙丙丁]方[:：])|\n\s*##\s|\Z)",
        rf"{role}为([^。]+)",
    ]
    return _extract_first(patterns, text)


def _clean_inline_value(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip(" ：:;；，,。")).strip()


def _extract_party_name(text: str, role: str) -> str:
    patterns = [
        rf"{role}为([^，。；;\n]+)",
        rf"{role}[:：]\s*([^\n；;]+)",
    ]
    return _clean_inline_value(_extract_first(patterns, text))


def _extract_party_detail(section: str, field_type: str) -> str:
    if not section:
        return ""
    patterns_map = {
        "legal_representative": [r"法定代表人\s*([^\s；;，,。]+)"],
        "contact_name": [r"联系人\s*([^\s；;，,。]+)"],
        "contact_title": [r"职务\s*([^\s；;，,。]+)"],
        "phone": [r"(?:联系电话|电话|手机)\s*([0-9\-]{7,20})"],
        "email": [r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"],
        "address": [r"(?:注册及办公地址|办公地址|注册地址|地址)[:：]?\s*([^。\n]+)"],
    }
    return _clean_inline_value(_extract_first(patterns_map.get(field_type, []), section, flags=re.I))


def _extract_dates(text: str) -> dict[str, str]:
    def normalize(date_text: str) -> str:
        return re.sub(r"\s+", "", date_text)

    effective = _extract_first(
        [r"拟于\s*([0-9]{4}\s*年\s*[0-9]{1,2}\s*月\s*[0-9]{1,2}\s*日)\s*生效", r"生效日期[:：]?\s*([0-9]{4}[^，。\n]+日)"],
        text,
    )
    sign = _extract_first(
        [r"均于\s*([0-9]{4}\s*年\s*[0-9]{1,2}\s*月\s*[0-9]{1,2}\s*日)\s*签署", r"签署日期[:：]?\s*([0-9]{4}[^，。\n]+日)"],
        text,
    )
    return {
        "effective_date": normalize(effective) if effective else "",
        "sign_date": normalize(sign) if sign else "",
    }


def _extract_product_section(text: str) -> str:
    return _extract_first([r"##\s*八、产品清单\s*(.*?)(?=\n\s*附件一合计金额|\n\s*##\s|\Z)"], text)


def _extract_payment_terms(text: str) -> str:
    section = _extract_first([r"##\s*六、付款约定\s*(.*?)(?=\n\s*##\s|\Z)"], text)
    if section:
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        return "\n".join(lines)
    return _extract_sentence(text, ("付款",)) or _extract_sentence(text, ("支付",))


def _extract_delivery_term(text: str) -> str:
    return _extract_sentence(text, ("交付期限",)) or _extract_sentence(text, ("履行期限",))


def _extract_material_facts(materials: list[dict[str, Any]]) -> dict[str, Any]:
    combined_text = "\n\n".join(item.get("text", "") for item in materials if item.get("text"))
    party_a_section = _extract_section(combined_text, "甲方")
    party_b_section = _extract_section(combined_text, "乙方")
    dates = _extract_dates(combined_text)
    total_amount = _extract_sentence(combined_text, ("合同总金额",))
    tax_rate = _extract_first([r"税率\s*([0-9]+(?:\.[0-9]+)?%)"], combined_text)
    delivery_term = _extract_delivery_term(combined_text)
    payment_terms = _extract_payment_terms(combined_text)
    product_section = _extract_product_section(combined_text)
    software_name = _extract_first([r"软件产品名称为([^。；;\n]+)"], combined_text)

    return {
        "combined_text": combined_text,
        "party_a_name": _extract_party_name(combined_text, "甲方"),
        "party_b_name": _extract_party_name(combined_text, "乙方"),
        "party_a_legal_representative": _extract_party_detail(party_a_section, "legal_representative"),
        "party_b_legal_representative": _extract_party_detail(party_b_section, "legal_representative"),
        "party_a_contact_name": _extract_party_detail(party_a_section, "contact_name"),
        "party_b_contact_name": _extract_party_detail(party_b_section, "contact_name"),
        "party_a_contact_title": _extract_party_detail(party_a_section, "contact_title"),
        "party_b_contact_title": _extract_party_detail(party_b_section, "contact_title"),
        "party_a_phone": _extract_party_detail(party_a_section, "phone"),
        "party_b_phone": _extract_party_detail(party_b_section, "phone"),
        "party_a_email": _extract_party_detail(party_a_section, "email"),
        "party_b_email": _extract_party_detail(party_b_section, "email"),
        "party_a_address": _extract_party_detail(party_a_section, "address"),
        "party_b_address": _extract_party_detail(party_b_section, "address"),
        "effective_date": dates.get("effective_date", ""),
        "sign_date": dates.get("sign_date", ""),
        "delivery_term": delivery_term,
        "contract_total_amount": total_amount,
        "tax_rate": tax_rate,
        "payment_terms": payment_terms,
        "product_section": product_section.strip(),
        "software_name": _clean_inline_value(software_name),
        "recipient_name": _clean_inline_value(_extract_first([r"指定收货人[:：]?\s*([^\s；;，,。]+)"], combined_text)),
        "recipient_phone": _clean_inline_value(_extract_first([r"收货人[：:][^。\n]*?电话\s*([0-9\-]{7,20})"], combined_text)),
        "recipient_email": _clean_inline_value(_extract_first([r"收货人[：:][^。\n]*?邮箱\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"], combined_text, flags=re.I)),
        "recipient_address": _clean_inline_value(_extract_first([r"收货地址[:：]?\s*([^。\n]+)"], combined_text)),
    }


def _candidate_from_facts(row: dict[str, Any], facts: dict[str, Any], attachments: list[str]) -> dict[str, Any] | None:
    label = " ".join(
        str(row.get(key) or "")
        for key in ("field_name", "desc", "group", "path")
    )
    normalized = _normalize_text(label)
    candidate_key = ""
    reason = ""
    confidence = 0.0

    if _contains_all(normalized, "甲方") and _contains_any(normalized, "名称", "公司", "企业", "单位", "主体"):
        candidate_key = "party_a_name"
        reason = "matched_party_a_name"
        confidence = 0.98
    elif _contains_all(normalized, "乙方") and _contains_any(normalized, "名称", "公司", "企业", "单位", "主体"):
        candidate_key = "party_b_name"
        reason = "matched_party_b_name"
        confidence = 0.98
    elif _contains_all(normalized, "甲方", "法定代表人"):
        candidate_key = "party_a_legal_representative"
        reason = "matched_party_a_legal_representative"
        confidence = 0.97
    elif _contains_all(normalized, "乙方", "法定代表人"):
        candidate_key = "party_b_legal_representative"
        reason = "matched_party_b_legal_representative"
        confidence = 0.97
    elif _contains_all(normalized, "甲方") and _contains_any(normalized, "联系人", "联系人姓名"):
        candidate_key = "party_a_contact_name"
        reason = "matched_party_a_contact_name"
        confidence = 0.96
    elif _contains_all(normalized, "乙方") and _contains_any(normalized, "联系人", "联系人姓名"):
        candidate_key = "party_b_contact_name"
        reason = "matched_party_b_contact_name"
        confidence = 0.96
    elif _contains_all(normalized, "甲方") and _contains_any(normalized, "职务", "岗位"):
        candidate_key = "party_a_contact_title"
        reason = "matched_party_a_contact_title"
        confidence = 0.90
    elif _contains_all(normalized, "乙方") and _contains_any(normalized, "职务", "岗位"):
        candidate_key = "party_b_contact_title"
        reason = "matched_party_b_contact_title"
        confidence = 0.90
    elif _contains_all(normalized, "甲方") and _contains_any(normalized, "电话", "手机", "联系电话"):
        candidate_key = "party_a_phone"
        reason = "matched_party_a_phone"
        confidence = 0.96
    elif _contains_all(normalized, "乙方") and _contains_any(normalized, "电话", "手机", "联系电话"):
        candidate_key = "party_b_phone"
        reason = "matched_party_b_phone"
        confidence = 0.96
    elif _contains_all(normalized, "甲方") and "邮箱" in normalized:
        candidate_key = "party_a_email"
        reason = "matched_party_a_email"
        confidence = 0.96
    elif _contains_all(normalized, "乙方") and "邮箱" in normalized:
        candidate_key = "party_b_email"
        reason = "matched_party_b_email"
        confidence = 0.96
    elif _contains_all(normalized, "甲方") and _contains_any(normalized, "地址", "注册地址", "办公地址"):
        candidate_key = "party_a_address"
        reason = "matched_party_a_address"
        confidence = 0.94
    elif _contains_all(normalized, "乙方") and _contains_any(normalized, "地址", "注册地址", "办公地址"):
        candidate_key = "party_b_address"
        reason = "matched_party_b_address"
        confidence = 0.94
    elif _contains_any(normalized, "签署日期", "签订日期", "签约日期"):
        candidate_key = "sign_date"
        reason = "matched_sign_date"
        confidence = 0.95
    elif _contains_any(normalized, "生效日期"):
        candidate_key = "effective_date"
        reason = "matched_effective_date"
        confidence = 0.95
    elif _contains_any(normalized, "交付期限", "履行期限", "服务期限"):
        candidate_key = "delivery_term"
        reason = "matched_delivery_term"
        confidence = 0.90
    elif _contains_any(normalized, "合同总金额", "总金额", "合同金额", "价税合计"):
        candidate_key = "contract_total_amount"
        reason = "matched_contract_total_amount"
        confidence = 0.92
    elif _contains_any(normalized, "税率", "增值税率"):
        candidate_key = "tax_rate"
        reason = "matched_tax_rate"
        confidence = 0.95
    elif _contains_any(normalized, "付款", "支付"):
        candidate_key = "payment_terms"
        reason = "matched_payment_terms"
        confidence = 0.88
    elif _contains_any(normalized, "产品清单", "服务清单", "清单明细", "标的清单"):
        candidate_key = "product_section"
        reason = "matched_product_section"
        confidence = 0.88
    elif _contains_any(normalized, "产品名称", "软件名称"):
        candidate_key = "software_name"
        reason = "matched_software_name"
        confidence = 0.90
    elif _contains_any(normalized, "收货人", "收件人"):
        candidate_key = "recipient_name"
        reason = "matched_recipient_name"
        confidence = 0.92
    elif _contains_any(normalized, "收货地址", "收件地址"):
        candidate_key = "recipient_address"
        reason = "matched_recipient_address"
        confidence = 0.92
    elif _contains_any(normalized, "收货邮箱", "收件邮箱"):
        candidate_key = "recipient_email"
        reason = "matched_recipient_email"
        confidence = 0.92
    elif _contains_any(normalized, "收货电话", "收件电话"):
        candidate_key = "recipient_phone"
        reason = "matched_recipient_phone"
        confidence = 0.92

    if candidate_key:
        value = facts.get(candidate_key)
        if isinstance(value, str) and value.strip():
            return {
                "value": value.strip(),
                "confidence": confidence,
                "reason": reason,
                "attachments": attachments,
            }

    field_name = str(row.get("field_name") or "").strip()
    if field_name:
        fallback = _extract_first(
            [rf"{re.escape(field_name)}\s*[:：]\s*([^\n。；;]+)"],
            facts.get("combined_text", ""),
        )
        if fallback:
            return {
                "value": fallback.strip(),
                "confidence": 0.82,
                "reason": "matched_field_name_literal",
                "attachments": attachments,
            }
    return None


def _strip_json_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return value


def _extract_json_payload(text: str) -> Any:
    clean = _strip_json_fence(text)
    if not clean:
        return None
    try:
        return json.loads(clean)
    except Exception:
        pass
    match = re.search(r"(\[.*\]|\{.*\})", clean, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except Exception:
        return None


def _resolve_llm_config() -> dict[str, str]:
    model = ""
    base_url = ""
    api_key = ""
    if callable(get_active_llm_config):
        try:
            cfg = get_active_llm_config()
            if cfg and not getattr(cfg, "is_local", False):
                model = str(getattr(cfg, "model", "") or "").strip()
                base_url = str(getattr(cfg, "base_url", "") or "").strip()
                api_key = str(getattr(cfg, "api_key", "") or "").strip()
        except Exception:
            pass
    if not model:
        model = os.environ.get("CONTRACT_DRAFT_EXTRACT_MODEL", "").strip()
    if not base_url:
        base_url = os.environ.get(
            "CONTRACT_DRAFT_EXTRACT_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).strip()
    if not api_key:
        api_key = (
            os.environ.get("CONTRACT_DRAFT_EXTRACT_API_KEY", "").strip()
            or os.environ.get("DASHSCOPE_API_KEY", "").strip()
        )
    if not model:
        model = "qwen-plus"
    return {"model": model, "base_url": base_url, "api_key": api_key}


def _extract_candidates_by_llm(rows: list[dict[str, Any]], material_text: str, attachments: list[str]) -> dict[str, dict[str, Any]]:
    if requests is None or not rows or not material_text.strip():
        return {}
    cfg = _resolve_llm_config()
    base_url = cfg.get("base_url", "").rstrip("/")
    api_key = cfg.get("api_key", "").strip()
    model = cfg.get("model", "").strip()
    if not base_url or not api_key or not model:
        return {}

    field_specs = []
    for row in rows:
        path = str(row.get("path") or "").strip()
        if not path:
            continue
        field_specs.append(
            {
                "path": path,
                "field_name": str(row.get("field_name") or ""),
                "desc": str(row.get("desc") or ""),
                "group": str(row.get("group") or ""),
                "required": bool(row.get("required", True)),
                "current_value": row.get("value"),
            }
        )
    if not field_specs:
        return {}

    user_prompt = {
        "task": "根据合同附件文本抽取字段值并映射到给定 path",
        "rules": [
            "只返回 JSON，不要解释",
            "仅可输出字段列表中的 path",
            "无法确定就不要输出该字段",
            "confidence 为 0~1 的小数",
            "value 必须是字符串",
        ],
        "fields": field_specs,
        "material_text": material_text[:MAX_LLM_TEXT_CHARS],
        "output_format": [
            {
                "path": "字段 path",
                "value": "提取值字符串",
                "confidence": 0.95,
                "reason": "简短提取依据",
                "evidence": "附件中的原文片段",
            }
        ],
    }
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": "你是合同参数提取助手。严格按用户要求输出 JSON。",
            },
            {
                "role": "user",
                "content": json.dumps(user_prompt, ensure_ascii=False),
            },
        ],
    }

    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    try:
        resp = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
        if not resp.ok:
            return {}
        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _extract_json_payload(str(content))
    except Exception:
        return {}

    if isinstance(parsed, dict):
        parsed = parsed.get("results") or parsed.get("items") or []
    if not isinstance(parsed, list):
        return {}

    best: dict[str, dict[str, Any]] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        value = str(item.get("value") or "").strip()
        if not path or not value:
            continue
        try:
            confidence = float(item.get("confidence") or 0)
        except Exception:
            confidence = 0.0
        if confidence < LLM_CONFIDENCE_THRESHOLD:
            continue
        candidate = {
            "value": value,
            "confidence": confidence,
            "reason": str(item.get("reason") or "llm_extract"),
            "evidence": str(item.get("evidence") or ""),
            "attachments": attachments,
        }
        prev = best.get(path)
        if prev is None or float(prev.get("confidence") or 0) < confidence:
            best[path] = candidate
    return best


def _resolve_push_params_script() -> Path:
    local_script = _CUR_DIR / "push_params.py"
    if local_script.exists():
        return local_script
    raise RuntimeError("push_params.py not found")


def _run_push_params(script_path: Path, params_file: Path, exec_id: str, session_id: str, user_id: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            str(params_file),
            exec_id or "",
            session_id or "",
            user_id or "",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "push_params failed").strip())
    output = (completed.stdout or "").strip()
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    return {"ok": True}


def _load_materials(file_refs: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    materials: list[dict[str, Any]] = []
    skipped: list[str] = []
    for ref in file_refs:
        try:
            path = materialize_file_ref(ref)
            ext = Path(path).suffix.lower()
            if ext and ext not in SUPPORTED_EXTS:
                skipped.append(ref)
                continue
            text = extract_text(path).strip()
            if not text:
                skipped.append(ref)
                continue
            materials.append(
                {
                    "ref": ref,
                    "path": path,
                    "name": Path(path).name,
                    "text": text[:20000],
                }
            )
        except Exception:
            skipped.append(ref)
    return materials, skipped


def main() -> None:
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "error": "usage: auto_extract_params.py <params_json_file> [exec_id] [session_id] [user_id] [file_refs]"
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    start_time = time.time()
    params_file = Path(sys.argv[1])
    exec_id = sys.argv[2] if len(sys.argv) > 2 else ""
    session_id = resolve_session_id(sys.argv[3] if len(sys.argv) > 3 else "")
    user_id = resolve_user_id(sys.argv[4] if len(sys.argv) > 4 else "")
    runtime_file_refs = sys.argv[5] if len(sys.argv) > 5 else ""
    current_refs = resolve_file_refs(resolve_input_file_urls(runtime_file_refs))
    run_id = str(uuid.uuid4())
    input_data = {"params_file": str(params_file), "exec_id": exec_id, "new_attachment_refs": current_refs}

    push_start(
        session_id=session_id,
        user_id=user_id,
        skill_name=SKILL_NAME,
        skill_label=SKILL_LABEL,
        event_name=get_event_name("template_params_auto_extract_started"),
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
        render_type="template_params_auto_extract_started",
    )

    try:
        if not params_file.exists():
            raise RuntimeError(f"params file not found: {params_file}")

        payload = load_params_payload(params_file)
        schema = extract_schema(payload)
        if not isinstance(schema, (dict, list)):
            raise RuntimeError("param schema is invalid")

        merged_refs = merge_attachment_refs(payload, current_refs)
        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name=get_event_name("template_params_material_merged"),
            render_type="template_params_material_merged",
            input_data=input_data,
            output_data={
                "new_attachment_count": len(current_refs),
                "merged_attachment_count": len(merged_refs),
                "attachment_refs": merged_refs,
            },
            exec_id=exec_id,
            run_id=run_id,
        )

        materials, skipped_refs = _load_materials(merged_refs)
        if not materials:
            raise RuntimeError("未找到可用于自动填写的附件内容")

        facts = _extract_material_facts(materials)
        rows = collect_table_rows(schema)
        updated_paths: list[str] = []
        processed_attachments = [item["ref"] for item in materials]
        llm_candidates = _extract_candidates_by_llm(
            rows=rows,
            material_text=facts.get("combined_text", ""),
            attachments=processed_attachments,
        )
        llm_hit_paths: list[str] = []
        fallback_hit_paths: list[str] = []

        for row in rows:
            path = str(row.get("path") or "").strip()
            current_value = row.get("value")
            if not path:
                continue
            candidate = llm_candidates.get(path)
            used_fallback = False
            if not candidate:
                candidate = _candidate_from_facts(row, facts, processed_attachments)
                used_fallback = True
            if not candidate or float(candidate.get("confidence") or 0) < LLM_CONFIDENCE_THRESHOLD:
                continue
            new_value = candidate.get("value")
            if is_blank(new_value):
                continue
            if current_value == new_value:
                mark_auto_path(
                    payload,
                    path,
                    confidence=float(candidate.get("confidence") or 0),
                    attachments=processed_attachments,
                    reason=str(candidate.get("reason") or ""),
                )
                if used_fallback:
                    fallback_hit_paths.append(path)
                else:
                    llm_hit_paths.append(path)
                continue
            if set_field_value(schema, path, new_value):
                updated_paths.append(path)
                mark_auto_path(
                    payload,
                    path,
                    confidence=float(candidate.get("confidence") or 0),
                    attachments=processed_attachments,
                    reason=str(candidate.get("reason") or ""),
                )
                if used_fallback:
                    fallback_hit_paths.append(path)
                else:
                    llm_hit_paths.append(path)

        payload = replace_schema(payload, schema)
        dump_params_payload(params_file, payload)
        push_params_result = _run_push_params(
            _resolve_push_params_script(),
            params_file,
            exec_id,
            session_id,
            user_id,
        )

        runtime_ms = int((time.time() - start_time) * 1000)
        result = {
            "ok": True,
            "params_file": str(params_file),
            "new_attachment_count": len(current_refs),
            "merged_attachment_count": len(merged_refs),
            "processed_attachment_count": len(processed_attachments),
            "processed_attachments": processed_attachments,
            "skipped_attachment_refs": skipped_refs,
            "llm_hit_paths": sorted(set(llm_hit_paths)),
            "fallback_hit_paths": sorted(set(fallback_hit_paths)),
            "updated_paths": updated_paths,
            "push_params_result": push_params_result,
        }
        push_end(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name=get_event_name("template_params_auto_extract_finished"),
            input_data=input_data,
            output_data=result,
            render_type="template_params_auto_extract_finished",
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(
            session_id,
            user_id,
            f"✅ 已根据 {len(processed_attachments)} 份项目材料更新合同信息，共自动填写 {len(updated_paths)} 项",
            msg_type="result",
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        runtime_ms = int((time.time() - start_time) * 1000)
        push_error(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            skill_label=SKILL_LABEL,
            event_name="根据附件自动填写失败",
            input_data=input_data,
            error_msg=str(exc),
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        push(session_id, user_id, f"❌ 根据附件自动填写失败：{exc}", msg_type="error")
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
