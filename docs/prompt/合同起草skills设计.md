# 项目背景

现在开发团队计划开发一款合同审查平台，主要功能模块包含：合同起草（编写）、合同审查、合同对比，这是是一个工业级项目，生成内容需要严谨可靠可实现。

我现在需要完成合同起草流程编排，通过 skills技术进行完成，主智能体、子智能体都是通过 skill 技术完成，实现流程如下：

1.主智能体（Skill）：主要完成子智能体（Skill）任务编排。
2.子智能体（Skill）：主要完成详细任务内容包含脚本等相关内容，数据输入、数据输出等。

# 平台框架使用说明

采用 Copaw 技术平台完成，必要时需修改前后端源代码完成当前需求建设。

# 页面交付说明

前端用户通过对话方式下发任务，如：帮我起草一份采购合同，等相关任务内容描述，后端通过Skill 进行完成，在调用每个子智能体（Skill）都必须通 websocket 技术发送（每个智能体数据的输入、数据的输出）给发送至前端（Web 端），订阅 ID 采用 当前对话 sessionID+登录用户 userID 进行拼接。

# 子智能体skill调用说明

子智能体（Skill）对应的数据输入和数据的输出并必须进行数据库保存（调用 `save_agent_log`，可封装为 skill 或 tool）。

保留当前执行 ID 相应的子智能体运行日志，保存在数据库中，字段如下：

| 规范字段名 | 说明 |
|---|---|
| `runId` | 本次子智能体运行唯一 ID（每次调用时用 `uuid4()` 生成）|
| `execId` | 主执行 ID（主智能体启动时生成，全程透传所有子智能体）|
| `agentID` | 智能体唯一标识（如 `qichacha_query`、`contract_parse`）|
| `inputContent` | 输入内容（JSON 字符串）|
| `outputContent` | 输出内容（JSON 字符串，失败时为 null）|
| `runtime` | 执行耗时（毫秒）|

# 环境变量配置

PlateCompanyName(平台企业名称)：软通智慧

# 名称解释

| 名称 | 说明 |
|---|---|
| `exec_id` | 调用主智能体时生成，对应规范 `execId`，全程透传给所有子智能体 |
| `run_id` | 每个子智能体每次执行时生成，对应规范 `runId`，用于定位单次执行记录 |
| `subscribe_id` | WebSocket 订阅 ID = `sessionID + "_" + userID`，前端用此 ID 订阅推送消息 |

---

# 公共规范速查（字段映射清单）

> 本规范适用于合同起草、合同审查、合同对比所有模块，所有 skill/scripts 开发必须遵守。

## 一、数据库日志字段映射

| 规范字段 | Python 参数名 | 数据类型 | 说明 |
|---|---|---|---|
| `runId` | `run_id` | UUID | 本次子智能体运行唯一 ID，`uuid4()` 生成 |
| `execId` | `exec_id` | UUID | 主执行 ID，主智能体启动时生成，全程透传 |
| `agentID` | `agent_id` | string | 智能体唯一标识，命名规则：`{功能}_{动作}` |
| `inputContent` | `input_content` | TEXT(JSON) | 输入内容，JSON 字符串 |
| `outputContent` | `output_content` | TEXT(JSON) | 输出内容，JSON 字符串；失败时传 `None` |
| `runtime` | `runtime` | int(ms) | 执行耗时，毫秒 |
| —— | `error_msg` | string | 错误信息，失败时填写，成功时省略 |

## 二、save_agent_log 调用模板

```python
import sys, time, uuid, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

session_id = sys.argv[1]
user_id    = sys.argv[2]
exec_id    = sys.argv[3]   # execId，全程透传

run_id     = str(uuid.uuid4())   # runId，本次运行唯一 ID
start_time = time.time()

push(session_id, user_id, "🔍 正在执行：{智能体名称}...", msg_type="progress")

try:
    result = do_business_logic()
    push(session_id, user_id, "✅ {智能体名称}完成", msg_type="result")
    save_agent_log(
        run_id=run_id,
        exec_id=exec_id,
        agent_id="your_agent_id",
        input_content=json.dumps(input_data),
        output_content=json.dumps(result),
        runtime=int((time.time() - start_time) * 1000),
    )
    print(json.dumps(result))
except Exception as e:
    push(session_id, user_id, f"❌ {智能体名称}失败：{e}", msg_type="error")
    save_agent_log(
        run_id=run_id,
        exec_id=exec_id,
        agent_id="your_agent_id",
        input_content=json.dumps(input_data),
        output_content=None,
        runtime=int((time.time() - start_time) * 1000),
        error_msg=str(e),
    )
    sys.exit(1)
```

