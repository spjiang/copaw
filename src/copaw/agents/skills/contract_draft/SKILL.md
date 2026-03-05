---
name: contract_draft
description: "合同起草主编排智能体。当用户请求起草合同时调用（如'帮我起草一份采购合同'、'我要写一份服务合同'、'起草合同'等）。负责协调所有子智能体完成完整的合同起草流程，包括模板选择、参数填写和最终生成Word文件。"
metadata:
  {
    "copaw": {
      "emoji": "📋",
      "requires": {}
    }
  }
---

# 合同起草主编排智能体

协调子智能体完成完整合同起草流程，最终输出 Word 文件。

> ⚠️ **执行规范（必须遵守）**
>
> - **所有内部步骤静默执行**，包括：读取参数、生成 exec_id、调用脚本、解析 JSON、提取文本等操作，**一律不向用户输出任何描述**
> - **禁止向用户说明**你在做什么步骤、读取了什么变量、执行了什么命令
> - **只有以下内容才输出给用户**：
>   1. 需要用户回答的问题（如选择模板序号、填写合同参数）
>   2. 最终完成结果（如 Word 文件地址）
>   3. 执行失败时的错误提示

**运行时可用变量**（从系统上下文中直接读取，无需用户输入）：
- `session_id`：从系统提示词中 `当前的session_id: <值>` 提取
- `user_id`：从系统提示词中 `当前的user_id: <值>` 提取
- `exec_id`：本次起草任务的唯一 ID，执行前用 `python3 -c "import uuid; print(uuid.uuid4())"` 生成

**合同类型定义**：
- **采购合同**：软通智慧为甲方/委托方/采购方（公司出钱向外采购）
- **销售合同**：软通智慧为乙方/受托方（公司向客户提供服务/产品）

---

## Step 1：生成执行 ID

```bash
execute_shell_command("python3 -c \"import uuid; print(uuid.uuid4())\"")
```

将输出结果保存为 `exec_id`，全程透传。

生成后立即推送 start 事件：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py 合同起草主智能体 start {exec_id} progress '🚀 合同起草流程开始' '{}' {session_id} {user_id}")
```

---

## Step 2：判断用户输入方式

查看消息内容，判断走哪条路径：

---

### Case A：用户上传了附件

**如何识别并提取文件地址**（按优先级依次检查消息内容）：

#### 方式 1：本地路径（CoPaw 自动注入）

CoPaw 处理附件时会将文件保存到本地，并在消息中追加：
```
用户上传文件，已经下载到 /Users/xxx/.copaw/file_store/uploads/20260305_abc_合同.docx
```
用正则 `用户上传文件，已经下载到\s+(\S+)` 提取路径，赋值给 `file_ref`。

#### 方式 2：HTTP 下载地址

若消息中没有本地路径注入，检查是否包含 HTTP 下载地址，例如：
```
http://127.0.0.1:8088/api/files/download/20260305_abc_合同.docx
```
或用户直接提供的文件 URL。将该 URL 赋值给 `file_ref`。

> **两种格式 `match_by_file.py` 均支持**：
> - 本地路径 → 直接读取文件
> - HTTP URL → 脚本自动下载到临时目录后处理，完成后自动清理

#### A-1：调用文件匹配脚本

脚本内部完成：（下载文件 →）读取文件文本 → 识别合同类型 → TF-IDF 相似度匹配模板库：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_template_match/scripts/match_by_file.py {session_id} {user_id} {exec_id} '{file_ref}'")
```

> **匹配逻辑**：
> 1. 若上传文件路径与模板库中某文件完全一致 → **精准命中**（`matched_file: true`）
> 2. 否则提取文件全文 → 识别合同类型 → TF-IDF 相似度排序 → 返回 top-5

#### A-2：根据匹配结果处理

解析脚本输出的 JSON：

**精准命中（`matched_file: true`）**：
- 告知用户："识别到您上传的正是模板库中的 **{template_name}**，将直接以此为模板起草"
- 获取模板全文（含占位符）：
  ```bash
  execute_shell_command("curl -s http://localhost:9000/api/template/{template_id}/content")
  ```
- 解析 JSON，取 `content` 字段，设置 `draft_template_text = content`

