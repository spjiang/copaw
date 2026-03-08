---
name: contract_draft
description: "【主智能体/唯一入口】用户发起合同起草请求时必须优先调用本技能；本技能负责编排模板匹配、参数提取、模板渲染与 LLM 自由起草，最终输出合同文件。"
metadata:
  {
    "copaw": {
      "emoji": "📋",
      "requires": {}
    }
  }
---

# 合同起草主编排智能体

本技能是合同起草的唯一入口，负责把用户输入编排成一条稳定的工业级合同生成链路。

## 核心职责

1. 统一生成 `exec_id`
2. 统一推送主流程 `start -> running -> end`
3. 判断有无附件
4. 判断用户合同意图是否明确
5. 编排调用：
   - `contract_template_match`
   - `contract_template_params`
   - `contract_draft_llm`
6. 输出最终合同结果

## 可用运行时变量

- `session_id`：从系统上下文提取
- `user_id`：来自 `COPAW_USER_ID` 或系统上下文
- `file_list`：`os.environ.get("COPAW_INPUT_FILE_URLS")`
- `user_input_text`：用户当前输入

## 严格约束

1. 内部脚本执行、Redis 推送、JSON 解析必须静默执行。
2. 只有以下三类内容可以直接发给用户：
   - 需要用户确认模板
   - 需要用户补充参数
   - 最终结果或必要错误提示
3. 未上传附件时，不能直接默认走 LLM；必须先尝试识别合同类型并查模板。
4. 匹配到模板后，不能绕过用户确认。
5. 参数未补齐时，不能调用模板渲染。

## 执行主流程

### Step 1：生成 `exec_id`

```bash
execute_shell_command("python3 -c \"import uuid; print(uuid.uuid4())\"")
```

保存为 `exec_id`，后续所有脚本与事件必须透传。

### Step 2：推送主流程开始事件

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py contract_draft start {exec_id} agent_start '🚀 合同起草流程开始' '{\"user_input_text\":\"{user_input_text}\",\"file_list\":\"{file_list}\"}' '{\"message\":\"合同起草主流程开始\"}' {session_id} {user_id}")
```

### Step 3：检查附件

先读取：

```python
file_list = os.environ.get("COPAW_INPUT_FILE_URLS")
```

然后推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py contract_draft running {exec_id} file_list_checked '' '{\"file_list\":\"{file_list}\"}' '{\"has_attachment\":true,\"attachment_count\":1}' {session_id} {user_id}")
```

#### 场景 A：存在附件

调用 `contract_template_match`，并让它走附件匹配脚本：

- 优先取最新一条附件作为 `file_ref`
- 等待 `contract_template_match` 返回模板候选列表

#### 场景 B：没有附件

先判断用户意图是否足够明确：

- 若用户已明确说“采购合同”“销售合同”“租赁合同”等，则调用 `contract_template_match`
- 若用户只说“帮我起草一份合同”，则先追问合同类型

推荐话术：

`请问您要起草哪一类合同？例如采购合同、销售合同、租赁合同、服务合同等。`

### Step 4：调用模板匹配子智能体

#### 有附件

将附件交给 `contract_template_match`：

- 让其调用 `match_by_file.py`
- 解析返回的 `templates`

#### 无附件

将用户意图交给 `contract_template_match`：

- 让其调用 `template_match.py`
- 解析返回的 `templates`

### Step 5：处理模板匹配结果

#### 场景 A：`need_user_intent = true`

继续追问用户合同类型，不进入后续流程。

#### 场景 B：`total > 0`

向用户展示模板列表并要求确认：

```markdown
已为您匹配到以下合同模板，请选择要使用的模板：

| 序号 | 模板名称 | 合同类型 | 分类 |
| --- | --- | --- | --- |
| 1 | 软件采购合同 | 采购 | 软件采购 |

请输入序号选择模板；如需跳过模板并直接起草，请输入 `0`。
```

#### 场景 C：用户输入 `0` 或明确表示“跳过模板，直接起草”

推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py contract_draft running {exec_id} template_skipped '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"message\":\"用户选择跳过模板\"}' {session_id} {user_id}")
```

然后调用 `contract_draft_llm`。

#### 场景 D：`total = 0`

推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py contract_draft running {exec_id} template_not_found '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"message\":\"未匹配到平台模板\"}' {session_id} {user_id}")
```

然后直接调用 `contract_draft_llm`。

### Step 6：模板确认后调用参数子智能体

当用户选择了某个模板后，至少记录以下变量：

- `selected_template_id`
- `selected_template_url`
- `selected_template_params_schema`
- `selected_template_file_path`

然后调用 `contract_template_params`。

### Step 7：处理参数子智能体结果

#### 参数未补齐

继续等待用户填写参数，不结束主流程。

#### 模板渲染成功

直接输出渲染后的合同地址。

#### 模板渲染失败

回退到 `contract_draft_llm`。

### Step 8：调用 LLM 自由起草子智能体

以下场景必须调用 `contract_draft_llm`：

- 用户未上传附件且未匹配到模板
- 用户上传附件但未匹配到模板
- 用户主动跳过模板
- 模板渲染失败

调用时应传入：

- `template_text`：若有模板正文则传入，否则为空
- `template_file_path`：若有本地模板路径则传入，否则为空
- `params_json`：若已有参数文件则传入，否则为空对象
- `user_intent`
- `exec_id`
- `session_id`
- `user_id`

### Step 9：结束主流程

当最终获得 `file_url` 或 `render_result_url` 后，推送结束事件：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py contract_draft end {exec_id} agent_end '✅ 合同起草流程完成' '{\"selected_template_id\":\"{selected_template_id}\",\"final_mode\":\"template_render_or_llm\"}' '{\"result_url\":\"{file_url}\",\"result_type\":\"docx\"}' {session_id} {user_id}")
```

然后再向用户输出：

```text
✅ 合同起草完成！

📄 文件地址：{file_url}

如需继续修改，请直接告诉我需要调整的条款或参数。
```

## 主流程决策矩阵

- 未上传附件 + 意图不明确：先追问合同类型
- 未上传附件 + 意图明确 + 匹配到模板：进入模板确认 -> 参数提取 -> 模板渲染
- 未上传附件 + 意图明确 + 未匹配到模板：进入 `contract_draft_llm`
- 已上传附件 + 匹配到模板：进入模板确认 -> 参数提取 -> 模板渲染
- 已上传附件 + 未匹配到模板：进入 `contract_draft_llm`
- 任意阶段用户主动跳过模板：进入 `contract_draft_llm`
- 模板渲染失败：进入 `contract_draft_llm`

## 失败处理

- 附件解析失败：引导用户重新上传或改为文字描述
- 模板匹配脚本失败：提示稍后重试，并允许走文字模式
- 参数渲染失败：自动回退到 `contract_draft_llm`
- LLM 起草失败：返回明确错误提示，不伪造成功结果
