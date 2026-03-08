---
name: contract_template_match
description: "【合同模板匹配子智能体】仅供 contract_draft 主流程内部调用：根据用户上传附件或文字意图调用模板检索 API 匹配合同模板，返回候选模板列表及 param_schema_json。"
metadata:
  {
    "copaw": {
      "emoji": "📄",
      "requires": {}
    }
  }
---

# 合同模板匹配智能体

本技能负责把"用户需求"转成"可供确认的模板候选列表"，不负责最终合同生成。

## 适用边界

- 仅供 `contract_draft` 主智能体内部调用。
- 本技能只负责：
  - 判断是"附件匹配"还是"语义匹配"
  - 识别合同类型与关键词
  - 调用模板检索 API
  - 返回候选模板列表（含 `param_schema_json`）
- 本技能不负责：
  - 让用户填写参数
  - 生成最终合同
  - 调用模板渲染接口

## 运行时变量

- `session_id` = `os.environ.get("COPAW_SESSION_ID")`
- `user_id` = `os.environ.get("COPAW_USER_ID")`
- `exec_id` — 主流程传入
- `file_list` — `os.environ.get("COPAW_INPUT_FILE_URLS")`
- `query_text` — 用户当前需求描述

## 模板检索接口

```text
GET http://10.17.55.121:8012/search_template

Query:
- keyword: 检索关键词，如 `销售合同`
- limit: 返回条数，默认 `20`，范围 `1-100`
- offset: 分页偏移，默认 `0`，且必须 `>= 0`

示例:
curl "http://10.17.55.121:8012/search_template?keyword=销售合同&limit=20&offset=0"
```

接口响应结构：

```json
{
  "success": true,
  "keyword": "销售合同",
  "total": 1,
  "rows": [
    {
      "id": 14,
      "title": "软件产品销售合同",
      "description": "模板描述",
      "category": "销售合同",
      "tags": "[\"软件产品\", \"销售合同\"]",
      "sub_tags": "[\"软件销售\", \"维护服务\"]",
      "version": "v1.0",
      "usage_count": 0,
      "variables_count": 85,
      "status": "draft",
      "starred": false,
      "file_id": 177,
      "contract_type": "sales",
      "file_path": "users/1/2026/03/xxx.docx",
      "param_schema_json": "{...}",
      "template_type": "COMPANY"
    }
  ]
}
```

`rows` 关键字段说明：

| 字段 | 说明 |
| ---- | ---- |
| `id` | 模板唯一 ID |
| `title` | 模板名称 |
| `description` | 模板描述 |
| `category` | 模板分类 |
| `tags` | 标签，通常为 JSON 字符串 |
| `sub_tags` | 子标签，通常为 JSON 字符串 |
| `version` | 模板版本 |
| `usage_count` | 使用次数 |
| `variables_count` | 变量数量 |
| `status` | 模板状态 |
| `starred` | 是否星标 |
| `file_id` | 关联文件 ID |
| `file_path` | 模板文件路径或 HTTP URL |
| `contract_type` | 合同类型，接口当前可能返回英文枚举值，如 `sales` |
| `param_schema_json` | 参数结构 JSON，接口返回时通常是字符串 |
| `template_type` | 模板类型，如 `COMPANY` |

## 执行规则

1. 内部脚本调用、JSON 解析、Redis 推送必须静默执行，不向用户解释过程。
2. 只有需要用户确认模板时，才向用户输出结果。
3. 若用户意图不明确，不允许盲查模板库，必须返回主智能体继续追问。
4. 若只匹配到 1 份模板，也建议向用户确认，不要无感知自动采用。

## 执行步骤

### Step 1：判断匹配入口

优先判断是否存在附件：

- 若 `file_list` 有可用合同附件，走**附件匹配**。
- 若 `file_list` 为空，走**语义匹配**。

### Step 2：附件匹配

当用户上传了合同模板或参考合同附件时，调用：

```bash
execute_shell_command(
  "python3 ~/.copaw/active_skills/contract_template_match/scripts/match_by_file.py \
    {session_id} {user_id} {exec_id} '{file_ref}'"
)
```

脚本执行流程：