## 三、WebSocket 订阅 ID 规则

```
subscribe_id = f"{session_id}_{user_id}"
```

前端以 `subscribe_id` 订阅，接收当前用户当前会话所有子智能体的实时推送消息。

## 四、脚本命令行参数规范

所有 skill 的 scripts 脚本前三个参数固定为：

```
python scripts/xxx.py <session_id> <user_id> <exec_id> [业务参数...]
```

## 五、agentID 命名规范

| 模块 | agentID | 说明 |
|---|---|---|
| 合同审查 | `contract_review_main` | 主审查智能体 |
| 合同审查 | `contract_parse` | 合同内容解析 |
| 合同审查 | `contract_extract` | 合同信息提取 |
| 合同审查 | `qichacha_query` | 企查查查询 |
| 合同审查 | `review_record_query` | 历史审查记录查询 |
| 合同审查 | `review_point_query` | 审查点查询（企业/个人）|
| 合同审查 | `product_price_query` | 产品价格查询 |
| 合同审查 | `staff_info_query` | 交付人员查询 |
| 合同审查 | `contract_relation_query` | 合同关联查询 |
| 合同审查 | `law_retrieval` | 法案检索 |
| 合同审查 | `contract_review_llm` | 审查 LLM 分析 |
| 合同起草 | `contract_draft_main` | 主起草智能体 |
| 合同起草 | `contract_template_match` | 模板匹配 |
| 合同起草 | `contract_generate` | 合同生成 |
| 合同对比 | `contract_compare_main` | 主对比智能体 |
| 合同对比 | `contract_diff_analyze` | 差异分析 |

## 六、数据库表结构

```sql
CREATE TABLE agent_logs (
    id             BIGSERIAL PRIMARY KEY,
    run_id         UUID NOT NULL,            -- runId：本次运行唯一 ID
    exec_id        UUID NOT NULL,            -- execId：主执行 ID
    agent_id       VARCHAR(100) NOT NULL,    -- agentID：智能体标识
    input_content  TEXT,                    -- inputContent：输入内容（JSON）
    output_content TEXT,                    -- outputContent：输出内容（JSON）
    runtime        INTEGER,                 -- runtime：执行耗时（ms）
    error_msg      TEXT,                    -- 错误信息（失败时填写）
    extra          JSONB,                   -- 扩展字段
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_logs_exec_id ON agent_logs(exec_id);
CREATE INDEX idx_agent_logs_run_id  ON agent_logs(run_id);
CREATE INDEX idx_agent_logs_created ON agent_logs(created_at DESC);
```



# 需求说明

- 合同模板管理是存储在 PostgreSQL 中，三方系统会提供一个 HTTP API 接口进行合同模板向量检索

- case1：用户通过对话窗口上传自有合同模板文件，解析合同文本内容，发送至 API 接口进行向量检索，返回相似合同模板列表，用户进行确认合同模板，拿到用户确认后的模板 path 地址，通过 websocket 发送至选中后的合同模板 path 地址到前端页面 word 渲染。 解析合同文本内容，发送给大模型上下文进行合同起草。如果未匹配到合同模板就需要采用用户上传的合同模板文本内容提供给大模型进行合同起草。

- case2：如果用户未上传合同模板时，需要通过对话找到合适的合同模板才能进行合同起草，通过对话匹配提取合同模版名称参数，然后调用 API 接口获取合同模板列表，进行用户确认，用户确认合同模板，通过 websocket 发送至选中后的合同模板 path 地址到前端页面 word 渲染。

- 如果用户通过对话未找到合同模板，就根据用户意图进行合同编写。

- 确定好的合同模板，获取到模板内容，进行大模型模板解析提取参数（json 结构）哪些内容需要进行填写如甲方确认和签署、乙方确认和签署、签署日期、授权代表、人民币大写、小写等，然后提取的json 参数，通过 websocket 返回给前端，前端会根据 json 结构进行页面渲染成表单，用户输入后，进行 json 参数赋值，如果json 参数未空的参数，还需要提醒用户不停的完善此 json 参数。如果用户直接发送开始起草等相似命令，就发起大模型起草合同，最终返回一个完整的起草 markdown 合同内容，并继续调用 markdown 转 word 智能体（skill），并调用 word 合同存储智能体保存至服务器，得到保存好的起草合同 word 文件 path 地址，并返回至前端，前端进行 wrod 渲染。


