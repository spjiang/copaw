---
name: contract_draft_llm
description: "合同起草流程最后阶段，当用户已填写好模板参数（或直接说开始起草）时，根据合同模板和参数生成完整合同正文（Markdown格式），然后生成Word文件。由合同起草主智能体在参数收集完成后调用。"
metadata:
  {
    "copaw": {
      "emoji": "✍️",
      "requires": {}
    }
  }
---

# 合同起草 LLM 智能体

根据模板和参数，生成完整合同正文并输出 Word 文件。

> ⚠️ **执行规范（必须遵守）**
>
> - **Step 2（写文件）和 Step 3（调用脚本）静默执行**，不向用户输出任何描述
> - **只有 Step 1（合同正文）和 Step 4（完成提示）才输出给用户**

> **注意**：本 skill 只使用 CoPaw 内置工具 `write_file` 和 `execute_shell_command`，
> 无需任何自定义 Tool 注册，可直接移植到任意 CoPaw 项目。

## 起草提示词

接收以下变量，生成合同正文：
- `template_text`：合同模板全文（无模板时为空）
- `params_json`：用户填写的参数 JSON
- `user_intent`：用户描述的合同需求（无模板时使用）
- `exec_id`：当前执行 ID（透传）

**你是一名专业合同起草专家。请根据以下信息起草一份完整、严谨的合同：**

### 合同模板
{template_text}

### 用户填写的参数
{params_json}

### 起草要求

1. 将参数值准确填入模板对应位置，不得遗漏任何参数
2. 金额大写自动转换（如 1500000 → 人民币壹佰伍拾万元整）
3. 保持合同的法律语言风格，不得随意改变条款实质内容
4. 使用标准 Markdown 格式输出：
   - 合同标题：`# 标题`
   - 各条款：`## 第X条 条款名称`
5. 合同末尾必须包含甲乙双方签署区块

**只输出 Markdown 格式合同正文，不要添加任何说明文字。**

---

## 执行步骤

### Step 0：推送开始事件

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py LLM模型分析智能体 start {exec_id} progress '✍️ 正在起草合同正文...' '{}' {session_id} {user_id}")
```

### Step 1：生成合同 Markdown 正文

按照上述起草提示词生成完整合同内容，存入变量 `contract_md`。

---

### Step 2：将 Markdown 写入临时文件

使用内置工具 `write_file` 将合同内容保存为临时文件：

```
write_file(
    path="/tmp/copaw_draft_{exec_id}.md",
    content="{contract_md}"
)
```

---

### Step 3：调用 word_gen.py 生成 Word 文件

使用内置工具 `execute_shell_command` 调用独立脚本转换：

```bash
execute_shell_command(
  "python ~/.copaw/active_skills/shared/word_gen.py \
   /tmp/copaw_draft_{exec_id}.md \
   ~/.copaw/contracts/drafts \
   {exec_id} \
   {session_id} \
   {user_id}"
)
```

解析命令输出的 JSON，获取以下字段：
- `file_path`：Word 文件的本地绝对路径
- `file_url`：Word 文件的 HTTP 访问地址
- `filename`：文件名

若输出包含 `"error"` 字段，说明生成失败，直接将 Markdown 内容返回给用户。

---

### Step 4：推送结束事件并输出结果

先推送 end 事件：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/shared/push_event.py LLM模型分析智能体 end {exec_id} progress '✅ 合同正文已生成' '{}' {session_id} {user_id}")
```

将 `file_url` 和 `file_path` 告知用户，并用以下格式总结：

> ✅ 合同《{合同标题}》起草完成！
>
> 📄 Word 文件已生成：`{filename}`
>
> 访问地址：{file_url}
>
> 如需修改，请告诉我需要调整的内容。

---

## 无模板直接起草

若 `template_text` 为空，根据 `user_intent` 自行起草完整合同，包含所有标准合同条款：
- 合同双方信息
- 合同标的和金额
- 履行期限和方式
- 双方权利义务
- 违约责任
- 争议解决
- 其他条款
- 签署区块
