# 项目背景

现在开发团队计划开发一款合同审查平台，主要功能模块包含：合同起草（编写）、合同审查、合同对比，这是是一个工业级项目，生成内容需要严谨可靠可实现。

我现在需要完成合同起流程编排，通过 skills技术进行完成，主智能体、子智能体都是通过 skill 技术完成，实现流程如下：

1.主智能体（Skill）：主要完成子智能体（Skill）任务编排。
2.子智能体（Skill）：主要完成详细任务内容包含脚本等相关内容，数据输入、数据输出等。

# 平台框架使用说明

采用 Copaw 技术平台完成，必要时需修改前后端源代码完成当前需求建设。

# 页面交付说明

前端用户通过对话方式下发任务，如：我要合同对比，等相关任务内容描述，后端通过Skill 进行完成，在调用每个子智能体（Skill）都必须通 websocket 技术发送（每个智能体数据的输入、数据的输出）给发送至前端（Web 端），订阅 ID 采用 当前对话 sessionID+登录用户 userID 进行拼接。

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

三、合同对比
1、用户手动上传两个合同文件
2、用户对话，帮我找出来xxx项目的合同；
a)AI回复：好的，以帮您找到xxx项目的【xxx合同】，请上传您想对比的合同，我来给您进行合同差异分析

b)通过对话找到的合同对比，对比结果出来后，AI回复：是否需要将您上传的合同文件，替换已找到的文件？【是】【否】
用户选择【是】，AI回复：好的已将原文件替换【前往查看】


# 公共智能体(skill、tool)

## 一、公共共享模块（已实现，复用）

以下模块位于 `src/copaw/agents/skills/shared/`，**合同对比模块直接复用，无需重新开发**：

| 文件 | 功能 |
|---|---|
| `shared/push.py` | WebSocket 实时推送（调用 `/api/console/internal-push`） |
| `shared/db.py` | 智能体执行日志持久化（`save_agent_log`） |

---

## 二、Tools（Python 工具函数）

### Tool 1：`docx_extract` — 文档文本提取

| 项目 | 说明 |
|---|---|
| 文件路径 | `src/copaw/agents/tools/docx_extract.py` |
| 函数签名 | `async def docx_extract(file_path: str, **kwargs) -> ToolResponse` |
| 功能 | 从 `.docx` / `.pdf` / `.txt` / `.md` 文件中提取纯文本，返回结构化文本内容 |
| 输入 | `file_path`：本地文件绝对路径 |
| 输出 JSON | `{ "text": "...", "page_count": N, "word_count": N, "file_type": "docx" }` |
| 异常处理 | 不支持的格式返回 `{ "error": "unsupported file type" }` |

**注册位置**：`src/copaw/agents/tools/__init__.py` 和 `react_agent.py`

---

### Tool 2：`contract_diff` — 合同差异分析

| 项目 | 说明 |
|---|---|
| 文件路径 | `src/copaw/agents/tools/contract_diff.py` |
| 函数签名 | `async def contract_diff(text_a: str, text_b: str, label_a: str = "合同A", label_b: str = "合同B", **kwargs) -> ToolResponse` |
| 功能 | 对两份合同文本进行逐段差异对比，生成结构化差异报告（Markdown 格式） |
| 输入 | `text_a`：第一份合同文本；`text_b`：第二份合同文本；`label_a/b`：显示标签 |
| 输出 JSON | `{ "diff_markdown": "...", "summary": { "added": N, "removed": N, "changed": N }, "sections": [...] }` |
| 实现方式 | 使用 Python `difflib.unified_diff` 做段落级差异，结合 LLM 对关键差异做语义归纳 |

**注册位置**：`src/copaw/agents/tools/__init__.py` 和 `react_agent.py`

---

### Tool 3：`contract_file_replace` — 合同文件替换

| 项目 | 说明 |
|---|---|
| 文件路径 | `src/copaw/agents/tools/contract_file_replace.py` |
| 函数签名 | `async def contract_file_replace(source_path: str, target_path: str, exec_id: str = "", **kwargs) -> ToolResponse` |
| 功能 | 用 `source_path`（用户上传文件）替换 `target_path`（系统存储文件），同时备份原文件 |
| 输入 | `source_path`：来源文件路径；`target_path`：被替换文件路径 |
| 输出 JSON | `{ "replaced": true, "backup_path": "...", "target_path": "...", "file_url": "..." }` |
| 备份路径 | `~/.copaw/contracts/backup/{exec_id[:8]}_{原文件名}` |