# 公共智能体(skill、tool)

---

## 合同模板匹配智能体（Skill）

### 提示词描述

从用户对话中提取合同模板名称关键词，调用三方模板向量检索 API，返回相似合同模板列表供用户确认。支持两种触发方式：用户上传模板文件（file_attach）和用户通过对话描述（file_chat）。

### 实现方式

在 `scripts/template_match.py` 中调用向量检索 API。

```python
# skills/contract_template_match/scripts/template_match.py
import sys, os, json, time, uuid, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

TEMPLATE_API = os.environ.get("TEMPLATE_API_BASE", "http://localhost:9000")

session_id    = sys.argv[1]
user_id       = sys.argv[2]
exec_id       = sys.argv[3]
query_text    = sys.argv[4]   # 合同模板名称或合同文本内容（用于向量检索）
search_mode   = sys.argv[5] if len(sys.argv) > 5 else "name"  # name / content

run_id     = str(uuid.uuid4())
start_time = time.time()

push(session_id, user_id, "🔍 正在检索匹配合同模板...", msg_type="progress")
save_agent_log(run_id=run_id, exec_id=exec_id, agent_id="contract_template_match",
               input_content=json.dumps({"query": query_text, "mode": search_mode}),
               output_content=None, runtime=0)

try:
    resp = requests.post(
        f"{TEMPLATE_API}/api/template/vector-search",
        json={"query": query_text, "mode": search_mode, "top_k": 10},
        timeout=15,
    )
    resp.raise_for_status()
    result = resp.json()   # { "templates": [...], "total": N }

    save_agent_log(run_id=run_id, exec_id=exec_id, agent_id="contract_template_match",
                   input_content=json.dumps({"query": query_text}),
                   output_content=json.dumps(result),
                   runtime=int((time.time() - start_time) * 1000))
    push(session_id, user_id,
         f"✅ 找到 {result.get('total', 0)} 份相似合同模板", msg_type="result")
    print(json.dumps(result, ensure_ascii=False))
except Exception as e:
    save_agent_log(run_id=run_id, exec_id=exec_id, agent_id="contract_template_match",
                   input_content=json.dumps({"query": query_text}),
                   output_content=None, runtime=int((time.time() - start_time) * 1000),
                   error_msg=str(e))
    push(session_id, user_id, f"❌ 模板检索失败：{e}", msg_type="error")
    print(json.dumps({"templates": [], "total": 0}))
```

### 输入参数

| 参数 | 说明 |
|---|---|
| `query_text` | 检索关键词（file_chat 时为模板名称；file_attach 时为解析的合同文本内容）|
| `search_mode` | `name`（名称检索）/ `content`（向量内容检索）|

### 输出参数

```json
{
  "total": 3,
  "templates": [
    {
      "template_id": "TPL-2024-001",
      "template_name": "IT运维服务采购合同模板",
      "template_type": "采购合同",
      "version": "V2.1",
      "similarity": 0.92,
      "file_path": "/templates/2024/TPL-2024-001.docx",
      "description": "适用于IT运维类服务采购场景，含SLA条款"
    }
  ]
}
```

**后续逻辑：**
- `total > 0`：推送 websocket（type=template_match_list），前端展示模板列表，等待用户确认选择
- `total = 0` 且来源为 `file_attach`：使用用户上传文件作为模板，继续流程
- `total = 0` 且来源为 `file_chat`：提示用户未找到匹配模板，询问是否根据意图直接起草

---

## 合同模板参数提取智能体（Skill）

### 提示词描述

接收用户确认的合同模板全文，通过 LLM 解析模板结构，提取所有需要用户填写的参数（如甲方信息、乙方信息、合同金额、签署日期、授权代表等），返回 JSON 结构的参数清单，推送至前端渲染为表单。

### 提示词

