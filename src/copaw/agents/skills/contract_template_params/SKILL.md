---
name: contract_template_params
description: "合同起草流程中，当用户已选定合同模板后，解析模板内容，提取所有需要用户填写的空白字段（甲方信息、乙方信息、金额、日期、授权代表等），以JSON结构返回参数表单。由合同起草主智能体在确认模板后调用。"
metadata:
  {
    "copaw": {
      "emoji": "📝",
      "requires": {}
    }
  }
---

# 合同模板参数提取智能体

解析合同模板，提取所有待填写字段，生成参数表单。**仅向用户展示 Markdown 格式表单，禁止输出 raw JSON。**

**运行时可用的变量**（由主智能体传入）：`template_text`、`exec_id`、`session_id`

> ⚠️ **输出规范（必须遵守）**
>
> - **禁止在聊天窗口输出** JSON 代码块、`{...}` 结构或 `template_id`、`params` 等机器格式
> - **只向用户输出** Markdown 格式的参数填写表单（见下方示例）
> - JSON 仅用于内部 write_file 和 push_params，不展示给用户

## 执行步骤

### Step 1：分析模板，生成 JSON（内部使用）

接收合同模板全文（变量 `template_text`），识别所有空白字段，按以下 JSON 结构在内心生成（不输出）：

```json
{
  "template_id": "TPL-xxx",
  "params": [
    {
      "param_id": "p001",
      "label": "字段名称",
      "field_name": "snake_case字段名",
      "value": null,
      "required": true,
      "type": "text | number | date | select | textarea",
      "placeholder": "填写提示",
      "options": null,
      "group": "分组（甲方信息 | 乙方信息 | 合同条款 | 签署信息）"
    }
  ]
}
```

**识别规则**：
1. 【___】、（___）、《___》等空白括号内的内容 → 待填写字段
2. "年  月  日" 格式 → `date` 类型字段
3. "人民币（大写）___" → `text` 类型，`field_name=amount_cn`
4. 金额数字 "¥___" → `number` 类型，`field_name=amount`
5. 甲方/乙方的名称、地址、电话、信用代码、法人 → 分别提取，`group=甲方信息/乙方信息`
6. 违约金比例、付款天数等数值 → `number` 类型
7. 授权代表签字行 → `text` 类型，`group=签署信息`

### Step 2：静默写入文件并推送（不输出）

使用 `write_file` 将 JSON 写入：
```
write_file(path="/tmp/copaw_params_{exec_id}.json", content="{生成的JSON字符串}")
```

使用 `execute_shell_command` 调用推送脚本：
```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_template_params/scripts/push_params.py /tmp/copaw_params_{exec_id}.json {exec_id} {session_id}")
```

**以上两步静默执行，不向用户输出任何内容。**

### Step 3：只输出 Markdown 参数表单

**仅输出**以下格式的人类可读表单，禁止附带 JSON：

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

请按上述项逐一填写，完成后回复「开始起草」或「直接起草」。
```

**不要输出** `template_id`、`params`、`param_id`、`field_name` 等 JSON 字段，不要输出 ```json 代码块。