**注册位置**：`src/copaw/agents/tools/__init__.py` 和 `react_agent.py`

---

## 三、Skills（子智能体）

### Skill 1：`contract_search` — 合同检索

| 项目 | 说明 |
|---|---|
| 目录 | `src/copaw/agents/skills/contract_search/` |
| agentID | `contract_search` |
| 功能 | 根据用户描述（项目名称、合同类型、甲乙方、时间等关键词）从合同存储库检索匹配合同 |
| 输入参数 | `session_id`, `user_id`, `exec_id`, `query_text`（用户描述） |
| 脚本 | `scripts/contract_search.py` — 调用合同检索 API（向量搜索或关键词搜索） |
| 输出 JSON | `{ "total": N, "contracts": [{ "contract_id", "name", "file_path", "file_url", "contract_type", "created_at" }] }` |
| WS 推送 | `🔍 正在检索：{query_text}...` → `✅ 找到 N 份相关合同` |

---

### Skill 2：`contract_diff_analyze` — 差异分析

| 项目 | 说明 |
|---|---|
| 目录 | `src/copaw/agents/skills/contract_diff_analyze/` |
| agentID | `contract_diff_analyze` |
| 功能 | 提取两份合同文本，调用 `contract_diff` tool 生成差异报告，通过 LLM 输出分析摘要 |
| 输入参数 | `session_id`, `user_id`, `exec_id`, `file_path_a`, `file_path_b`, `label_a`, `label_b` |
| 脚本 | `scripts/diff_analyze.py` — 调用 `docx_extract` + `contract_diff` |
| 输出 JSON | `{ "diff_markdown": "...", "summary": "...", "key_diff_count": N, "report_path": "..." }` |
| WS 推送 | `📊 正在分析差异...` → `✅ 差异分析完成，共发现 N 处关键差异` |

---

### Skill 3：`contract_compare`（主智能体）

| 项目 | 说明 |
|---|---|
| 目录 | `src/copaw/agents/skills/contract_compare/` |
| agentID | `contract_compare_main` |
| 功能 | 流程编排：获取两份合同 → 差异分析 → 展示结果 → 询问是否替换文件 |
| 触发条件 | 用户说"合同对比"、"帮我比较两份合同"、"找一下xxx项目合同" 等 |

---

# Skills流程编排

## 整体流程图

```
用户输入（对话 / 上传文件）
        │
        ▼
┌─────────────────────────────┐
│  contract_compare 主智能体   │  ← 生成 exec_id，全程透传
└────────────┬────────────────┘
             │
     ┌───────┴───────┐
     │ 判断获取合同方式│
     └───┬───────┬───┘
         │       │
    Case A    Case B
  手动上传   对话检索
         │       │
         │       ▼
         │  contract_search 子智能体
         │  (scripts/contract_search.py)
         │  检索匹配合同 → 展示列表 → 用户确认
         │       │
         └───┬───┘
             │  两份合同文件路径确认
             ▼
   contract_diff_analyze 子智能体
   (scripts/diff_analyze.py)
   提取文本 → 差异对比 → LLM 分析摘要
             │
             ▼
      展示差异报告（Markdown）
             │
             ▼
   ┌─────────────────────┐
   │ Case B专属：询问是否  │
   │ 用上传文件替换检索文件 │
   │   【是】     【否】   │
   └──────┬────────┬──────┘
          │是       │否
          ▼         ▼
  contract_file_replace  结束流程
  (tool: contract_file_replace)
  备份原文件 → 替换 → 返回文件URL
          │
          ▼
  "已替换完成，[前往查看]"
```

---

## Step 详细说明

### Step 1：初始化

```
exec_id = uuid4()   # 主智能体启动时生成，全程透传
push(session_id, user_id, "📋 开始合同对比流程...", msg_type="progress")
```

---

### Step 2：获取两份合同

#### Case A：用户手动上传两个文件

> CoPaw 消息处理器自动下载附件后，在消息中注入：
> `"用户上传文件，已经下载到 /path/to/file"`
> 从消息中提取两个本地路径。