```
你是一名合同模板分析专家。请仔细阅读以下合同模板全文，识别出所有需要用户填写或确认的空白字段，
返回结构化的参数清单（JSON 格式）。

## 合同模板全文
{template_text}

---

识别规则：
1. 空白括号（如【___】、（___）、《___》）内的内容视为待填写字段
2. 固定格式占位符（如"年  月  日"、"人民币（大写）"）视为待填写字段
3. 甲方、乙方的名称、地址、联系人、联系电话、统一社会信用代码均需提取
4. 金额字段需同时提取大写和小写版本
5. 日期字段标注格式要求（如 YYYY-MM-DD）

严格按以下 JSON 格式输出，不要添加任何解释文字：

{
  "template_id": "{template_id}",
  "params": [
    {
      "param_id": "p001",
      "label": "字段显示名称",
      "field_name": "字段英文名（snake_case）",
      "value": null,
      "required": true,
      "type": "text | number | date | select | textarea",
      "placeholder": "填写提示（如：请填写甲方企业全称）",
      "options": null,
      "group": "分组名称（如：甲方信息 / 乙方信息 / 合同条款 / 签署信息）"
    }
  ]
}
```

### 输出参数

```json
{
  "template_id": "TPL-2024-001",
  "params": [
    {
      "param_id": "p001",
      "label": "甲方企业名称",
      "field_name": "party_a_name",
      "value": null,
      "required": true,
      "type": "text",
      "placeholder": "请填写甲方企业全称（与营业执照一致）",
      "options": null,
      "group": "甲方信息"
    },
    {
      "param_id": "p002",
      "label": "合同金额（小写）",
      "field_name": "amount",
      "value": null,
      "required": true,
      "type": "number",
      "placeholder": "请填写合同金额（元）",
      "options": null,
      "group": "合同条款"
    },
    {
      "param_id": "p003",
      "label": "合同金额（大写）",
      "field_name": "amount_cn",
      "value": null,
      "required": true,
      "type": "text",
      "placeholder": "系统将根据小写金额自动填写，也可手动修改",
      "options": null,
      "group": "合同条款"
    },
    {
      "param_id": "p004",
      "label": "签署日期",
      "field_name": "sign_date",
      "value": null,
      "required": true,
      "type": "date",
      "placeholder": "YYYY-MM-DD",
      "options": null,
      "group": "签署信息"
    }
  ]
}
```

**后续逻辑：**
- 推送 websocket（type=template_params_form），携带 `params[]`，前端渲染为分组表单
- 用户填写表单后，前端回传 `params[]`（每项的 `value` 已赋值）
- 若有 `required=true` 且 `value=null` 的字段，AI 持续提醒用户补全
- 用户发出"开始起草"等指令后，触发**合同起草LLM智能体**

---

## 合同起草LLM智能体（Skill）

### 提示词描述

接收合同模板全文及用户填写完成的参数清单，驱动大模型将参数填入模板，补全模板中的空白内容，生成完整的合同正文（Markdown 格式）。生成完成后推送给前端，并调用 Markdown 转 Word 工具生成 Word 文件。

### 提示词

```
你是一名专业的合同起草专家。请根据以下合同模板和用户提供的参数信息，起草一份完整、严谨的合同。

## 合同模板
{template_text}

## 用户填写的参数
{params_json}

---

起草要求：
1. 将参数值准确填入模板对应位置，不得遗漏任何参数
2. 对于用户未填写的非必填字段，根据上下文语义合理补全，或保留原模板提示格式
3. 金额大写自动根据数字金额转换（如 ¥1,500,000 → 人民币壹佰伍拾万元整）
4. 保持合同的法律语言风格，不得随意改变合同条款的实质内容
5. 输出完整的合同正文，使用标准 Markdown 格式：
   - 合同标题用 `# 标题`
   - 各条款用 `## 第X条 条款名称`
   - 正文段落、列表、表格按标准 Markdown 书写
6. 合同末尾必须包含甲乙双方签署区块（签名、日期、盖章行）

只输出 Markdown 格式的合同正文，不要添加任何说明文字。
```

### 实现方式

在 `scripts/contract_generate.py` 中调用 LLM API，生成 Markdown 合同文本，再依次调用 Markdown转Word 工具和文件存储工具。

```python
# skills/contract_draft_llm/scripts/contract_generate.py
import sys, os, json, time, uuid, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

LLM_API_BASE = os.environ.get("LLM_API_BASE", "http://localhost:8000")
LLM_API_KEY  = os.environ.get("LLM_API_KEY", "")
LLM_MODEL    = os.environ.get("LLM_MODEL", "deepseek-v3")

session_id   = sys.argv[1]
user_id      = sys.argv[2]
exec_id      = sys.argv[3]
payload_str  = sys.argv[4]  # JSON：{ template_text, params, template_id }

run_id     = str(uuid.uuid4())
start_time = time.time()

push(session_id, user_id, "✍️ 大模型正在起草合同，请稍候...", msg_type="progress")
save_agent_log(run_id=run_id, exec_id=exec_id, agent_id="contract_generate",
               input_content=payload_str, output_content=None, runtime=0)

