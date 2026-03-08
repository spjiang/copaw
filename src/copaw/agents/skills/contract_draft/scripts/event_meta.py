#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared skill event metadata for contract_draft."""

from __future__ import annotations

import os

SKILL_NAME = "contract_draft"
SKILL_LABEL = os.environ.get("COPAW_SKILL_LABEL", "合同起草智能体")

EVENT_NAME_MAP = {
    "agent_start": "合同起草开始",
    "file_list_checked": "附件检查完成",
    "attachment_missing": "未发现合同附件",
    "user_intent_required": "需要补充合同类型",
    "template_selection_required": "等待确认模板",
    "template_selected": "已确认模板",
    "template_skipped": "已跳过模板",
    "template_match_started": "开始匹配模板",
    "attachment_detected": "已识别上传附件",
    "user_intent_identified": "已识别合同意图",
    "template_candidates_found": "已找到候选模板",
    "template_not_found": "未匹配到模板",
    "template_match_finished": "模板匹配完成",
    "template_params_started": "开始合同模板数据采集",
    "template_params_required": "等待补充合同模板参数",
    "template_params_completed": "合同模板参数已补齐",
    "template_params_finished": "合同模板数据采集",
    "template_render_prepare": "开始准备模板渲染",
    "template_render_started": "开始渲染模板",
    "template_render_preview_prepare": "开始准备预览渲染",
    "template_render_preview_started": "开始预览渲染",
    "template_render_preview_success": "预览渲染成功",
    "template_render_preview_finished": "预览渲染完成",
    "template_render_preview_failed": "预览渲染失败",
    "template_render_success": "模板渲染成功",
    "template_render_finished": "模板渲染完成",
    "template_render_failed": "模板渲染失败",
    "llm_draft_started": "开始自由起草",
    "llm_draft_success": "自由起草完成",
    "llm_draft_failed": "自由起草失败",
    "agent_end": "合同起草完成",
    "error": "处理失败",
}

STAGE_NAME_MAP = {
    "start": "流程开始",
    "running": "处理中",
    "end": "流程结束",
    "error": "处理失败",
}

EVENT_CATEGORY_MAP = {
    "agent_start": "status",
    "file_list_checked": "status",
    "attachment_missing": "status",
    "user_intent_required": "status",
    "template_selection_required": "status",
    "template_selected": "status",
    "template_skipped": "status",
    "template_match_started": "status",
    "attachment_detected": "data",
    "user_intent_identified": "data",
    "template_candidates_found": "data",
    "template_not_found": "result",
    "template_match_finished": "result",
    "template_params_started": "status",
    "template_params_required": "status",
    "template_params_completed": "status",
    "template_params_finished": "data",
    "template_render_prepare": "status",
    "template_render_started": "status",
    "template_render_preview_prepare": "status",
    "template_render_preview_started": "status",
    "template_render_preview_success": "result",
    "template_render_preview_finished": "result",
    "template_render_preview_failed": "result",
    "template_render_success": "result",
    "template_render_finished": "result",
    "template_render_failed": "result",
    "llm_draft_started": "status",
    "llm_draft_success": "result",
    "llm_draft_failed": "result",
    "agent_end": "result",
    "error": "result",
}

STAGE_CATEGORY_MAP = {
    "start": "status",
    "running": "status",
    "end": "result",
    "error": "result",
}


def get_event_name(render_type: str = "", stage: str = "", fallback: str = "") -> str:
    return (
        EVENT_NAME_MAP.get(render_type)
        or STAGE_NAME_MAP.get(stage)
        or fallback
        or render_type
        or stage
        or "未命名事件"
    )


def get_event_category(render_type: str = "", stage: str = "", fallback: str = "status") -> str:
    return (
        EVENT_CATEGORY_MAP.get(render_type)
        or STAGE_CATEGORY_MAP.get(stage)
        or fallback
    )