1. 检测消息中是否包含两个文件路径（`用户上传文件，已经下载到 {path}`）
2. 若只有一个文件，提示用户："您已上传第一份合同 `{文件名}`，请继续上传第二份合同"
3. 等待用户上传第二份，获取 `file_path_a`、`file_path_b`
4. 设置 `label_a = 原文件名A`，`label_b = 原文件名B`

#### Case B：对话找到合同 + 上传对比文件

1. 用户描述（如"帮我找出xxx项目的合同"），提取 `query_text`
2. 调用 `contract_search` 子智能体脚本：

```bash
python skills/contract_search/scripts/contract_search.py \
  {session_id} {user_id} {exec_id} "{query_text}"
```

3. 解析脚本输出 JSON：
   - `total > 0`：展示合同列表（Markdown 表格，含合同名称、类型、日期），等待用户确认
   - `total = 0`：回复"未找到相关合同，请直接上传两份合同文件"，切换到 Case A
4. 用户确认后，获取 `file_path_a`（检索到的合同），提示：

   > 好的，已找到 **{合同名称}**，请上传您想对比的合同文件

5. 等待用户上传，从消息中提取 `file_path_b`
6. 设置 `label_a = 检索合同名称`，`label_b = 用户上传文件名`

---

### Step 3：差异分析

调用 `contract_diff_analyze` 子智能体脚本：

```bash
python skills/contract_diff_analyze/scripts/diff_analyze.py \
  {session_id} {user_id} {exec_id} \
  "{file_path_a}" "{file_path_b}" "{label_a}" "{label_b}"
```

脚本内部执行顺序：
1. 调用 `docx_extract` Tool 分别提取两份合同文本
2. 调用 `contract_diff` Tool 生成结构化差异（段落级 diff）
3. 将差异内容发给 LLM，输出语义化分析摘要：
   - 核心差异条款（金额、期限、违约责任等）
   - 缺失/新增条款
   - 风险提示

脚本输出 JSON（打印到 stdout）：

```json
{
  "diff_markdown": "## 差异对比报告\n...",
  "summary": "两份合同在付款方式和违约责任条款上存在3处关键差异...",
  "key_diff_count": 3,
  "added_count": 5,
  "removed_count": 2,
  "changed_count": 3
}
```

---

### Step 4：展示差异报告

向用户展示分析结果（Markdown 格式）：

```
📊 **合同差异分析报告**

**对比对象**
- 合同A：{label_a}
- 合同B：{label_b}

**差异摘要**
{summary}

**详细差异（共 {key_diff_count} 处关键差异）**
{diff_markdown}
```

---

### Step 5：询问文件替换（仅 Case B）

若流程为 Case B（对话检索 + 用户上传），在展示报告后追加询问：

> 是否需要将您上传的合同文件，替换已找到的文件？
>
> 【是】 【否】

**用户选【是】**：

调用 `contract_file_replace` Tool：

```python
contract_file_replace(
    source_path=file_path_b,   # 用户上传文件
    target_path=file_path_a,   # 系统检索文件
    exec_id=exec_id,
)
```

回复：

> ✅ 好的，已将原文件替换。[前往查看]({file_url})

**用户选【否】**：

> 好的，已保留原文件，本次对比已完成。

---

### Step 6：异常处理

| 异常场景 | 处理方式 |
|---|---|
| 文件格式不支持（非 docx/pdf/txt） | 提示"暂不支持该格式，请上传 .docx 或 .pdf 文件" |
| 文件提取文本为空 | 提示"文件内容无法读取，请确认文件是否损坏" |
| 检索 API 不可用 | 提示"合同检索服务暂时不可用，请直接上传两份合同文件进行对比" |
| 差异分析超时（>60s） | 推送进度提示，返回原始 diff 文本，不做 LLM 摘要 |
| 文件替换失败 | 提示"文件替换失败，请联系管理员"，保留原文件不做任何修改 |

---

## agentID 注册清单（合同对比模块）

| agentID | 所属 skill/tool | 说明 |
|---|---|---|
| `contract_compare_main` | skill: `contract_compare` | 主编排智能体 |
| `contract_search` | skill: `contract_search` | 合同检索 |
| `contract_diff_analyze` | skill: `contract_diff_analyze` | 差异分析 |
| `contract_file_replace` | tool: `contract_file_replace` | 文件替换 |
| `docx_extract` | tool: `docx_extract` | 文档提取（公共）|
| `contract_diff` | tool: `contract_diff` | 差异对比（公共）|