try:
    payload       = json.loads(payload_str)
    template_text = payload["template_text"]
    params        = payload["params"]

    prompt = DRAFT_PROMPT_TEMPLATE.format(
        template_text=template_text,
        params_json=json.dumps(params, ensure_ascii=False, indent=2),
    )

    resp = requests.post(
        f"{LLM_API_BASE}/v1/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1},
        timeout=120,
    )
    resp.raise_for_status()
    markdown_content = resp.json()["choices"][0]["message"]["content"]

    save_agent_log(run_id=run_id, exec_id=exec_id, agent_id="contract_generate",
                   input_content=payload_str,
                   output_content=json.dumps({"length": len(markdown_content)}),
                   runtime=int((time.time() - start_time) * 1000))

    push(session_id, user_id, "✅ 合同起草完成，正在生成 Word 文件...", msg_type="progress")
    print(json.dumps({"markdown": markdown_content}, ensure_ascii=False))

except Exception as e:
    save_agent_log(run_id=run_id, exec_id=exec_id, agent_id="contract_generate",
                   input_content=payload_str, output_content=None,
                   runtime=int((time.time() - start_time) * 1000), error_msg=str(e))
    push(session_id, user_id, f"❌ 合同起草失败：{e}", msg_type="error")
    sys.exit(1)
