---
name: contract_template_params
description: "【合同模板参数子智能体】仅供 contract_draft 主流程内部调用：在模板确认后提取/补齐模板参数，推送参数状态，并在参数完整时调用渲染 API（POST /render）生成合同文件。"
metadata:
  {
    "copaw": {
      "emoji": "📝",
      "requires": {}
    }
  }
---

# 合同模板参数智能体

本技能负责把"已确认模板"转成"可渲染参数 + 渲染结果"，是模板路线中的核心子智能体。

## 适用边界

- 仅在用户已确认模板后调用。
- 本技能负责：
  - 读取 `param_schema_json`（来自数据库，格式为 `{key: {desc, value}}`）
  - 结合历史对话为参数赋值
  - 对缺失参数继续追问
  - 将参数写入 `/tmp/copaw_params_{exec_id}.json`
  - 调用参数推送脚本（Redis 进度通知）
  - 参数完整后调用模板渲染 API（`POST http://10.17.55.121:8012/render`）
- 本技能不负责：
  - 再次匹配模板
  - 决定是否走 LLM 自由起草

## 运行时变量

- `session_id` = `os.environ.get("COPAW_SESSION_ID")`
- `user_id` = `os.environ.get("COPAW_USER_ID")`
- `exec_id` — 主流程传入
- `selected_template_id` — 用户已确认的模板 ID
- `selected_template_url` — 模板 HTTP 下载地址（用于渲染 API）
- `selected_template_params_schema` — 来自数据库的 `param_schema_json`（`{key:{desc,value}}` 格式）
- `user_input_text` — 用户当前及历史输入

## param_schema_json 格式说明

数据库返回的 `param_schema_json` 为平铺字典格式：

```json
{
  "contract_effect_year": {
    "desc": "合同生效年份",
    "value": ""
  },
  "company_a": {
    "desc": "甲方公司名称",
    "value": ""
  },
  "company_b": {
    "desc": "乙方公司名称",
    "value": ""
  },
  "contract_amount": {
    "desc": "合同金额（小写数字）",
    "value": ""
  },
  "tax_rate": {
    "desc": "税率",
    "value": ""
  }
}
```

每个字段的 `desc` 是给用户看的中文描述，`value` 是待填入的参数值（初始为空字符串）。

## 强约束

1. 禁止把原始 JSON 代码块直接输出给用户。
2. 只允许向用户输出 Markdown 表单或缺参追问。
3. 参数未补齐前，禁止调用模板渲染接口。
4. 若渲染接口失败，必须把失败结果返回主智能体，让主智能体决定是否回退到 `contract_draft_llm`。
5. 工具调用使用 `selected_template_params_schema`（数据库原始格式）写入文件，不需要转换格式。

## 执行步骤

### Step 1：读取并展示参数结构

从 `selected_template_params_schema`（`{key:{desc,value}}` 格式）中读取所有参数：

1. 遍历每个 key，`desc` 为用户展示名称，`value` 为当前填写值。
2. 识别 `value` 为空字符串 `""` 的字段作为"待填写"字段。

**判断逻辑**：
- 若所有 `value` 均为空 → 需要追问用户
- 若从历史对话中能直接提取部分值 → 先填入，再追问剩余

### Step 2：结合对话填充值

从以下信息中抽取参数值：

- 用户当前输入
- 历史对话（公司名称、金额、日期、服务内容、标的名称等）
- 已上传附件中提到的内容

提取后，将 `selected_template_params_schema` 中对应 key 的 `value` 填入，写入文件：

```bash
write_file(
  path="/tmp/copaw_params_{exec_id}.json",
  content="{param_schema_json_with_filled_values}"
)
```

文件内容示例（部分已填值）：

```json
{
  "contract_effect_year": {"desc": "合同生效年份", "value": "2025"},
  "company_a": {"desc": "甲方公司名称", "value": "北京华夏科技有限公司"},
  "company_b": {"desc": "乙方公司名称", "value": "软通智慧信息技术有限公司"},
  "contract_amount": {"desc": "合同金额（小写数字）", "value": ""},
  "tax_rate": {"desc": "税率", "value": ""}
}
```

