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
- `user_id`
- `exec_id`
- `file_list`
- `user_input_text`
- `selected_template_id`
- `selected_template_url`
- `selected_template_params_schema`
- `render_result_url`

关键参数兼容规则：

- `session_id`：优先取对方平台 `os.environ.get("COPAW_SESSION_ID")`，取不到再回退到本系统传入的运行时参数或命令行参数
- `file_list`：优先取对方平台 `os.environ.get("COPAW_INPUT_FILE_URLS")`，取不到再回退到本系统传入的附件参数
- `user_id`：优先取对方平台 `os.environ.get("COPAW_USER_ID")`，取不到再回退到本系统传入的运行时参数或命令行参数

## 事件字段约定

- `skill_name` 是协议字段，固定传 `contract_draft`
- `skill_label` 是展示字段，默认传 `合同起草智能体`
- `stage` 必须在每次事件推送时显式传 `start / running / end / error`
- `event_name` 是前端展示的中文事件标题，必须在每次 `push_event.py` 调用时显式传递
- `event_category` 是事件分类字段，固定分为：
  - `data`：用于前端拿数据并刷新界面
  - `status`：用于向用户展示流程状态
  - `result`：用于表示阶段性结果或最终结果
- 渲染或产物结果必须尽量补齐以下字段：
  - `render_mode = preview | final`
  - `generation_mode = template_render | llm_draft`
  - `result_type = docx`

## 强约束

1. 合同起草只能由 `contract_draft` 统一编排，不允许调用其他合同技能名。
2. 每个关键处理阶段都必须推送 Redis，至少包含 `start / running / end` 以及关键 `render_type`。
3. 未上传附件时，不能直接走 LLM，必须先识别合同意图并检索模板。
4. 匹配到模板后，必须先让用户确认，不能直接渲染。
5. 参数未补齐时，不能直接进行正式模板渲染；只有用户明确选择 `preview_render` 时，才允许先生成预览稿。
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
2. 在 Redis 推送的 `output` 中原样输出 `param_schema_json`，并附带可直接渲染表格的 `param_table` 与可直接回复给用户的 `param_table_markdown`

不要把 `param_schema_json` 转成 `params` 数组、表单结构或其他加工格式。

事件语义要求：

1. 必须先推送 `template_params_finished`，表示前端可以读取 `output.param_schema_json`、`output.param_table` 和 `output.param_table_markdown`，并开始或刷新动态表单 / 参数表格渲染
2. 再根据是否仍有缺参，继续推送 `template_params_required` 或 `template_params_completed`

如果脚本返回有 `missing_fields`：

1. 不要直接继续机械追问，必须先向用户展示当前参数总览，优先使用表格化方式说明“参数名称 / 填写说明 / 当前值 / 状态”
2. 必须主动询问用户下一步意愿，并将意愿归类为以下三种之一：
   - `continue_fill`：继续补充剩余参数
   - `preview_render`：按当前已填写参数先生成预览稿
   - `switch_to_llm`：放弃模板渲染，转自由起草
3. 如果用户表达不明确，必须继续追问，直到意愿明确后再进入后续分支
4. 每次用户补参后，更新 `/tmp/copaw_params_{exec_id}.json`
5. 每次参数文件更新后，都必须重新执行 `push_params.py`

后续补参时，默认优先采用“批量收集”而不是“一次只问一个字段”：

1. 主智能体先基于 `output.param_table_markdown` 在聊天对话框中展示参数总览表；如果该字段不存在，再退回基于 `output.param_table.rows` 自行生成 Markdown 表格
2. 引导用户一次填写多个字段
3. 用户如果只愿意逐条回答，才退回单字段追问模式
4. 每次用户补参后，都要把最新 `value` 回写到 `/tmp/copaw_params_{exec_id}.json`，并重新执行 `push_params.py`，让 Redis 中的 `output.param_schema_json`、`output.param_table` 与 `output.param_table_markdown` 始终携带用户最新采集到的值，供前端实时刷新表单，并供聊天窗口同步展示

批量填写时，允许用户使用以下任一格式：

- Markdown 表格
- JSON 对象
- 多行键值对，例如 `甲方名称=软通智慧`
- 自然语言批量描述，例如“甲方是软通智慧，乙方是某某公司，签约日期是 2026-03-08”

批量填写解析要求：

1. 必须优先尝试从用户一轮回复中提取多个字段，不要默认只更新一个值
2. 必须结合字段名、字段说明 `desc`、上下文语义判断“用户这句话对应哪个参数”
3. 对高置信度字段直接回写
4. 对低置信度或存在歧义的字段，集中列出后一次性请用户确认，不要拆成很多轮
5. 每次完成一轮解析后，都要重新推送 `template_params_finished`

对话框展示要求：

1. 每次出现 `template_params_finished` 后，聊天窗口都必须展示最新的 Markdown 参数表
2. 表格中必须同时展示“已填写”和“待填写”项，不能只列缺失字段
3. 当用户补充了一批参数后，必须重新展示更新后的完整表格，而不是只回复“已更新”
4. 如果字段很多，可以优先展示完整表格；若确实过长，可先展示前若干项并明确说明“其余字段已同步到右侧参数总表”

缺参时推荐用户提示模板：

````markdown
我已为您整理出当前合同模板需要填写的参数总表，并同步了最新数据。

建议您优先直接按表格一次填写多个字段，这样会比一问一答更快。

{param_table_markdown}

当前仍缺少：
{missing_fields_human_readable}

您可以直接这样回复我：