1. 下载或读取附件（支持 `.docx/.doc/.pdf/.txt/.md`）
2. 提取文本，推断 `contract_type` 和 `keyword_list`
3. 调用模板检索 API 匹配模板
4. 推送 `attachment_detected` → `user_intent_identified` → `template_candidates_found` / `template_not_found`

脚本输出（stdout JSON）：

```json
{
  "total": 2,
  "templates": [
    {
      "template_id": "42",
      "title": "产品采购合同-软件采购",
      "template_name": "产品采购合同-软件采购",
      "description": "模板描述",
      "category": "采购合同",
      "tags": ["软件采购", "采购合同"],
      "sub_tags": ["软件采购"],
      "version": "v1.0",
      "usage_count": 0,
      "variables_count": 8,
      "status": "draft",
      "starred": false,
      "file_id": 177,
      "template_type": "COMPANY",
      "raw_contract_type": "purchase",
      "contract_type": "采购",
      "sub_type": "软件采购",
      "file_path": "/templates/software_purchase.docx",
      "template_url": "http://10.156.196.158:19000/copaw-files/templates/software_purchase.docx",
      "param_schema_json": {
        "contract_effect_year": {"desc": "合同生效年份", "value": ""},
        "company_a": {"desc": "甲方公司名称", "value": ""},
        "company_b": {"desc": "乙方公司名称", "value": ""}
      }
    }
  ],
  "detected_contract_type": "采购",
  "keyword_list": ["软件采购", "采购"],
  "source": "api",
  "need_user_confirm": true,
  "need_user_intent": false
}
```

### Step 3：语义匹配

当无附件时，调用：

```bash
execute_shell_command(
  "python3 ~/.copaw/active_skills/contract_template_match/scripts/template_match.py \
    {session_id} {user_id} {exec_id} '{query_text}'"
)
```

脚本执行流程：

1. 提取关键词和合同类型
2. 若无法识别意图，返回 `need_user_intent=true`
3. 调用模板检索 API 匹配模板
4. 推送 `user_intent_identified` → `template_candidates_found` / `template_not_found`

### Step 4：结果处理

| 脚本输出 | 处理方式 |
| ---- | ---- |
| `need_user_intent=true` | 返回主智能体，追问用户意图 |
| `total > 0`，`need_user_confirm=true` | 向用户展示候选列表，等待确认 |
| `total = 0` | 返回主智能体，触发 LLM 自由起草 |

### Step 5：向用户展示候选列表

匹配成功时，向用户输出如下格式：

```markdown
已找到以下匹配的合同模板，请选择一个：

1. **产品采购合同-软件采购**（采购合同 · 非项目类）
   适用：软通智慧作为采购方，向供应商采购软件产品

2. **1【项目类】产品采购合同-软件采购**（采购合同 · 项目类）
   适用：项目类软件采购，含项目里程碑付款

请回复序号（1/2）确认使用，或回复"不使用模板，直接起草"。
```

## 返回格式要求

返回给主智能体的结构必须包含：

```json
{
  "total": 2,
  "templates": [...],
  "detected_contract_type": "采购",
  "keyword_list": ["软件采购"],
  "source": "api",
  "need_user_confirm": true,
  "need_user_intent": false,
  "selected_template_id": null,
  "selected_template_url": null,
  "selected_template_params_schema": null
}
```

其中每个 `templates[i]` 至少包含：

- `template_id`
- `title`
- `description`
- `category`
- `tags`
- `sub_tags`
- `contract_type`
- `raw_contract_type`
- `file_path`
- `template_url`
- `param_schema_json`
- `template_type`

用户确认模板后，补充填入：

```json
{
  "selected_template_id": "42",
  "selected_template_url": "http://10.156.196.158:19000/.../template.docx",
  "selected_template_params_schema": {
    "contract_effect_year": {"desc": "合同生效年份", "value": ""},
    "company_a": {"desc": "甲方公司名称", "value": ""},
    "company_b": {"desc": "乙方公司名称", "value": ""}
  }
}
```

## 失败处理

| 场景 | 处理方式 |
| ---- | ---- |
| 附件下载失败 | 推送 `error`，提示用户重传或描述需求 |
| 附件文本提取为空 | 推送 `error`，回退到语义匹配 |
| 模板检索 API 调用失败 | 返回 `total=0`，触发 LLM 自由起草 |
| 匹配结果为空 | 返回 `total=0`，由主智能体触发 LLM 自由起草 |
