---
name: contract_draft
description: "【主智能体/唯一入口】合同起草只允许使用本技能：由 contract_draft 统一完成附件识别、模板检索、模板确认、参数补齐、模板渲染与 LLM 自由起草，并在每个关键处理节点推送 Redis 事件。"
metadata:
  {
    "copaw": {
      "emoji": "📋",
      "requires": {}
    }
  }
---

# 合同起草主智能体

`contract_draft` 是合同起草的唯一入口。禁止再调用任何独立的合同子智能体；模板匹配、参数整理、模板渲染都必须由本技能直接调用内部脚本完成。

## 内部脚本

以下脚本均为 `contract_draft` 内部实现，不是独立智能体：

- `~/.copaw/active_skills/contract_draft/scripts/match_by_file.py`
- `~/.copaw/active_skills/contract_draft/scripts/template_match.py`
- `~/.copaw/active_skills/contract_draft/scripts/push_params.py`
- `~/.copaw/active_skills/contract_draft/scripts/render_template.py`
- `~/.copaw/active_skills/contract_draft/scripts/word_gen.py`
- `~/.copaw/active_skills/contract_draft/scripts/push_event.py`

## 可用运行时变量

- `session_id`
- `user_id = os.environ.get("COPAW_USER_ID")`
- `exec_id`
- `file_list = os.environ.get("COPAW_INPUT_FILE_URLS")`
- `user_input_text`
- `selected_template_id`
- `selected_template_url`
- `selected_template_params_schema`
- `render_result_url`

## 事件字段约定

- `skill_name` 是协议字段，固定传 `contract_draft`
- `skill_label` 是展示字段，默认传 `合同起草智能体`
- `stage` 必须在每次事件推送时显式传 `start / running / end / error`
- `event_name` 是前端展示的中文事件标题，必须在每次 `push_event.py` 调用时显式传递

## 强约束

1. 合同起草只能由 `contract_draft` 统一编排，不允许调用其他合同技能名。
2. 每个关键处理阶段都必须推送 Redis，至少包含 `start / running / end` 以及关键 `render_type`。
3. 未上传附件时，不能直接走 LLM，必须先识别合同意图并检索模板。
4. 匹配到模板后，必须先让用户确认，不能直接渲染。
5. 参数未补齐时，不能调用模板渲染。
6. 只有以下场景才能进入自由起草：
   - 未匹配到模板
   - 用户明确跳过模板
   - 模板渲染失败
7. 内部脚本调用、JSON 解析、Redis 推送必须静默执行；只向用户展示确认、追问、结果或必要错误。

## 主流程

### Step 1：生成 `exec_id`

```bash
execute_shell_command("python3 -c \"import uuid; print(uuid.uuid4())\"")
```

### Step 2：推送主流程开始

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft start {exec_id} agent_start '🚀 合同起草流程开始' '{\"user_input_text\":\"{user_input_text}\",\"file_list\":\"{file_list}\"}' '{\"message\":\"合同起草主流程开始\"}' {session_id} {user_id} '' '' '合同起草智能体' '合同起草开始'")
```

### Step 3：检查附件

先读取 `file_list`，然后立即推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} file_list_checked '' '{\"file_list\":\"{file_list}\"}' '{\"has_attachment\":true,\"attachment_count\":1}' {session_id} {user_id} '' '' '合同起草智能体' '附件检查完成'")
```

如果无可用附件，再推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} attachment_missing '' '{\"file_list\":\"{file_list}\"}' '{\"message\":\"未发现可用合同附件\"}' {session_id} {user_id} '' '' '合同起草智能体' '未发现合同附件'")
```

### Step 4：模板检索

#### 有附件

调用内部附件匹配脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/match_by_file.py {session_id} {user_id} {exec_id} '{file_ref}'")
```

#### 无附件

如果用户意图明确，调用语义匹配脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/template_match.py {session_id} {user_id} {exec_id} '{user_input_text}'")
```

如果用户意图不明确，必须推送并追问：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} user_intent_required '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"message\":\"需要用户补充合同类型\"}' {session_id} {user_id} '' '' '合同起草智能体' '需要补充合同类型'")
```

向用户回复：

```text
请问您要起草哪一类合同？例如采购合同、销售合同、租赁合同、服务合同等。
```

### Step 5：处理模板检索结果

如果脚本返回 `need_user_intent = true`，继续追问，不进入后续流程。

如果脚本返回 `total > 0`：

1. 推送 `template_selection_required`
2. 向用户展示模板列表
3. 等待用户确认序号

推送示例：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} template_selection_required '' '{\"template_count\":{template_count}}' '{\"message\":\"需要用户确认模板\"}' {session_id} {user_id} '' '' '合同起草智能体' '等待确认模板'")
```

展示模板时优先输出：

- 模板名称 `title`
- 模板描述 `description`
- 合同类型 `contract_type`
- 分类 `category`
- 模板类型 `template_type`

推荐回复格式：

```markdown
已为您匹配到以下合同模板，请选择要使用的模板：

1. **软件产品销售合同**
   说明：软通智慧作为供货方（乙方）向购买方（甲方）提供软件产品的销售合同
   类型：销售合同 / COMPANY

