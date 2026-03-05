---
name: contract_template_match
description: "合同起草时，基于用户描述或上传合同内容进行模板相似匹配，返回最相似模板列表供用户选择。匹配过程不需要外部传入合同类型，合同类型由脚本根据内容自动识别。"
metadata:
  {
    "copaw": {
      "emoji": "📄",
      "requires": {}
    }
  }
---

# 合同模板匹配智能体

从真实合同模板库检索最相似的模板。

**运行时可用的变量**（由主智能体传入）：`session_id`、`user_id`、`exec_id`、`query_text`

> ⚠️ **执行规范（必须遵守）**
>
> - Step 1（推送开始）和 Step 3（推送结束）**静默执行**，不向用户输出任何内容
> - 只有 Step 4（展示结果）才输出给用户

## 执行步骤

### Step 1：调用模板检索脚本

脚本内部自动完成 Redis start/end 推送，无需额外调用 push_event.py。

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_template_match/scripts/template_match.py {session_id} {user_id} {exec_id} \"{query_text}\"")
```

**参数说明**：

| 参数 | 说明 | 取值 |
|---|---|---|
| `query_text` | 检索内容：用户需求描述，或从上传文件提取的文本 | 字符串 |

**合同类型识别**：
- 本 skill 不再接收 `contract_type` 输入参数。
- 由脚本基于文本内容自动识别并返回 `detected_contract_type`（如采购/销售）。

解析脚本 stdout 的 JSON 结果，保存 `match_result`（包含 `templates[]`、`total`、`detected_contract_type`）。

### Step 2：向用户展示结果

## 输出处理

- `total > 0`：以 Markdown 表格展示模板列表，格式如下：

  ```
  找到以下 {N} 份相似合同模板，请选择：

  | 序号 | 模板名称 | 合同类型 | 分类 |
  |---|---|---|---|
  | 1 | {template_name} | {contract_type} | {sub_type} |
  ```

  提示用户："请输入序号选择模板，或输入 0 直接起草"

- `total = 0`：告知用户"未找到匹配模板，将根据您的描述直接起草合同"
