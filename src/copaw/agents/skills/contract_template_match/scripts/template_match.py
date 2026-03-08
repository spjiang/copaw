#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template search by user intent text.

Usage:
    python template_match.py <session_id> <user_id> <exec_id> <query_text> [contract_type]
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

_CUR_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _CUR_DIR.parent.parent
sys.path.insert(0, str(_CUR_DIR))
sys.path.insert(0, str(_SKILLS_DIR))

from search_common import extract_keywords, infer_contract_type, search_templates
from shared.push import push
from shared.redis_push import push_end, push_error, push_running, push_start

SKILL_NAME = "contract_template_match"


def main():
    if len(sys.argv) < 5:
        print(json.dumps({"error": "usage: template_match.py session_id user_id exec_id query_text [contract_type]"}))
        sys.exit(1)

    session_id = os.environ.get("COPAW_SESSION_ID") or sys.argv[1] or "unknown_session"
    user_id = os.environ.get("COPAW_USER_ID") or sys.argv[2] or "unknown_user"
    exec_id = sys.argv[3]
    query_text = sys.argv[4]
    contract_type = sys.argv[5] if len(sys.argv) > 5 else ""
    run_id = str(uuid.uuid4())
    start_time = time.time()

    detected_contract_type = contract_type or infer_contract_type(query_text)
    keyword_list = extract_keywords(query_text, contract_type=detected_contract_type)
    input_data = {
        "query_text": query_text,
        "contract_type": detected_contract_type,
        "keyword_list": keyword_list,
    }

    push(session_id, user_id, "🔍 正在检索合同模板...", msg_type="progress")
    push_start(
        session_id=session_id,
        user_id=user_id,
        skill_name=SKILL_NAME,
        input_data=input_data,
        exec_id=exec_id,
        run_id=run_id,
    )

    try:
        if not detected_contract_type and not keyword_list:
            runtime_ms = int((time.time() - start_time) * 1000)
            result = {
                "total": 0,
                "templates": [],
                "detected_contract_type": "",
                "keyword_list": [],
                "need_user_confirm": False,
                "need_user_intent": True,
            }
            push_running(
                session_id=session_id,
                user_id=user_id,
                skill_name=SKILL_NAME,
                render_type="user_intent_required",
                input_data=input_data,
                output_data={"message": "无法识别合同类型，需要用户进一步说明"},
                exec_id=exec_id,
                run_id=run_id,
                runtime_ms=runtime_ms,
            )
            push_end(
                session_id=session_id,
                user_id=user_id,
                skill_name=SKILL_NAME,
                input_data=input_data,
                output_data=result,
                render_type="agent_end",
                exec_id=exec_id,
                run_id=run_id,
                runtime_ms=runtime_ms,
            )
            print(json.dumps(result, ensure_ascii=False))
            return

        push_running(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            render_type="user_intent_identified",
            input_data={"query_text": query_text},
            output_data={
                "contract_type": detected_contract_type,
                "keyword_list": keyword_list,
            },
            exec_id=exec_id,
            run_id=run_id,
        )

        result = search_templates(
            query_text=query_text,
            keyword_list=keyword_list,
            contract_type=detected_contract_type,
            top_k=5,
        )
        result["need_user_confirm"] = result.get("total", 0) > 0
        result["need_user_intent"] = False

        runtime_ms = int((time.time() - start_time) * 1000)
        if result.get("total", 0) > 0:
            push(session_id, user_id, f"✅ 已匹配到 {result['total']} 份合同模板", msg_type="result")
            push_running(
                session_id=session_id,
                user_id=user_id,
                skill_name=SKILL_NAME,
                render_type="template_candidates_found",
                input_data=input_data,
                output_data={
                    "template_count": result["total"],
                    "template_list": result["templates"],
                },
                exec_id=exec_id,
                run_id=run_id,
                runtime_ms=runtime_ms,
            )
        else:
            push(session_id, user_id, "ℹ️ 未匹配到标准合同模板", msg_type="progress")
            push_running(
                session_id=session_id,
                user_id=user_id,
                skill_name=SKILL_NAME,
                render_type="template_not_found",
                input_data=input_data,
                output_data={"template_count": 0, "template_list": []},
                exec_id=exec_id,
                run_id=run_id,
                runtime_ms=runtime_ms,
            )

        push_end(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            input_data=input_data,
            output_data=result,
            render_type="agent_end",
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        runtime_ms = int((time.time() - start_time) * 1000)
        push(session_id, user_id, f"❌ 合同模板匹配失败：{exc}", msg_type="error")
        push_error(
            session_id=session_id,
            user_id=user_id,
            skill_name=SKILL_NAME,
            input_data=input_data,
            error_msg=str(exc),
            exec_id=exec_id,
            run_id=run_id,
            runtime_ms=runtime_ms,
        )
        print(json.dumps({"error": str(exc), "total": 0, "templates": []}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