```

### 输出参数

```json
{
  "markdown": "# IT运维服务采购合同\n\n## 第一条 项目概述\n...",
  "exec_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**后续逻辑：**
1. 将 `markdown` 传入 **Markdown转Word工具**，生成 `.docx` 文件
2. 将生成的 `.docx` 路径传入 **Word文件存储工具**，保存至服务器
3. 获得最终 `file_path`，推送 websocket（type=word_render），前端渲染合同 Word 视图

---

## Markdown转Word工具（Python Tool）

> 实现方式：Python 工具函数，代码直接调用，不经过 LLM。

将大模型生成的 Markdown 格式合同文本转换为标准 `.docx` Word 文件。

### 函数签名

```python
def markdown_to_word(
    markdown_content: str,   # Markdown 格式合同正文
    output_filename: str,    # 输出文件名（不含路径，如 "采购合同_草稿.docx"）
    template_path: str = None,  # 可选：使用指定 Word 模板样式
) -> dict:
    """
    Returns:
        { "file_path": "/drafts/2024/xxx.docx", "file_size": 12345 }
    """
```

### 实现说明

使用 `python-docx` 库，按照 Markdown 标题层级自动映射 Word 样式：

| Markdown | Word 样式 |
|---|---|
| `# 标题` | 标题（居中、加粗）|
| `## 第X条` | 一级条款（加粗）|
| `### 子条款` | 二级条款 |
| 普通段落 | 正文 |
| `- 列表项` | 项目符号列表 |
| `| 表格 |` | Word 表格 |

### 输出参数

```json
{
  "file_path": "/drafts/2024/IT运维服务采购合同_草稿_20240315.docx",
  "file_size": 45678,
  "page_count": 8
}
```

---

## Word文件存储工具（Python Tool）

> 实现方式：Python 工具函数，代码直接调用，不经过 LLM。

将生成的合同 Word 文件保存至服务器指定目录，返回永久访问路径。

### 函数签名

```python
def save_contract_file(
    file_path: str,          # 临时文件路径
    contract_type: str,      # 合同类型：draft（起草）/ review（审查）
    exec_id: str,            # 关联主执行 ID
    original_name: str = None,  # 原始文件名（可选）
) -> dict:
    """
    Returns:
        { "saved_path": "/storage/contracts/drafts/...", "file_url": "http://..." }
    """
```

### 存储规则

```
/storage/contracts/
├── drafts/          ← 起草生成的合同
│   └── {YYYY}/{MM}/
│       └── {exec_id}_{filename}.docx
└── reviews/         ← 审查用合同
    └── {YYYY}/{MM}/
        └── {exec_id}_{filename}.docx
```

### 输出参数

```json
{
  "saved_path": "/storage/contracts/drafts/2024/03/550e8400_IT运维服务采购合同_草稿.docx",
  "file_url": "http://localhost:8088/files/contracts/drafts/2024/03/550e8400_IT运维服务采购合同_草稿.docx",
  "file_size": 45678
}
```

---

# Skills流程编排

## 主合同起草智能体（Skill）

### SKILL.md 提示词（编排指令）

````markdown
---
name: contract_draft
description: >
  合同起草主编排智能体。当用户请求起草合同（如"帮我起草一份采购合同"）时调用本 skill，
  按以下流程依次驱动子智能体完成合同起草，最终输出 Word 文件并推送至前端渲染。
version: 1.0.0
---

你是一名合同起草流程编排专家。收到合同起草请求后，**严格按照以下步骤顺序执行**，
不得跳步、不得合并步骤。每步执行完毕通过 websocket 向前端实时推送进度。

公共参数（从当前会话上下文获取）：
- session_id: 当前会话 ID
- user_id: 当前登录用户 ID
- exec_id: 本次起草任务唯一 ID（启动时用 uuid4() 生成，全程共用）

---

## Step 1：获取合同模板

根据用户请求方式判断来源：

### Case A：用户上传了合同模板文件（file_attach）

1. 从消息附件中获取文件路径，调用**合同内容解析工具（Python Tool）**提取文本
2. 调用**合同模板匹配智能体**，传入 `query_text=模板文本内容`、`search_mode=content`
3. 推送 websocket（type=template_match_list），展示相似模板列表
4. AI 回复：「已找到以下相似模板，请确认使用哪份，或直接使用您上传的文件」
5. 用户选择相似模板 → 以选中模板为准；用户选择上传文件 → 以上传文件为准
6. 赋值 `draft_template_path` 和 `draft_template_text`，继续 Step 2

### Case B：用户未上传文件，通过对话描述需求（file_chat）

1. 从用户消息中提取合同类型/模板名称关键词
2. 调用**合同模板匹配智能体**，传入 `query_text=模板名称`、`search_mode=name`
3. 推送 websocket（type=template_match_list），展示匹配模板列表
4. AI 回复匹配结果：
   - 有匹配：展示列表，请用户确认选择
   - 无匹配：AI 回复「未找到匹配模板，将根据您的需求描述直接起草合同」，跳转 Step 3（直接起草模式）
5. 用户确认后，调用**合同内容解析工具**解析选中模板文件，获得 `draft_template_text`
6. 推送 websocket（type=word_render），携带 `draft_template_path`，前端渲染模板预览
7. 继续 Step 2

---

## Step 2：提取模板参数

调用**合同模板参数提取智能体（skill）**：
- 输入：`draft_template_text`（模板全文）
- 输出：`template_params`（参数清单 JSON）
- 推送 websocket（type=template_params_form），携带 `template_params`，前端渲染表单

等待用户填写表单：
- 用户回传参数后，检查所有 `required=true` 的字段是否已有 `value`
- 若有空缺：AI 回复提醒用户补全（列出缺少的字段名），继续等待
- 若全部填写完整，或用户发出「开始起草」「直接起草」等指令，进入 Step 3

---

## Step 3：起草合同正文

调用**合同起草LLM智能体（skill）**：
- 输入：`draft_template_text` + `template_params`（含用户填写的参数值）
- 直接起草模式（无模板）：`draft_template_text` 传空，`template_params` 传用户的需求描述
- 输出：`markdown_content`（Markdown 格式合同正文）
- 推送 websocket（type=progress）：「✍️ 大模型正在起草合同，请稍候...」

---

## Step 4：生成 Word 文件

调用 **Markdown转Word工具（Python Tool）**：
- 输入：`markdown_content`、`output_filename`（根据合同标题自动生成）
- 输出：`docx_path`（临时文件路径）
- 推送 websocket（type=progress）：「📄 正在生成 Word 文件...」

---

## Step 5：保存文件

调用 **Word文件存储工具（Python Tool）**：
- 输入：`docx_path`、`contract_type=draft`、`exec_id`
- 输出：`saved_path`、`file_url`
- 推送 websocket（type=word_render），携带 `saved_path`，前端渲染最终合同 Word 视图

---

## Step 6：AI 总结回复

用自然语言向用户确认起草完成：

> 合同《{合同标题}》起草完成。
>
> **共 {页数} 页**，已保存至服务器，可在右侧 Word 视图中查看和下载。
>
> 如需修改，请告诉我需要调整的内容，我将重新起草。

---

## 异常处理规范

- 模板解析失败：提示用户检查文件格式（仅支持 .docx / .pdf），终止流程
- LLM 起草超时：推送错误提示，提供重试选项
- Word 生成失败：推送错误提示，将 Markdown 内容直接返回给用户作为备用
````