### Step 3：调用参数推送脚本（Redis 进度通知）

每次参数结构初始化或更新时，静默调用：

```bash
execute_shell_command(
  "python3 ~/.copaw/active_skills/contract_template_params/scripts/push_params.py \
    /tmp/copaw_params_{exec_id}.json \
    {exec_id} {session_id} {user_id}"
)
```

该脚本自动：
- 解析 `{key:{desc,value}}` 格式
- 统计已填/缺失字段
- 推送 `template_params_required`（有缺失）或 `template_params_completed`（全部完成）

### Step 4：向用户展示参数表单

当仍有未填写的参数时，输出人类可读的 Markdown 表单：

```markdown
请补充以下合同参数：

**合同基本信息**
- 合同生效年份（contract_effect_year）：___（必填）
- 合同生效月份（contract_effect_month）：___（必填）
- 合同生效日期（contract_effect_day）：___（必填）

**甲方信息**
- 甲方公司名称（company_a）：___（必填）
- 甲方法定代表人（company_a_legal）：___（必填）

**乙方信息**
- 乙方公司名称（company_b）：___（必填）

**合同金额**
- 合同金额-小写（contract_amount）：___（必填）
- 合同金额-大写（contract_amount_capital）：___（必填）
- 税率（tax_rate）：___（必填，如：13%）

如您希望跳过模板直接起草，也可以回复：`跳过模板，直接起草`。
```

**禁止输出**：`template_id`、`param_id`、`field_name`、原始 JSON。

### Step 5：缺参补齐后再次写回

用户每次补充参数后：

1. 将用户输入的值更新到 `{key:{desc,value}}` 对应 key 的 `value` 字段
2. 重新写入 `/tmp/copaw_params_{exec_id}.json`
3. 再次调用 `push_params.py`
4. 检查是否仍有 `value` 为空的字段

若仍有缺项，继续追问；若全部填写完成，进入 Step 6。

### Step 6：调用模板渲染接口

当所有参数均已填写后，调用：

```bash
execute_shell_command(
  "python3 ~/.copaw/active_skills/contract_template_params/scripts/render_template.py \
    '{selected_template_url}' \
    /tmp/copaw_params_{exec_id}.json \
    {exec_id} {session_id} {user_id}"
)
```

脚本内部处理：
1. 读取 `/tmp/copaw_params_{exec_id}.json`（`{key:{desc,value}}` 格式）
2. 转换为平铺 JSON 字符串：`{"contract_effect_year":"2025","company_a":"北京华夏科技有限公司",...}`
3. 调用 `POST http://10.17.55.121:8012/render`：
   ```json
   {
     "template_url": "http://xxx/template.docx",
     "text": "{\"contract_effect_year\":\"2025\",\"company_a\":\"北京华夏科技有限公司\",...}"
   }
   ```
4. 推送 `template_render_started` → `template_render_success` / `template_render_failed`

### Step 7：结果返回

#### 渲染成功

```json
{
  "success": true,
  "template_id": "123",
  "template_url": "http://xxx/template.docx",
  "render_result_url": "http://10.156.196.158:9000/yuanti/docxtpl/xxx.docx"
}
```

向用户展示：

```markdown
✅ 合同文件已生成！

[点击下载合同文件](http://10.156.196.158:9000/yuanti/docxtpl/xxx.docx)

如需修改参数，请告知具体字段和新值，我将重新生成。
```

#### 渲染失败

```json
{
  "error": "render api returned success=false: ...",
  "success": false
}
```

返回主智能体，由主智能体决定是否回退到 `contract_draft_llm`。

## 失败处理

| 场景 | 处理方式 |
|------|---------|
| `param_schema_json` 为空 | 返回失败给主智能体，由主智能体决定回退 LLM |
| `push_params.py` 脚本失败 | 记录警告，继续流程（不阻断参数收集） |
| `render_template.py` 失败 | 返回 `error`，主智能体决定是否走 LLM 回退 |
| 用户明确要求"跳过模板" | 立即返回主智能体，触发 LLM 自由起草 |