**相似匹配（`matched_file: false`，`total > 0`）**：
- 展示模板列表（Markdown 表格：序号、模板名称、合同类型、相似度）
- 提问："以上是相似模板，请选择序号；或输入 **0** 直接用您上传的文件作为起草依据"
- 用户选序号 N → 获取第 N 个模板内容，设置 `draft_template_text`
- 用户选 0 → 读取上传文件全文作为模板：
  ```bash
  execute_shell_command("python3 -c \"from docx import Document; d=Document('{local_path}'); print('\\n'.join(p.text for p in d.paragraphs if p.text.strip()))\"")
  ```

**无匹配（`total = 0`）**：
- 告知"未找到相似模板，将直接基于您上传的文件起草"
- 读取上传文件全文作为 `draft_template_text`

---

### Case B：用户通过文字描述需求（无附件）

1. 从用户描述提取关键词（如"运维服务采购"、"向客户提供技术开发"等）
2. 调用模板检索脚本（不传 `contract_type`，由脚本自动识别）：
   ```bash
   execute_shell_command("python3 ~/.copaw/active_skills/contract_template_match/scripts/template_match.py {session_id} {user_id} {exec_id} '{query_text}'")
   ```
3. **有结果（`total > 0`）**：
   - 展示模板表格，等待用户选择序号
   - 用户选择后获取模板内容：
     ```bash
     execute_shell_command("curl -s http://localhost:9000/api/template/{template_id}/content")
     ```
   - 设置 `draft_template_text = content`
4. **无结果（`total = 0`）**：
   - 告知"未找到匹配模板，将根据您的需求直接起草"
   - `draft_template_text = ""`

---

## Step 3：提取模板参数

若 `draft_template_text` 非空，调用 **contract_template_params** skill，传入：
- `template_text`：模板全文（即 `draft_template_text`）
- `exec_id`：当前执行 ID
- `session_id`：当前会话 ID

skill 会分析模板中的 `【   】`、`（   ）` 等占位符，**只以 Markdown 格式**展示参数表单给用户（不输出 raw JSON）：

```
请填写以下合同参数：

**甲方信息**
- 甲方企业名称：___（必填）
- 统一社会信用代码：___（必填）

**乙方信息**
- 乙方企业名称：___（必填）

**合同条款**
- 合同金额（元）：___（必填）
- 签署日期：___（必填，格式 YYYY-MM-DD）
- 甲方授权代表：___（必填）
- 乙方授权代表：___（必填）
```

等待用户填写，将回复记录到 `filled_params`，检查必填字段是否完整。
用户发出"开始起草"/"直接起草"/"跳过"时，进入 Step 4。

若 `draft_template_text` 为空，跳过此步直接进入 Step 4。

> `contract_template_params` 内部会将参数 JSON 写入文件并调用 `push_params.py` 推送至 Redis，主智能体无需重复执行。

---

## Step 4：起草合同正文

调用 **contract_draft_llm** skill，传入：
- `draft_template_text`：模板全文（为空则纯 LLM 起草）
- `filled_params`：用户填写的参数
- `user_intent`：用户原始描述（无模板时使用）
- `exec_id`：执行 ID（透传）

---

## Step 5：生成 Word 文件

由 `contract_draft_llm` skill 内部完成（写入临时 Markdown 文件后调用 `word_gen.py` 转换）。
从 skill 输出中获取：
- `file_path`：Word 文件本地路径
- `file_url`：Word 文件访问地址

---

## Step 6：输出结果

在输出最终文字结果前，推送 end 事件：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py 合同起草主智能体 end {exec_id} contract_draft_task_end '✅ 合同起草流程完成' '{\"file_url\":\"{file_url}\",\"filename\":\"{filename}\"}' {session_id} {user_id}")
```

```
✅ 合同《{合同标题}》起草完成！

📄 Word 文件已生成：{filename}
访问地址：{file_url}

如需修改，请告诉我需要调整的内容。
```

---

## 异常处理

| 场景 | 处理方式 |
|---|---|
| 消息中无文件路径注入 | 告知"附件处理失败，请重新上传或描述合同需求" |
| 模板 API 不可用（curl 失败） | 告知"模板服务暂时不可用，将根据您的描述直接起草" |
| 脚本执行失败 | 输出错误信息，询问是否改用文字描述模式 |
| Word 生成失败 | 将 Markdown 合同内容直接返回，提示可手动复制 |
| 用户中途取消 | 礼貌确认并停止流程 |