```text
甲方名称=xxx
乙方名称=xxx
签署日期=2026-03-08
付款方式=验收后7个工作日内付款
```

您希望我下一步怎么处理？

1. 继续补充剩余参数
2. 按当前已填内容先生成预览稿
3. 放弃模板渲染，转自由起草

请直接回复 `1`、`2` 或 `3`，也可以直接告诉我您想怎么做。
````

用户意愿识别规则：

- 如果用户回复 `1`、`继续补充`、`继续填写`、`补参数`、`继续完善`，归类为 `continue_fill`
- 如果用户回复 `2`、`先预览`、`先渲染看看`、`先出一版`、`按当前内容生成`，归类为 `preview_render`
- 如果用户回复 `3`、`自由起草`、`重新起草`、`不要模板了`、`直接起草`，归类为 `switch_to_llm`

固定对话要求：

- 不要自由发挥生成多套问法，优先使用“状态说明 + Markdown 参数总表 + 缺失字段摘要 + 选项确认”的固定模板
- 每次只做一轮明确引导，等用户表达意愿后再进入下一步
- 若用户表达混杂，例如“先预览一下，不行就直接起草”，优先追问确认当前这一步是 `preview_render` 还是 `switch_to_llm`

各分支处理规则：

- `continue_fill`：优先继续批量收集；只有当用户明确要求“一个个问”或当前字段歧义过大时，才逐项追问；每采集到一轮新参数，都必须回写文件并重新执行 `push_params.py`
- `preview_render`：允许在参数未补齐时进入预览渲染；但必须明确告知用户这是预览稿，不是最终定稿
- `switch_to_llm`：进入 Step 9 自由起草；若已有用户已填写的参数，必须作为自由起草的重要输入上下文继续使用；同时必须记录 `draft_entry_reason`

### Step 8：模板渲染

当所有参数补齐后，调用内部渲染脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/render_template.py '{selected_template_url}' /tmp/copaw_params_{exec_id}.json {exec_id} {session_id} {user_id}")
```

如果用户在缺参时明确选择 `preview_render`，允许先按当前已填参数生成预览稿，此时调用：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/render_template.py '{selected_template_url}' /tmp/copaw_params_{exec_id}.json {exec_id} {session_id} {user_id} preview")
```

预览渲染对用户的提示要求：

```text
我会先按您当前已填写的信息生成一份预览稿，未填写的字段可能保持为空或以模板默认占位呈现。您确认后，我可以继续帮您补齐参数并生成正式版。
```

如果渲染成功：

1. 记录 `render_result_url`
2. 若本次为正式渲染，推送主流程结束事件
3. 返回文件地址给用户

如果本次为预览渲染成功：

1. 返回预览文件地址给用户
2. 明确告知该结果是预览稿，不是最终定稿
3. 继续询问用户是：
   - 继续补齐参数后生成正式版
   - 保持当前内容直接转自由起草
   - 结束本轮预览

预览稿返回给前端时，必须保证结果中能区分：

- `render_mode = preview`
- `generation_mode = template_render`
- `result_type = docx`

如果渲染失败：

1. 推送 `template_render_failed`
2. 告知用户可选择继续补参重试，或转自由起草
3. 只有在用户明确选择放弃模板时，才进入 Step 9 自由起草

### Step 9：自由起草

只有以下场景允许进入本步骤：

- 模板未匹配到
- 用户明确跳过模板
- 模板渲染失败

**自由起草强约束：禁止在聊天窗口流式展示起草过程。** 起草必须在后台静默执行：生成完整 Markdown 后保存到本地，调用 `word_gen.py` 生成 docx，获取文件 URL，仅将最终 docx URL 通过 Redis 事件与回复返回给前端。聊天窗口不显示中间 token 流。

进入自由起草前，必须先明确并记录 `draft_entry_reason`，只能取以下值之一：

- `template_not_found`
- `template_skipped_by_user`
- `template_render_failed`
- `user_selected_llm_after_partial_fill`

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
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/word_gen.py /tmp/copaw_draft_{exec_id}.md ~/.copaw/contracts/drafts {exec_id} {session_id} {user_id} {draft_entry_reason}")
```

如果 Word 生成成功，推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} llm_draft_success '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"result_type\":\"docx\",\"result_url\":\"{file_url}\"}' {session_id} {user_id} '' '' '合同起草智能体' '自由起草完成'")
```

自由起草结果返回给前端时，必须保证结果中能区分：

- `render_mode = final`
- `generation_mode = llm_draft`
- `result_type = docx`
- `draft_entry_reason`

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
- 未上传附件 + 意图明确 + 匹配到模板：模板确认 -> 参数补齐 -> 正式渲染或预览渲染
- 未上传附件 + 意图明确 + 未匹配到模板：自由起草
- 已上传附件 + 匹配到模板：模板确认 -> 参数补齐 -> 正式渲染或预览渲染
- 已上传附件 + 未匹配到模板：自由起草
- 任意阶段用户主动跳过模板：自由起草
- 模板渲染失败：由用户选择继续补参重试或转自由起草

## 禁止事项

- 禁止再调用 `contract_template_match`
- 禁止再调用 `contract_template_params`
- 禁止再调用 `contract_draft_llm`
- 禁止在未确认模板时直接渲染
- 禁止在缺参时未经用户同意直接进入正式渲染
- 禁止在可检索模板时跳过模板阶段
- 禁止自由起草时在聊天窗口流式展示，必须后台静默执行并只返回 docx URL