请回复序号确认；如需跳过模板直接起草，请回复：`0`
```

### Step 6：用户确认模板

如果用户回复 `0`、`跳过模板`、`直接起草`，必须：

1. 推送 `template_skipped`
2. 进入 Step 9 自由起草

如果用户确认模板，必须记录：

- `selected_template_id`
- `selected_template_url`
- `selected_template_params_schema`
- `selected_template_file_path`

并推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} template_selected '' '{\"selected_template_id\":\"{selected_template_id}\"}' '{\"selected_template_url\":\"{selected_template_url}\"}' {session_id} {user_id} '' '' '合同起草智能体' '已确认模板'")
```

### Step 7：参数整理与补齐

用户确认模板后，先把该模板原始的 `param_schema_json` 写入临时文件：

```text
/tmp/copaw_params_{exec_id}.json
```

文件内容直接使用 `selected_template_params_schema` 原始数据，不要转换结构。然后调用内部参数推送脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_params.py /tmp/copaw_params_{exec_id}.json {exec_id} {session_id} {user_id}")
```

该脚本的职责只有两件事：

1. 读取确认模板对应的原始 `param_schema_json`
2. 在 Redis 推送的 `output` 中原样输出 `param_schema_json`

不要把 `param_schema_json` 转成 `params` 数组、表单结构或其他加工格式。

事件语义要求：

1. 必须先推送 `template_params_finished`，表示前端可以读取 `output.param_schema_json` 并开始或刷新动态表单渲染
2. 再根据是否仍有缺参，继续推送 `template_params_required` 或 `template_params_completed`

如果脚本返回有 `missing_fields`：

1. 继续向用户追问参数
2. 每次用户补参后，更新 `/tmp/copaw_params_{exec_id}.json`
3. 重新执行 `push_params.py`

后续追问参数时，由主智能体直接基于原始 `param_schema_json` 中各字段的 `desc` 和 `value` 向用户提问；每次用户补参后，都要把最新 `value` 回写到 `/tmp/copaw_params_{exec_id}.json`，并重新执行 `push_params.py`，让 Redis 中的 `output.param_schema_json` 始终携带用户最新采集到的值，供前端实时刷新表单。

### Step 8：模板渲染

当所有参数补齐后，调用内部渲染脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/render_template.py '{selected_template_url}' /tmp/copaw_params_{exec_id}.json {exec_id} {session_id} {user_id}")
```

如果渲染成功：

1. 记录 `render_result_url`
2. 推送主流程结束事件
3. 返回文件地址给用户

如果渲染失败：

1. 推送 `template_render_failed`
2. 进入 Step 9 自由起草

### Step 9：自由起草

只有以下场景允许进入本步骤：

- 模板未匹配到
- 用户明确跳过模板
- 模板渲染失败

**自由起草强约束：禁止在聊天窗口流式展示起草过程。** 起草必须在后台静默执行：生成完整 Markdown 后保存到本地，调用 `word_gen.py` 生成 docx，获取文件 URL，仅将最终 docx URL 通过 Redis 事件与回复返回给前端。聊天窗口不显示中间 token 流。

进入本步骤前必须推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} llm_draft_started '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"message\":\"开始自由起草合同\"}' {session_id} {user_id} '' '' '合同起草智能体' '开始自由起草'")
```

然后直接在本技能内生成完整合同 Markdown，保存到：

```text
/tmp/copaw_draft_{exec_id}.md
```

使用：

```text
write_file(path="/tmp/copaw_draft_{exec_id}.md", content="{contract_md}")
```

起草要求：

1. 输出必须是完整合同 Markdown，不要附加解释。
2. 至少包含：合同标题、合同主体、标的/服务内容、金额与支付、履行期限、权利义务、违约责任、争议解决、签署页。
3. 若已有模板参数或用户明确信息，必须优先使用，不得遗漏。

然后调用：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/word_gen.py /tmp/copaw_draft_{exec_id}.md ~/.copaw/contracts/drafts {exec_id} {session_id} {user_id}")
```

如果 Word 生成成功，推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} llm_draft_success '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"result_type\":\"docx\",\"result_url\":\"{file_url}\"}' {session_id} {user_id} '' '' '合同起草智能体' '自由起草完成'")
```

如果失败，推送 `llm_draft_failed`，并给用户返回可理解错误。

### Step 10：主流程结束

最终成功后必须推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft end {exec_id} agent_end '✅ 合同起草流程完成' '{\"selected_template_id\":\"{selected_template_id}\",\"final_mode\":\"template_render_or_llm\"}' '{\"result_url\":\"{result_url}\",\"result_type\":\"docx\"}' {session_id} {user_id} '' '' '合同起草智能体' '合同起草完成'")
```

向用户输出：

```text
✅ 合同起草完成！

📄 文件地址：{result_url}

如需继续修改，请直接告诉我需要调整的条款或参数。
```

## 决策矩阵

- 未上传附件 + 意图不明确：先追问合同类型
- 未上传附件 + 意图明确 + 匹配到模板：模板确认 -> 参数补齐 -> 模板渲染
- 未上传附件 + 意图明确 + 未匹配到模板：自由起草
- 已上传附件 + 匹配到模板：模板确认 -> 参数补齐 -> 模板渲染
- 已上传附件 + 未匹配到模板：自由起草
- 任意阶段用户主动跳过模板：自由起草
- 模板渲染失败：自由起草

## 禁止事项

- 禁止再调用 `contract_template_match`
- 禁止再调用 `contract_template_params`
- 禁止再调用 `contract_draft_llm`
- 禁止在未确认模板时直接渲染
- 禁止在缺参时直接渲染
- 禁止在可检索模板时跳过模板阶段
- 禁止自由起草时在聊天窗口流式展示，必须后台静默执行并只返回 docx URL
