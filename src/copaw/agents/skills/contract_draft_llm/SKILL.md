---
name: contract_draft_llm
description: "【LLM自由起草子智能体】仅供 contract_draft 主流程内部调用：当用户跳过模板、未匹配到模板、或模板渲染失败时，负责使用大模型生成完整合同并输出 Word 文件。"
metadata:
  {
    "copaw": {
      "emoji": "✍️",
      "requires": {}
    }
  }
---

# 合同自由起草智能体

说明：本技能在业务上扮演 `contract_template_llm` 的角色，当前目录名保留为 `contract_draft_llm`，以兼容现有项目引用路径。

## 适用场景

以下任一场景必须调用本技能：

1. 未上传附件且未匹配到平台模板
2. 已上传附件但未匹配到平台模板
3. 用户明确表示“跳过模板，直接起草”
4. 模板渲染失败，需要回退

## 运行时变量

- `session_id`
- `user_id`
- `exec_id`
- `template_text`：可为空
- `template_file_path`：可为空
- `params_json`：可为空对象
- `user_intent`

## 强约束

1. 内部写文件、脚本调用、事件推送必须静默执行。
2. 最终必须返回结构化结果，不允许只说“已完成”。
3. 若具备本地 `.docx` 模板路径和参数文件，可优先尝试模板填充保留样式。
4. 若模板填充不可用，则必须回退为 Markdown -> Word。

## 起草原则

你是一名专业合同起草专家。请根据模板、参数和用户需求，生成完整、严谨、可交付的合同正文。

### 起草要求

1. 若存在 `template_text`，尽量保持模板条款结构与法律表达风格。
2. 若存在 `params_json`，必须优先使用参数值，不得遗漏必填信息。
3. 若无模板，则根据 `user_intent` 自主生成完整合同。
4. 输出必须为 Markdown 正文，不要附加解释性文字。
5. Markdown 至少包含：
   - `# 合同标题`
   - `##` 级条款标题
   - 合同主体信息
   - 标的/服务内容
   - 金额与付款方式
   - 履行期限
   - 双方权利义务
   - 违约责任
   - 争议解决
   - 签署页

## 执行步骤

### Step 1：推送开始事件

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py contract_draft_llm start {exec_id} agent_start '✍️ 正在进行合同自由起草' '{\"user_intent\":\"{user_intent}\"}' '{\"message\":\"开始自由起草合同\"}' {session_id} {user_id}")
```

### Step 2：推送起草中事件

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py contract_draft_llm running {exec_id} llm_draft_started '' '{\"contract_type\":\"{contract_type_or_empty}\",\"user_intent\":\"{user_intent}\"}' '{\"message\":\"正在生成合同正文\"}' {session_id} {user_id}")
```

### Step 3：生成合同 Markdown

根据当前输入生成完整合同 Markdown，保存到变量 `contract_md`。

### Step 4：写入临时文件

```text
/tmp/copaw_draft_{exec_id}.md
/tmp/copaw_params_{exec_id}.json
```

使用：

```text
write_file(path="/tmp/copaw_draft_{exec_id}.md", content="{contract_md}")
write_file(path="/tmp/copaw_params_{exec_id}.json", content="{params_json}")
```

### Step 5：优先尝试模板填充

若同时满足以下条件：

- `template_file_path` 非空
- `template_file_path` 以 `.docx` 结尾
- `/tmp/copaw_params_{exec_id}.json` 已存在

则先尝试：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/template_fill.py '{template_file_path}' /tmp/copaw_params_{exec_id}.json ~/.copaw/contracts/drafts {exec_id} {session_id} {user_id}")
```

若脚本返回结果中不含 `error`，直接以该结果作为最终输出。

### Step 6：回退为 Markdown 转 Word

若 Step 5 未执行或失败，则调用：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/word_gen.py /tmp/copaw_draft_{exec_id}.md ~/.copaw/contracts/drafts {exec_id} {session_id} {user_id}")
```

解析其 stdout JSON，至少取得：

- `file_path`
- `file_url`
- `filename`

### Step 7：若 Word 生成仍失败

如果模板填充和 Markdown 转 Word 都失败，则：

1. 推送错误事件
2. 将 `contract_md` 作为文本结果返回主智能体
3. 让主智能体决定如何向用户展示

### Step 8：推送结束事件

若生成成功，推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py contract_draft_llm end {exec_id} agent_end '✅ 合同自由起草完成' '{\"user_intent\":\"{user_intent}\"}' '{\"result_type\":\"docx\",\"result_url\":\"{file_url}\",\"filename\":\"{filename}\"}' {session_id} {user_id}")
```

## 返回结构要求

### 成功

```json
{
  "success": true,
  "result_type": "docx",
  "file_path": "/abs/path/to/file.docx",
  "file_url": "http://xxx/file.docx",
  "filename": "file.docx"
}
```

### 回退为文本

```json
{
  "success": false,
  "result_type": "markdown",
  "markdown": "# 合同标题\n..."
}
```

## 失败处理

- `template_fill.py` 失败：继续走 `word_gen.py`
- `word_gen.py` 失败：返回 Markdown 文本
- 起草内容为空：视为失败，不允许返回空文档
