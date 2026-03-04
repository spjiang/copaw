# 项目背景

现在开发团队计划开发一款合同审查平台，主要功能模块包含：合同起草（编写）、合同审查、合同对比，是一个工业级项目

我现在主要合同审查，通过 skills技术进行完成，合同审查编写多个子 skill 实现，主 skill 通过用户聊天窗口下达合同审查对话。



# 合同审查智能体skill说明

## 技术实现

合同审查skill：合同审查智能体，合同审查分主智能体、子智能体。

主智能体 为 主 skill，子智能体也是 skill 实现。

## 调用说明

主智能体为合同审查入口，并记录调用主合同审查时，并生成执行ID(exec_id)。

子智能体服务于主智能体，在主智能体编排子智能体。

## 环境变量配置

PlateCompanyName(平台企业名称)：软通智慧

## 名称解释
exec_id: 调用主智能体时，生成exec_id
智能体：提到的智能体都是以 skill进行实现。

## 合同审查日志记录技术实现

 - 根据用户对话发起合同审核需求时，调用合同审核主智能体（skill）时，生成记录调用合同审查主智能体，并记录执行ID(action id)
并保留当前执行ID相应的的子智能体运行日志，并保存在数据库中，子智能体 属性包含 runId,actionID,agentID,inputContent,outputContent,runtime等相关字段


---------------------------------------------------------------------------

# 公共智能体(skill、tool)

## 开发规范

本项目基于 CoPaw 框架，智能体功能分为两种实现方式，开发时按以下原则选择：

### 通用约定：session_id / user_id 与 WebSocket 推送

**所有 skill 的 scripts 脚本**，无论功能，必须遵守以下约定：

#### 1. 命令行参数规范

每个脚本的前三个参数固定为：

```
python scripts/xxx.py <session_id> <user_id> <exec_id> [业务参数...]
```

```python
session_id = sys.argv[1]   # 会话 ID
user_id    = sys.argv[2]   # 登录用户 ID
exec_id    = sys.argv[3]   # 主执行 ID（全程透传）
# sys.argv[4...] 为各脚本自身的业务参数
```

#### 2. 执行前后必须推送 WebSocket 消息

每个脚本执行前发送"开始"消息，执行完成后发送"完成"或"失败"消息：

```python
from shared.push import push
from shared.db import save_agent_log
import time, uuid

session_id = sys.argv[1]
user_id    = sys.argv[2]
exec_id    = sys.argv[3]
action_id  = str(uuid.uuid4())
start_time = time.time()

# ① 执行前推送
push(session_id, user_id, "🔍 正在执行：企查查查询...", msg_type="progress")

try:
    result = do_business_logic()

    # ② 执行成功推送
    push(session_id, user_id, "✅ 企查查查询完成", msg_type="result")

    # ③ 记录执行日志
    save_agent_log(
        exec_id=exec_id, action_id=action_id,
        agent_type="合同审查", agent_name="企查查查询",
        status="success",
        input=json.dumps({"company": company_name}),
        output=json.dumps(result),
        duration_ms=int((time.time() - start_time) * 1000),
    )
    print(json.dumps(result))

except Exception as e:
    # ④ 执行失败推送
    push(session_id, user_id, f"❌ 企查查查询失败：{str(e)}", msg_type="error")

    # ⑤ 记录失败日志
    save_agent_log(
        exec_id=exec_id, action_id=action_id,
        agent_type="合同审查", agent_name="企查查查询",
        status="failed",
        input=json.dumps({"company": company_name}),
        output="null", error_msg=str(e),
        duration_ms=int((time.time() - start_time) * 1000),
    )
    print(json.dumps({"error": str(e)}))
    sys.exit(1)
```

#### 3. 推送消息文案规范

| 时机 | msg_type | 文案格式 |
|---|---|---|
| 执行开始 | `progress` | `🔍 正在执行：{智能体名称}...` |
| 执行成功 | `result` | `✅ {智能体名称}完成` |
| 执行失败 | `error` | `❌ {智能体名称}失败：{错误信息}` |
| 中间进度 | `progress` | `⏳ {智能体名称}（{当前}/{总数}）` |

#### 4. SKILL.md 中传参方式

在 SKILL.md 里调用子脚本时，统一将 `session_id`、`user_id`、`exec_id` 作为前三个参数传入：

```bash
python scripts/qichacha/query.py {session_id} {user_id} {exec_id} {company_name}
python scripts/contract_parse/parse.py {session_id} {user_id} {exec_id} {file_path}
python scripts/law_retrieval/search.py {session_id} {user_id} {exec_id} {contract_text_file}
```

> `session_id` 和 `user_id` 由主合同审查智能体从上下文中获取，`exec_id` 在主智能体启动时生成，全程透传给所有子脚本。

---

### Skill（LLM 驱动）
适用于：**需要 LLM 理解、判断、编排的业务逻辑**

- 在 `src/copaw/agents/skills/{skill_name}/` 下创建目录
- 必须包含 `SKILL.md`（YAML frontmatter 定义 `name` 和 `description`）
- `description` 决定 LLM 什么时候选用此 skill，**务必写清触发条件**
- 业务逻辑复杂时，在 `scripts/` 子目录放 Python 脚本，SKILL.md 里用 `execute_shell_command` 调用
- `scripts/shared/` 存放脚本间共享的公共模块（数据库、签名、工具函数等）

```
skills/
├── shared/                  ← 跨 skill 公共模块（放在外层，所有 skill 共用）
│   ├── __init__.py
│   ├── db.py                ← 数据库操作（save_agent_log 等）
│   └── auth.py              ← 签名、token 等鉴权工具
│
└── {skill_name}/
    ├── SKILL.md             ← LLM 读取的指令文档（必须）
    └── scripts/
        └── do_something.py  ← 业务脚本，通过 sys.path 引用上层 shared
```

脚本内引用 shared 的方式：
```python
# skills/qichacha/scripts/query.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))  # 指向 skills/
from shared.db import save_agent_log
```

### Tool（代码驱动）
适用于：**确定性操作，不需要 LLM 判断，必须可靠执行**

- 在 `src/copaw/agents/tools/` 下创建 `.py` 文件
- 实现为 `async def` 函数，函数签名即接口文档
- 在 `src/copaw/agents/tools/__init__.py` 中导出
- 在 `src/copaw/agents/react_agent.py` 的 `_create_toolkit()` 里注册

```
tools/
└── save_agent_log.py   ← async def save_agent_log(...)
```

### 选择依据

| 场景 | 选择 |
|---|---|
| 用户问"帮我查XX公司"，LLM 决定怎么查 | **Skill** |
| 每次调用子智能体后强制写日志 | **Tool**（注册后由 Skill 脚本内部 import 调用）|
| 生成 UUID、获取当前时间 | **Tool** |
| 合同解析、企查查查询等业务流程 | **Skill**（scripts 里写逻辑）|

> ⚠️ 关键原则：日志记录、数据库写入等**不能漏掉的操作**，一律放在 scripts 脚本里用 `from shared.db import ...` 直接调用，**不依赖 LLM 触发**。

---

## 前端实时推送机制（shared/push.py）

CoPaw 已内置基于轮询的消息推送机制（`console_push_store`），本项目在此基础上扩展，支持以 `session_id + user_id` 作为订阅标识，实现合同审查各子步骤的实时进度推送。

> ⚠️ 这不是注册给 LLM 的 Tool，是 **scripts 脚本直接 import 使用的工具模块**，放在 `skills/shared/push.py`。

### 推送架构

```
skill/scripts（子进程）
    ↓ import shared.push → HTTP POST /api/internal/push（loopback）
CoPaw 内存队列（key = session_id:user_id）
    ↓ 前端订阅轮询 GET /api/console/push-messages?session_id=xxx&user_id=xxx
前端展示进度（对话气泡 / 进度条）
```

### shared/push.py 实现

```python
# skills/shared/push.py
import os
import requests

COPAW_API = os.environ.get("COPAW_API_BASE", "http://127.0.0.1:8088")

def push(session_id: str, user_id: str, text: str, msg_type: str = "progress") -> None:
    """向前端推送实时消息，scripts 脚本直接 import 调用，与 LLM 无关。
    
    Args:
        session_id: 当前会话 ID（由主智能体通过命令行参数传入）
        user_id:    登录用户 ID（由主智能体通过命令行参数传入）
        text:       推送内容（支持 Markdown）
        msg_type:   progress（进行中）/ result（完成）/ error（失败）
    """
    try:
        requests.post(
            f"{COPAW_API}/api/internal/push",
            json={
                "session_id": session_id,
                "user_id": user_id,
                "text": text,
                "msg_type": msg_type,
            },
            timeout=3,
        )
    except Exception:
        pass  # 推送失败不阻断主流程
```

### scripts 脚本使用方式

```python
# skills/qichacha/scripts/query.py
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

session_id = sys.argv[1]
user_id    = sys.argv[2]
exec_id    = sys.argv[3]
company    = sys.argv[4]

push(session_id, user_id, f"🔍 正在查询企查查：{company}")

result = call_qichacha_api(company)

push(session_id, user_id, "✅ 企查查查询完成", msg_type="result")
save_agent_log(exec_id=exec_id, agent_name="企查查查询", output=json.dumps(result), ...)
print(json.dumps(result))
```

### session_id 和 user_id 的来源

由合同审查主 skill 从上下文中获取，通过命令行参数逐级传给子脚本：

```bash
# SKILL.md 中调用子脚本时传入
python scripts/qichacha/query.py {session_id} {user_id} {exec_id} {company_name}
```

### 消息类型

| msg_type | 含义 | 前端展示建议 |
|---|---|---|
| `progress` | 子步骤进行中 | 灰色加载气泡 |
| `result` | 子步骤完成 | 绿色结果气泡 |
| `error` | 子步骤失败 | 红色错误气泡 |

## 企查查智能体(skill)

通过 API 查询企业信息

### 输入参数
- CompanyName: 企业名称

### 输出内容
- company_name: 企业全称
- legal_representative: 法定代表人
- registered_capital: 注册资本
- establishment_date: 成立日期
- business_status: 经营状态（如：存续、注销）
- unified_social_credit_code: 统一社会信用代码
- registered_address: 注册地址
- business_scope: 经营范围
- shareholders: 股东信息列表（股东名称、持股比例）
- qualifications: 资质证书列表（证书名称、有效期）
- risk_info: 风险信息（被执行人、失信记录、行政处罚数量）

### 输出格式
严格输出纯 JSON 字符串，不添加任何解释文字，不使用 Markdown 代码块包裹，无数据字段填 null。

示例：
```
{
  "company_name": "软通智慧信息技术有限公司",
  "legal_representative": "张三",
  "registered_capital": "5000万人民币",
  "establishment_date": "2010-06-01",
  "business_status": "存续",
  "unified_social_credit_code": "91110000XXXXXXXXXX",
  "registered_address": "北京市海淀区XX路XX号",
  "business_scope": "软件开发、信息技术服务...",
  "shareholders": [
    {"name": "软通动力信息技术集团股份有限公司", "ratio": "100%"}
  ],
  "qualifications": [
    {"name": "软件企业认定证书", "valid_until": "2025-12-31"}
  ],
  "risk_info": {
    "executed_count": 0,
    "dishonest_count": 0,
    "penalty_count": 0
  }
}
```

## 执行记录工具（Python Tool）

> 实现方式：Python 工具函数（`save_agent_log`），由代码层强制调用，不经过 LLM 判断。

用于记录每个智能体（skill）的执行过程，持久化写入 PostgreSQL 数据库，支持全链路追踪。

### 函数签名

```python
async def save_agent_log(
    exec_id: str,       # 主执行 ID，由主智能体生成，全程透传
    action_id: str,     # 子动作 ID，每次子智能体调用时生成
    agent_type: str,    # 业务类型：合同审查 / 合同起草 / 合同对比
    agent_name: str,    # 智能体名称：如 企查查查询、合同解析、LLM审查
    status: str,        # 执行状态：success / failed
    input: str,         # 输入内容（JSON 字符串）
    output: str,        # 输出内容（JSON 字符串）
    error_msg: str = None,   # 错误信息（失败时填写，成功时为 null）
    duration_ms: int = None, # 执行耗时（毫秒）
    extra: dict = None,      # 扩展字段（业务特定附加信息）
) -> dict
```

### 数据库表结构

```sql
CREATE TABLE agent_logs (
    id            BIGSERIAL PRIMARY KEY,
    exec_id       UUID NOT NULL,           -- 主执行 ID
    action_id     UUID NOT NULL,           -- 子动作 ID
    agent_type    VARCHAR(50) NOT NULL,    -- 业务类型
    agent_name    VARCHAR(100) NOT NULL,   -- 智能体名称
    status        VARCHAR(20) NOT NULL,    -- success / failed
    input         TEXT,                   -- 输入内容（JSON）
    output        TEXT,                   -- 输出内容（JSON）
    error_msg     TEXT,                   -- 错误信息
    duration_ms   INTEGER,                -- 执行耗时
    extra         JSONB,                  -- 扩展字段
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 索引：按主执行 ID 查全链路
CREATE INDEX idx_agent_logs_exec_id ON agent_logs(exec_id);
-- 索引：按时间查最近记录
CREATE INDEX idx_agent_logs_created_at ON agent_logs(created_at DESC);
```

### 返回值

```json
{
  "success": true,
  "log_id": 12345
}
```

### ID 说明

```
一次合同审查请求
└── exec_id: "550e8400-e29b-41d4-a716-446655440000"  （主智能体生成，全程唯一）
    ├── action_id: "6ba7b810-..."  → 企查查查询
    ├── action_id: "6ba7b811-..."  → 合同解析
    ├── action_id: "6ba7b812-..."  → 审查点查询
    └── action_id: "6ba7b813-..."  → LLM 审查
```

### 调用时机

在每个子智能体（skill）执行**完成后**立即调用，无论成功或失败都必须记录：

```python
start = time.time()
try:
    result = await run_skill(input_data)
    await save_agent_log(
        exec_id=exec_id, action_id=str(uuid4()),
        agent_type="合同审查", agent_name="企查查查询",
        status="success", input=json.dumps(input_data),
        output=json.dumps(result),
        duration_ms=int((time.time() - start) * 1000),
    )
except Exception as e:
    await save_agent_log(
        exec_id=exec_id, action_id=str(uuid4()),
        agent_type="合同审查", agent_name="企查查查询",
        status="failed", input=json.dumps(input_data), output="null",
        error_msg=str(e),
        duration_ms=int((time.time() - start) * 1000),
    )
```











## 合同内容解析工具（Python Tool）

> 实现方式：Python 工具函数（`parse_contract_file`），注册到 Toolkit，LLM 可调用，也可在 scripts 脚本中通过命令行调用。

将合同文件（.docx / .pdf）解析为纯文本，供后续"合同信息提取智能体"使用。

### 函数签名

```python
async def parse_contract_file(
    file_path: str,   # 合同文件绝对路径，支持 .docx / .pdf
) -> dict
```

### 实现说明

- `.docx`：使用 `python-docx` 提取段落文本，保留章节层级
- `.pdf`：使用 `pdfplumber` 提取文本，按页拼接
- 文件不存在或格式不支持时返回错误信息，不抛出异常

### 返回值

```json
{
  "success": true,
  "file_path": "/contracts/2024/HT-2024-001.docx",
  "file_type": "docx",
  "page_count": 12,
  "char_count": 8562,
  "content": "软件开发服务合同\n\n甲方：百纳科技有限公司\n乙方：软通智慧信息技术有限公司\n\n第一条 项目概述\n本合同约定甲方委托乙方开发合同审查管理平台..."
}
```

失败时：
```json
{
  "success": false,
  "file_path": "/contracts/2024/HT-2024-001.docx",
  "error": "文件不存在"
}
```

### 在 SKILL.md 中的调用位置

合同内容解析是合同审查流程的**第一步**，在合同文件确认后立即调用：

```
合同文件确认（上传 or 从系统检索）
    ↓
parse_contract_file(file_path)      ← 本工具（Tool）
    ↓ 返回 content 文本
合同信息提取智能体（skill）           ← 使用 content 提取结构化信息
```

## 合同信息提取智能体（skill）

### 提示词描述
从合同文本中提取关键结构化信息，包括合同主体、金额、期限、履约条款等，为后续审查流程提供数据基础。

### 输入参数
- contract_text: 合同全文内容（字符串）

### 输出参数

合同主体及关键信息提取，输出 JSON 结构：

```json
{
  "contract_title": "软件开发服务合同",
  "contract_no": "HT-2024-001",
  "sign_date": "2024-03-01",
  "party_a": {
    "name": "百纳科技有限公司",
    "role": "甲方",
    "unified_social_credit_code": "91110000XXXXXXXXXX",
    "legal_representative": "李四",
    "address": "北京市朝阳区XX路XX号",
    "contact": "010-88888888"
  },
  "party_b": {
    "name": "软通智慧信息技术有限公司",
    "role": "乙方",
    "unified_social_credit_code": "91110000YYYYYYYYYY",
    "legal_representative": "张三",
    "address": "北京市海淀区XX路XX号",
    "contact": "010-66666666"
  },
  "contract_amount": {
    "total": 500000,
    "currency": "CNY",
    "tax_included": true,
    "payment_terms": "分三期付款，首付30%，验收后付60%，质保期满付10%"
  },
  "contract_period": {
    "start_date": "2024-03-15",
    "end_date": "2024-09-15",
    "duration_days": 184
  },
  "subject_matter": "为甲方开发合同审查管理平台，包含合同起草、审查、对比功能模块",
  "delivery_items": [
    "软件系统源代码",
    "部署文档",
    "用户操作手册",
    "3个月免费运维服务"
  ],
  "key_clauses": {
    "warranty_period": "验收后12个月",
    "liability_cap": "合同总价的10%",
    "dispute_resolution": "北京仲裁委员会仲裁",
    "governing_law": "中华人民共和国法律"
  },
  "platform_company_match": true,
  "extract_confidence": 0.95
}
```

> `platform_company_match`：乙方名称是否与环境变量 `PlateCompanyName`（平台企业名称）匹配，影响后续审查点查询逻辑。
> `extract_confidence`：提取置信度（0~1），低于 0.8 时需人工复核。

## 合同名称匹配智能体（skill）

### 提示词描述
根据用户提供的合同名称关键词，调用第三方合同管理系统 HTTP API 进行模糊匹配，返回相似合同清单。用于用户上传合同前先检索系统内已有合同，支持合同对比和历史审查记录关联。

### 实现方式
调用第三方合同管理系统 HTTP API，在 skill 的 `scripts/contract_search.py` 中实现：

```python
# scripts/contract_search.py
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.db import save_agent_log
from shared.auth import get_api_token   # 获取接口 token

API_BASE_URL = os.environ.get("CONTRACT_API_BASE_URL")  # 从环境变量读取

def search_contracts(contract_file_name, page=1, page_size=10):
    token = get_api_token()
    response = requests.post(
        f"{API_BASE_URL}/api/contract/search",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "keyword": contract_file_name,
            "page": page,
            "page_size": page_size
        },
        timeout=10
    )
    response.raise_for_status()
    return response.json()
```

### 环境变量
- `CONTRACT_API_BASE_URL`：合同管理系统接口地址（如 `https://contract.example.com`）
- `CONTRACT_API_TOKEN` 或由 `shared/auth.py` 统一管理认证 token

### 输入参数
- contract_file_name: 合同名称关键词（如"软件开发"、"采购合同"）
- page: 页码，默认 1
- page_size: 每页数量，默认 10

### 输出参数

输出 JSON 结构：

```json
{
  "total": 3,
  "page": 1,
  "page_size": 10,
  "contracts": [
    {
      "contract_id": "CT-2024-0088",
      "contract_title": "软件开发服务合同",
      "contract_no": "HT-2024-001",
      "file_name": "软件开发服务合同_百纳科技_20240301.docx",
      "file_path": "/contracts/2024/HT-2024-001.docx",
      "party_a": "百纳科技有限公司",
      "party_b": "软通智慧信息技术有限公司",
      "contract_amount": 500000,
      "sign_date": "2024-03-01",
      "status": "执行中",
      "similarity_score": 0.92
    },
    {
      "contract_id": "CT-2023-0056",
      "contract_title": "软件定制开发合同",
      "contract_no": "HT-2023-088",
      "file_name": "软件定制开发合同_新华集团_20230615.docx",
      "file_path": "/contracts/2023/HT-2023-088.docx",
      "party_a": "新华集团有限公司",
      "party_b": "软通智慧信息技术有限公司",
      "contract_amount": 280000,
      "sign_date": "2023-06-15",
      "status": "已完成",
      "similarity_score": 0.85
    }
  ]
}
```

**后续交互逻辑：**
- `total > 0`：通过 websocket 将合同清单发送前端展示，提示用户确认需要审核的合同（回复合同名称或编号）
- `total = 0`：返回空列表，主智能体提示"未匹配到相似合同，请直接上传合同文件"
- `similarity_score`：相似度得分（0~1），按降序排列，低于 0.6 的结果不返回

---------------------------------------------------------------------------


## 审查记录本体查询智能体（skill）

### 提示词描述
根据合同 ID（contract_id），查询 Neo4j 知识图谱中该合同关联的历史审查记录，返回审查节点数据。用于了解该合同或同类合同的历史审查情况，辅助本次审查决策。

### 实现方式
在 `scripts/review_record_query.py` 中，调用 Neo4j HTTP API 执行 Cypher 查询语句。

```python
# scripts/review_record_query.py
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

NEO4J_URI  = os.environ.get("NEO4J_URI",  "http://localhost:7474")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "")

def query_neo4j(cypher: str, params: dict = {}) -> list:
    resp = requests.post(
        f"{NEO4J_URI}/db/neo4j/tx/commit",
        auth=(NEO4J_USER, NEO4J_PASS),
        json={"statements": [{"statement": cypher, "parameters": params}]},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    errors = data.get("errors", [])
    if errors:
        raise RuntimeError(errors[0].get("message"))
    results = data.get("results", [{}])[0]
    columns = results.get("columns", [])
    rows = []
    for row in results.get("data", []):
        rows.append(dict(zip(columns, row.get("row", []))))
    return rows
```

### 环境变量
- `NEO4J_URI`：Neo4j HTTP 接口地址（如 `http://localhost:7474`）
- `NEO4J_USER`：用户名
- `NEO4J_PASS`：密码

### 输入参数
- contract_id: 合同 ID（优先匹配）
- party_a: 甲方名称（contract_id 未知时使用）

### 查询 Cypher 示例

```cypher
// 按合同 ID 查询审查记录节点及其关联数据
MATCH (c:Contract {contract_id: $contract_id})-[:HAS_REVIEW]->(r:ReviewRecord)
OPTIONAL MATCH (r)-[:REVIEWED_BY]->(u:User)
OPTIONAL MATCH (r)-[:HAS_RISK]->(risk:RiskPoint)
RETURN r.review_id    AS review_id,
       r.review_date  AS review_date,
       r.status       AS status,
       r.conclusion   AS conclusion,
       u.name         AS reviewer,
       collect(risk)  AS risk_points
ORDER BY r.review_date DESC
LIMIT 10
```

### 输出参数

```json
{
  "contract_id": "CT-2024-0088",
  "total": 2,
  "review_records": [
    {
      "review_id": "RV-2024-0033",
      "review_date": "2024-03-05",
      "status": "已完成",
      "conclusion": "通过，存在2处风险点需关注",
      "reviewer": "王法务",
      "risk_points": [
        {"point": "违约金条款表述模糊", "level": "中"},
        {"point": "知识产权归属未明确", "level": "高"}
      ]
    },
    {
      "review_id": "RV-2023-0091",
      "review_date": "2023-11-20",
      "status": "已完成",
      "conclusion": "通过",
      "reviewer": "李法务",
      "risk_points": []
    }
  ]
}
```

**后续使用逻辑：**
- `total > 0`：将历史审查记录传入审查 LLM 智能体，作为参考上下文
- `total = 0`：无历史记录，审查 LLM 智能体仅依据审查点规则进行审查


## 预审人员本体查询智能体（skill）

### 提示词描述
根据合同ID:contract_id 或合同主体信息，查询 Neo4j 知识图谱中该合同关联的预审人员节点，返回当前合同的审核人及审批状态。

### 实现方式
复用 `scripts/shared/neo4j_client.py`（与审查记录查询共用），在 `scripts/reviewer_query.py` 中执行专属 Cypher。

### 输入参数
- contract_id: 合同 ID（优先）
- party_a: 甲方名称（contract_id 未知时使用）

### 查询 Cypher 示例

```cypher
// 查询合同关联的审核人及审批状态
MATCH (c:Contract {contract_id: $contract_id})-[:HAS_REVIEWER]->(r:Reviewer)
OPTIONAL MATCH (r)-[:BELONGS_TO]->(d:Department)
RETURN        r.user_id      AS user_id,
       r.name         AS name,
       r.role         AS role,
       r.status       AS status,
       r.assigned_at  AS assigned_at,
       r.reviewed_at  AS reviewed_at,
       d.name         AS department
ORDER BY r.assigned_at ASC
```

### 输出参数

```json
{
  "contract_id": "CT-2024-0088",
  "total": 2,
  "reviewers": [
    {
      "user_id": "U-001",
      "name": "王法务",
      "role": "法务专员",
      "department": "法务部",
      "status": "已审",
      "assigned_at": "2024-03-02",
      "reviewed_at": "2024-03-03"
    },
    {
      "user_id": "U-002",
      "name": "李经理",
      "role": "法务经理",
      "department": "法务部",
      "status": "待审",
      "assigned_at": "2024-03-03",
      "reviewed_at": null
    }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `status` | 审核状态：`已审` / `待审` / `已驳回` |
| `reviewed_at` | 为 null 表示尚未完成审核 |

**后续使用逻辑：**
- 将审核人信息传入审查 LLM 智能体，告知当前审核人及进度
- `status = 已驳回` 时，主智能体提示用户"该合同已被驳回，请确认是否重新发起审查"


## 合同向量本体查询智能体（skill）

### 提示词描述
传入用户上传的合同文本内容，将其向量化后在 Neo4j 向量索引中检索最相似的历史合同，返回相似度最高的合同 ID 及文件路径。用于合同对比场景：用户上传新合同时，自动匹配系统内最相似的已有合同，供前端进行双合同 Word 对比渲染。

### 实现方式
在 `scripts/contract_vector_search.py` 中分两步执行：
1. 调用 Embedding API 将合同文本向量化
2. 调用 Neo4j 向量索引执行余弦相似度检索

```python
# scripts/contract_vector_search.py
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

EMBEDDING_API  = os.environ.get("EMBEDDING_API_BASE")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-v4")
NEO4J_URI      = os.environ.get("NEO4J_URI", "http://localhost:7474")
NEO4J_USER     = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS     = os.environ.get("NEO4J_PASS", "")

def get_embedding(text: str) -> list[float]:
    """调用 Embedding API 将文本向量化。"""
    resp = requests.post(
        f"{EMBEDDING_API}/embeddings",
        headers={"Authorization": f"Bearer {os.environ.get('EMBEDDING_API_KEY')}"},
        json={"model": EMBEDDING_MODEL, "input": text[:8000]},  # 截取前 8000 字符
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]

def vector_search(embedding: list[float], top_k: int = 3) -> list:
    """在 Neo4j 向量索引中检索最相似合同。"""
    cypher = """
    CALL db.index.vector.queryNodes('contract_vector_index', $top_k, $embedding)
    YIELD node AS c, score
    RETURN c.contract_id  AS contract_id,
           c.contract_title AS contract_title,
           c.file_path      AS file_path,
           c.party_a        AS party_a,
           c.party_b        AS party_b,
           c.sign_date      AS sign_date,
           score
    ORDER BY score DESC
    """
    resp = requests.post(
        f"{NEO4J_URI}/db/neo4j/tx/commit",
        auth=(NEO4J_USER, NEO4J_PASS),
        json={"statements": [{"statement": cypher,
                               "parameters": {"top_k": top_k, "embedding": embedding}}]},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [{}])[0]
    columns = results.get("columns", [])
    return [dict(zip(columns, r.get("row", []))) for r in results.get("data", [])]
```

### 环境变量
- `EMBEDDING_API_BASE`：向量化接口地址
- `EMBEDDING_API_KEY`：向量化接口密钥
- `EMBEDDING_MODEL`：向量模型名称（默认 `text-embedding-v4`）
- `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASS`：Neo4j 连接配置

### Neo4j 向量索引（需提前创建）

```cypher
// 在 Contract 节点上创建向量索引（首次部署时执行一次）
CREATE VECTOR INDEX contract_vector_index IF NOT EXISTS
FOR (c:Contract) ON c.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 1024,
  `vector.similarity_function`: 'cosine'
}}
```

每次新合同入库时，需同步写入 embedding 字段：
```cypher
MATCH (c:Contract {contract_id: $contract_id})
SET c.embedding = $embedding
```

### 输入参数
- contract_text: 合同全文内容（字符串，由合同内容解析工具输出的 `content` 字段传入）
- top_k: 返回最相似合同数量，默认 3

### 输出参数

```json
{
  "top_k": 3,
  "results": [
    {
      "contract_id": "CT-2023-0056",
      "contract_title": "软件定制开发合同",
      "file_path": "/contracts/2023/HT-2023-088.docx",
      "party_a": "新华集团有限公司",
      "party_b": "软通智慧信息技术有限公司",
      "sign_date": "2023-06-15",
      "similarity_score": 0.94
    },
    {
      "contract_id": "CT-2022-0031",
      "contract_title": "信息系统开发服务合同",
      "file_path": "/contracts/2022/HT-2022-031.docx",
      "party_a": "中建科技有限公司",
      "party_b": "软通智慧信息技术有限公司",
      "sign_date": "2022-09-10",
      "similarity_score": 0.87
    }
  ]
}
```

**后续使用逻辑：**
- `similarity_score ≥ 0.85`：主智能体提示用户"找到高度相似合同，是否进行对比审查？"，用户确认后将 `file_path` 发送前端进行双 Word 渲染
- `similarity_score < 0.85`：跳过对比环节，直接进入审查流程
- `results` 为空：无相似合同，直接进入审查流程


## 自有产品本体查询智能体（skill）

### 提示词描述
从合同文本中提取交付产品/服务清单，然后在 Neo4j 自有产品知识图谱中逐一匹配，返回各产品的官方定价及差异分析。用于审查合同中的产品价格是否与公司定价体系一致，识别低价或异常定价风险。

### 实现方式
分两步执行：
1. **LLM 抽取**：由 skill 指示 LLM 从合同文本中提取产品/服务名称、合同约定数量、合同约定单价
2. **Neo4j 查询**：在 `scripts/product_price_query.py` 中，根据抽取的产品名称查询 Neo4j 自有产品实体，获取官方定价

```python
# scripts/product_price_query.py
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

NEO4J_URI  = os.environ.get("NEO4J_URI",  "http://localhost:7474")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "")

def query_product_price(product_names: list[str]) -> list:
    cypher = """
    UNWIND $names AS name
    MATCH (p:Product)
    WHERE p.name CONTAINS name OR name CONTAINS p.name
    RETURN p.product_id   AS product_id,
           p.name         AS product_name,
           p.unit         AS unit,
           p.unit_price   AS unit_price,
           p.price_level  AS price_level,
           p.description  AS description,
           name           AS query_name
    """
    resp = requests.post(
        f"{NEO4J_URI}/db/neo4j/tx/commit",
        auth=(NEO4J_USER, NEO4J_PASS),
        json={"statements": [{"statement": cypher,
                               "parameters": {"names": product_names}}]},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [{}])[0]
    columns = results.get("columns", [])
    return [dict(zip(columns, r.get("row", []))) for r in results.get("data", [])]
```

### 输入参数
- contract_text: 合同全文内容（由合同内容解析工具输出的 `content` 字段传入）

### 处理流程

```
contract_text
    ↓ LLM 从合同文本中提取产品清单（含合同约定单价）
    ↓ 得到 extracted_items[]
    ↓ 调用 scripts/product_price_query.py 查询 Neo4j 官方定价
    ↓ 对比合同价 vs 官方价，计算差异率
输出 price_analysis[]
```

### 输出参数

```json
{
  "total": 3,
  "price_analysis": [
    {
      "product_id": "P-001",
      "product_name": "合同审查管理平台软件",
      "unit": "套",
      "contract_quantity": 1,
      "contract_unit_price": 480000,
      "official_unit_price": 500000,
      "price_level": "标准版",
      "diff_amount": -20000,
      "diff_rate": -0.04,
      "risk_level": "低",
      "remark": "合同价低于官方定价4%，在正常折扣范围内"
    },
    {
      "product_id": "P-002",
      "product_name": "运维服务（年）",
      "unit": "年",
      "contract_quantity": 1,
      "contract_unit_price": 15000,
      "official_unit_price": 50000,
      "price_level": "标准版",
      "diff_amount": -35000,
      "diff_rate": -0.70,
      "risk_level": "高",
      "remark": "合同价低于官方定价70%，存在低价风险，需人工复核"
    },
    {
      "product_id": null,
      "product_name": "数据迁移服务",
      "unit": null,
      "contract_quantity": 1,
      "contract_unit_price": 20000,
      "official_unit_price": null,
      "price_level": null,
      "diff_amount": null,
      "diff_rate": null,
      "risk_level": "未知",
      "remark": "未在自有产品库中找到匹配项，需人工确认"
    }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `diff_rate` | 差异率 = (合同价 - 官方价) / 官方价，负值表示合同价低于官方价 |
| `risk_level` | `低`（差异 < 10%）/ `中`（10%~30%）/ `高`（> 30%）/ `未知`（未匹配到产品）|
| `official_unit_price` 为 null | 未在自有产品库匹配到，需人工确认 |

**后续使用逻辑：**
- `risk_level = 高` 的条目，作为审查风险点输出给审查 LLM 智能体
- `official_unit_price = null` 的条目，提示用户该产品不在自有产品库，需手动核查


## 企业审查点本体查询智能体（skill）

### 提示词描述
查询 Neo4j 知识图谱中企业审查点实体下的所有审查点规则，返回审查点清单。作为 LLM 审查智能体进行合同风险识别的核心依据。

> 是否调用此 skill 由**主合同审查智能体**根据 `platform_company_match` 判断决定，本 skill 内部无需判断。

### 实现方式
在 `scripts/enterprise_review_points_query.py` 中直接查询 Neo4j 企业审查点实体。

```python
# scripts/enterprise_review_points_query.py
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

NEO4J_URI  = os.environ.get("NEO4J_URI",  "http://localhost:7474")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "")

def query_enterprise_review_points(company_name: str) -> list:
    cypher = """
    MATCH (e:Enterprise {name: $company_name})-[:HAS_REVIEW_POINT]->(p:ReviewPoint)
    RETURN p.point_id     AS point_id,
           p.category     AS category,
           p.name         AS name,
           p.description  AS description,
           p.priority     AS priority,
           p.is_mandatory AS is_mandatory
    ORDER BY p.priority ASC
    """
    resp = requests.post(
        f"{NEO4J_URI}/db/neo4j/tx/commit",
        auth=(NEO4J_USER, NEO4J_PASS),
        json={"statements": [{"statement": cypher,
                               "parameters": {"company_name": company_name}}]},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [{}])[0]
    columns = results.get("columns", [])
    return [dict(zip(columns, r.get("row", []))) for r in results.get("data", [])]
```

### 输入参数
- company_name: 平台企业名称（从环境变量 `PlateCompanyName` 获取）

### 输出参数

```json
{
  "total": 3,
  "review_points": [
    {
      "point_id": "RP-E-001",
      "category": "主体资质",
      "name": "供应商营业执照有效期核查",
      "description": "检查合同乙方营业执照是否在有效期内，吊销或异常状态不得签约",
      "priority": 1,
      "is_mandatory": true
    },
    {
      "point_id": "RP-E-002",
      "category": "价格条款",
      "name": "合同价格与采购预算一致性",
      "description": "合同总价不得超过采购预算的10%，超出须附审批说明",
      "priority": 2,
      "is_mandatory": true
    },
    {
      "point_id": "RP-E-003",
      "category": "违约责任",
      "name": "违约金条款完整性",
      "description": "合同须明确约定违约金计算方式及上限，缺失则为高风险",
      "priority": 3,
      "is_mandatory": true
    }
  ]
}
```

**后续使用逻辑：**
- 将 `review_points` 传给审查 LLM 智能体，作为审查指令清单逐条核查
- `is_mandatory = true` 的审查点未通过时，直接标记为高风险

---

## 个人审查点查询智能体（skill）

### 提示词描述
根据当前登录用户 ID，调用第三方 API 接口查询该用户配置的个人审查点清单，返回个人审查点数据。

### 实现方式
在 `scripts/user_review_points_query.py` 中调用 HTTP API 接口获取个人审查点。

```python
# scripts/user_review_points_query.py
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log
from shared.auth import get_api_token

API_BASE_URL = os.environ.get("CONTRACT_API_BASE_URL")

def query_user_review_points(user_id: str) -> list:
    token = get_api_token()
    resp = requests.get(
        f"{API_BASE_URL}/api/review-points/user/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])
```

### 输入参数
- user_id: 当前登录用户 ID

### 输出参数

```json
{
  "user_id": "U-001",
  "total": 2,
  "review_points": [
    {
      "point_id": "RP-U-001",
      "category": "知识产权",
      "name": "交付物知识产权归属",
      "description": "定制开发成果知识产权须归甲方所有",
      "priority": 1,
      "is_mandatory": false
    },
    {
      "point_id": "RP-U-002",
      "category": "交付验收",
      "name": "验收标准明确性",
      "description": "合同须明确验收标准和验收周期，缺失则付款条件存在歧义",
      "priority": 2,
      "is_mandatory": false
    }
  ]
}
```

**后续使用逻辑：**
- 将 `review_points` 与企业审查点合并后传给审查 LLM 智能体（企业审查点优先级高于个人）
- 无论 `platform_company_match` 结果如何，个人审查点均需查询

---

## 交付人员信息本体查询智能体（skill）

### 提示词描述
根据合同主体信息，查询 Neo4j 知识图谱中与该合同关联的交付人员实体，返回交付人员的工时、单价及费用信息。用于审查合同中的人员成本是否与公司内部定价一致，识别人员费用异常风险。

### 实现方式
在 `scripts/delivery_staff_query.py` 中调用 Neo4j 查询交付人员实体。

```python
# scripts/delivery_staff_query.py
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

NEO4J_URI  = os.environ.get("NEO4J_URI",  "http://localhost:7474")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "")

def query_delivery_staff(contract_id: str) -> list:
    cypher = """
    MATCH (c:Contract {contract_id: $contract_id})-[:HAS_DELIVERY_STAFF]->(s:DeliveryStaff)
    OPTIONAL MATCH (s)-[:HAS_ROLE]->(r:Role)
    RETURN s.staff_id        AS staff_id,
           s.name            AS name,
           r.role_name       AS role,
           r.level           AS level,
           s.work_hours      AS work_hours,
           r.standard_price  AS standard_unit_price,
           s.contract_price  AS contract_unit_price,
           s.work_hours * s.contract_price  AS contract_total,
           s.work_hours * r.standard_price  AS standard_total
    ORDER BY r.level ASC
    """
    resp = requests.post(
        f"{NEO4J_URI}/db/neo4j/tx/commit",
        auth=(NEO4J_USER, NEO4J_PASS),
        json={"statements": [{"statement": cypher,
                               "parameters": {"contract_id": contract_id}}]},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [{}])[0]
    columns = results.get("columns", [])
    return [dict(zip(columns, r.get("row", []))) for r in results.get("data", [])]
```

### 输入参数
- contract_id: 合同 ID

### 输出参数

```json
{
  "contract_id": "CT-2024-0088",
  "total_staff": 4,
  "contract_staff_total": 280000,
  "standard_staff_total": 320000,
  "diff_rate": -0.125,
  "staff_list": [
    {
      "staff_id": "S-001",
      "name": "张工",
      "role": "项目经理",
      "level": "高级",
      "work_hours": 400,
      "standard_unit_price": 300,
      "contract_unit_price": 280,
      "standard_total": 120000,
      "contract_total": 112000,
      "diff_rate": -0.067,
      "risk_level": "低"
    },
    {
      "staff_id": "S-002",
      "name": "李工",
      "role": "开发工程师",
      "level": "中级",
      "work_hours": 600,
      "standard_unit_price": 200,
      "contract_unit_price": 120,
      "standard_total": 120000,
      "contract_total": 72000,
      "diff_rate": -0.400,
      "risk_level": "高"
    },
    {
      "staff_id": "S-003",
      "name": "王工",
      "role": "测试工程师",
      "level": "初级",
      "work_hours": 300,
      "standard_unit_price": 150,
      "contract_unit_price": 160,
      "standard_total": 45000,
      "contract_total": 48000,
      "diff_rate": 0.067,
      "risk_level": "低"
    },
    {
      "staff_id": "S-004",
      "name": "赵工",
      "role": "实施工程师",
      "level": "中级",
      "work_hours": 240,
      "standard_unit_price": 180,
      "contract_unit_price": 200,
      "standard_total": 43200,
      "contract_total": 48000,
      "diff_rate": 0.111,
      "risk_level": "低"
    }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `work_hours` | 合同约定工时（小时） |
| `standard_unit_price` | 公司内部标准单价（元/小时） |
| `contract_unit_price` | 合同约定单价（元/小时） |
| `diff_rate` | 差异率 = (合同价 - 标准价) / 标准价，负值表示合同价低于标准价 |
| `risk_level` | `低`（差异 < 10%）/ `中`（10%~30%）/ `高`（> 30%）|
| `contract_staff_total` | 合同人员费用合计 |
| `standard_staff_total` | 按标准定价计算的人员费用合计 |

**后续使用逻辑：**
- `risk_level = 高` 的人员条目，作为审查风险点输出给审查 LLM 智能体
- 整体 `diff_rate` 低于 -30% 时，主智能体提示人员成本整体偏低，可能存在人员配置不足风险

---

## 合同关联本体查询智能体（skill）

### 提示词描述
根据合同 ID，查询 Neo4j 知识图谱中与该合同存在关联关系的其他合同（如采购合同关联销售合同、框架合同关联子合同等），返回关联合同清单及关联关系类型。用于审查合同间的履约依赖关系，识别关联合同缺失或条款冲突风险。

### 实现方式
在 `scripts/contract_relation_query.py` 中查询 Neo4j 合同关联实体。

```python
# scripts/contract_relation_query.py
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

NEO4J_URI  = os.environ.get("NEO4J_URI",  "http://localhost:7474")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "")

def query_contract_relations(contract_id: str) -> list:
    cypher = """
    MATCH (c:Contract {contract_id: $contract_id})-[rel:RELATED_TO]->(rc:Contract)
    RETURN rc.contract_id    AS related_contract_id,
           rc.contract_title AS related_contract_title,
           rc.contract_no    AS related_contract_no,
           rc.party_a        AS party_a,
           rc.party_b        AS party_b,
           rc.contract_amount AS contract_amount,
           rc.sign_date      AS sign_date,
           rc.status         AS status,
           rc.file_path      AS file_path,
           type(rel)         AS relation_type,
           rel.description   AS relation_desc
    ORDER BY rc.sign_date DESC
    """
    resp = requests.post(
        f"{NEO4J_URI}/db/neo4j/tx/commit",
        auth=(NEO4J_USER, NEO4J_PASS),
        json={"statements": [{"statement": cypher,
                               "parameters": {"contract_id": contract_id}}]},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [{}])[0]
    columns = results.get("columns", [])
    return [dict(zip(columns, r.get("row", []))) for r in results.get("data", [])]
```

### 输入参数
- contract_id: 合同 ID

### 输出参数

```json
{
  "contract_id": "CT-2024-0088",
  "total": 2,
  "related_contracts": [
    {
      "related_contract_id": "CT-2024-0021",
      "related_contract_title": "软件产品采购框架合同",
      "related_contract_no": "CG-2024-021",
      "party_a": "软通智慧信息技术有限公司",
      "party_b": "百纳科技有限公司",
      "contract_amount": 2000000,
      "sign_date": "2024-01-10",
      "status": "执行中",
      "file_path": "/contracts/2024/CG-2024-021.docx",
      "relation_type": "PURCHASE_SALE",
      "relation_desc": "当前销售合同对应的采购框架合同"
    },
    {
      "related_contract_id": "CT-2023-0099",
      "related_contract_title": "软件开发补充协议",
      "related_contract_no": "HT-2023-099",
      "party_a": "百纳科技有限公司",
      "party_b": "软通智慧信息技术有限公司",
      "contract_amount": 80000,
      "sign_date": "2023-12-01",
      "status": "已完成",
      "file_path": "/contracts/2023/HT-2023-099.docx",
      "relation_type": "SUPPLEMENTARY",
      "relation_desc": "上一期项目的补充协议，与本合同甲乙方相同"
    }
  ]
}
```

**关联关系类型说明：**

| relation_type | 含义 |
|---|---|
| `PURCHASE_SALE` | 采购合同 ↔ 销售合同（履约成本关联）|
| `FRAMEWORK_SUB` | 框架合同 ↔ 子合同（授权范围关联）|
| `SUPPLEMENTARY` | 主合同 ↔ 补充协议（条款变更关联）|
| `CONTINUATION` | 前期合同 ↔ 续签合同（历史关联）|

**后续使用逻辑：**
- `total > 0`：将关联合同信息传入审查 LLM 智能体，审查当前合同与关联合同的条款是否一致（如金额、交付范围、期限）
- `relation_type = PURCHASE_SALE`：重点审查销售价格是否高于采购成本，确保合理利润空间
- `total = 0`：无关联合同，跳过此审查环节

---

## 法案检索匹配查询智能体（skill）

### 提示词描述
将合同文本按段落切分后，循环调用向量检索 API，查找每个段落对应的相关法律法规条款，返回法案匹配结果。用于审查合同中各条款是否符合现行法律法规，识别违法或无效条款风险。

### 实现方式
在 `scripts/law_retrieval.py` 中分两步执行：
1. **段落切分**：将合同全文按段落/条款拆分为文本块（chunk）
2. **循环向量检索**：逐块调用向量检索 API，返回最相关的法律条款

```python
# scripts/law_retrieval.py
import sys, os, json, re, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from shared.push import push
from shared.db import save_agent_log

LAW_SEARCH_API = os.environ.get("LAW_SEARCH_API_BASE")  # 法案向量检索 API
LAW_API_KEY    = os.environ.get("LAW_API_KEY", "")

def split_paragraphs(text: str, min_len: int = 30) -> list[str]:
    """按段落/条款切分合同文本，过滤过短的段落。"""
    # 按换行、第X条、（一）等常见合同结构切分
    raw = re.split(r'\n{2,}|(?=第[一二三四五六七八九十百]+条)|(?=\（[一二三四五六七八九十]+\）)', text)
    return [p.strip() for p in raw if len(p.strip()) >= min_len]

def search_law(chunk: str, top_k: int = 3) -> list:
    """调用向量检索 API 查询相关法律条款。"""
    resp = requests.post(
        f"{LAW_SEARCH_API}/api/law/search",
        headers={
            "Authorization": f"Bearer {LAW_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"query": chunk, "top_k": top_k},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])

def run(contract_text: str, session_id: str, user_id: str) -> dict:
    chunks = split_paragraphs(contract_text)
    total  = len(chunks)
    matched_results = []

    for idx, chunk in enumerate(chunks):
        push(session_id, user_id,
             f"⚖️ 法案检索中 ({idx + 1}/{total})：{chunk[:30]}...")

        laws = search_law(chunk, top_k=2)
        if laws:
            matched_results.append({
                "chunk_index": idx,
                "chunk_text": chunk,
                "matched_laws": laws,
            })

    return {
        "total_chunks": total,
        "matched_count": len(matched_results),
        "results": matched_results,
    }
```

### 环境变量
- `LAW_SEARCH_API_BASE`：法案向量检索服务地址
- `LAW_API_KEY`：法案检索服务密钥

### 输入参数
- contract_text: 合同全文内容（由合同内容解析工具输出的 `content` 字段传入）
- session_id / user_id: 用于实时推送检索进度

### 输出参数

```json
{
  "total_chunks": 18,
  "matched_count": 5,
  "results": [
    {
      "chunk_index": 2,
      "chunk_text": "乙方应在验收完成后30日内开具等额增值税专用发票，甲方收票后15日内付款",
      "matched_laws": [
        {
          "law_id": "L-2021-0033",
          "law_name": "中华人民共和国发票管理办法",
          "article_no": "第二十二条",
          "content": "销售商品、提供服务以及从事其他经营活动的单位和个人，对外发生经营业务收取款项，收款方应当向付款方开具发票",
          "similarity_score": 0.91,
          "risk_hint": "合同约定开票时限，需核查是否符合发票管理规定"
        }
      ]
    },
    {
      "chunk_index": 7,
      "chunk_text": "因不可抗力导致合同无法履行时，双方均不承担违约责任，但需在3日内书面通知对方",
      "matched_laws": [
        {
          "law_id": "L-2020-0180",
          "law_name": "中华人民共和国民法典",
          "article_no": "第五百九十条",
          "content": "当事人一方因不可抗力不能履行合同的，根据不可抗力的影响，部分或者全部免除责任，但是法律另有规定的除外",
          "similarity_score": 0.96,
          "risk_hint": "不可抗力条款与民法典规定基本一致，通知时限3日偏短，建议核查"
        }
      ]
    }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `total_chunks` | 合同被切分的段落总数 |
| `matched_count` | 命中法律条款的段落数量 |
| `chunk_text` | 合同原文段落 |
| `article_no` | 对应法律的具体条款编号 |
| `similarity_score` | 向量相似度（0~1），越高越相关 |
| `risk_hint` | 检索服务返回的风险提示（可选字段） |

**后续使用逻辑：**
- 将匹配结果传入审查 LLM 智能体，逐条分析合同段落与法律条款的一致性
- `similarity_score ≥ 0.90` 的结果优先输出，作为高置信度法律依据
- 无匹配结果（`matched_count = 0`）时，LLM 依据自身法律知识进行审查，并在结论中注明"未检索到对应法规"


# 合同审查流程步骤

## 主合同审查智能体（Skill）

负责业务流程流程编排，如何调用子智能体（skill）。

### 合同审查智能体编排如下（子智能体编排）

#### 1.合同文档获取方式

##### case1. 对话用户在聊天窗口上传合同审查附件📎

  get_contract_file_type: file_attach
  file_attach 代表是通过聊天窗口获取合同文件

  逻辑如下：
  调用 **合同向量本体查询智能体（skill）**，获取向量相似度合同信息
  
  如果有：AI回复：是否需要合同对比？
  用户回复：是， 通过 websocket 发送至前端进行两个合同 word 渲染（右边为附件上传的，左边为对比查询到合同）

后端拿到需要审核的合同 path 地址（json 结构），存储到当前对话session任务中的全局变量contract_review_file_path中。

##### case2.对话用户通过对话方式

get_contract_file_type: file_chat

file_chat： 通过用户对话提取合同文件

示例如下：

User对话: 请帮我审查 - 【鄂州市数据局共享交换平台2025年运维服务项目】采购合同_天湾1229-V1.0.docx

---------
此时大模型进行对话内容提取合同名称：【鄂州市数据局共享交换平台2025年运维服务项目】采购合同_天湾1229-V1.0
skill调用：合同名称匹配智能体（skill）获取已匹配合同列表(json结构)
前端渲染：调用前端实时推送机制（websocket), 发送已匹配合同列表(json结构)

AI回复: 显示已匹配合同列表(json结构)，如果 json 为空，显示"未匹配到相似合同"

User对话: 用户确认已匹配到的合同

前端 word 渲染: 调用前端实时推送机制（websocket), 发送合同存储地址（json 结构）至前端进行word渲染

后端拿到需要审核的合同 path 地址（json 结构），存储到当前对话session任务中的全局变量contract_review_file_path中。


#### 2.合同内容解析工具（Python Tool）

根据合同文档地址，获取合同文本内容。

前端 智能运行思维链 渲染: 调用前端实时推送机制（websocket)，包含当前智能体 input、output 等内容

#### 3.合同信息提取智能体（skill）

调用合同信息提取智能体（skill），传入合同审查 path 地址。

前端 智能运行思维链 渲染: 调用前端实时推送机制（websocket)，包含当前智能体 input、output 等内容

#### 4.审查记录本体查询智能体（skill）

根据合同主体信息，查询 Neo4j 知识图谱中该合同关联的历史审查记录，返回审查节点数据。用于了解该合同或同类合同的历史审查情况，辅助本次审查决策。

前端 智能运行思维链 渲染: 调用前端实时推送机制（websocket)，包含当前智能体 input、output 等内容


#### 5.企查查智能体(skill)

  前端 智能运行思维链 渲染: 调用前端实时推送机制（websocket)，包含当前智能体 input、output 等内容

#### 6.主体检索匹配PlateCompanyName(平台企业名称)-逻辑判断


##### case：匹配成功：审查点本体查询智能体（主体检索匹配PlateCompanyName(平台企业名称)如软通智慧）

  预审人员记录（合同审核人员关联，如哪些人员审批通过了）：调用**预审人员本体查询智能体（skill）**
  企业审查点查询：调用**企业审查点本体查询智能体（skill）**
  产品价格分析查询：调用**自有产品本体查询智能体（skill）**
  交付人员信息查找（工时、价格）：调用**交付人员信息本体查询智能体（skill）**
  合同关联（采购合同销售销售合同）：调用**合同关联本体查询智能体（skill）**
  法案检索：调用**法案检索匹配查询智能体（skill）**


##### case：主体检索匹配PlateCompanyName(平台企业名称)，未匹配成功

  个人审查点查询：调用**个人审查点查询智能体（skill）**
  法案检索：调用**法案检索匹配查询智能体（skill）**

#### 7. 合同审查LLM智能体（Skill）

汇总前 6 步收集到的所有信息，通过结构化提示词驱动大模型逐条审查，输出风险点列表。

##### 输入数据汇总

| 来源 | 数据 |
|---|---|
| 合同内容解析 | `contract_text`（合同全文）|
| 合同信息提取 | `contract_info`（甲乙方、金额、期限等）|
| 企查查查询 | `qichacha_info`（企业资质、风险信息）|
| 审查点查询 | `review_points`（企业审查点 + 个人审查点）|
| 法案检索 | `law_matches`（合同段落 → 对应法律条款）|
| 产品价格查询 | `price_analysis`（产品定价差异）|
| 交付人员查询 | `staff_analysis`（人员工时价格差异）|
| 合同关联查询 | `related_contracts`（关联合同信息）|
| 历史审查记录 | `review_records`（历史审查结论）|
| 预审人员 | `reviewers`（审核人及状态）|

##### 提示词设计

```
你是一名专业的合同法律审查专家，请根据以下信息对合同进行全面风险审查。

## 合同基本信息
{contract_info}

## 合同全文
{contract_text}

## 对方企业背调（企查查）
{qichacha_info}

## 审查点清单（必须逐条核查）
{review_points}

## 法律法规匹配结果
{law_matches}

## 产品价格差异分析
{price_analysis}

## 交付人员费用分析
{staff_analysis}

## 关联合同信息
{related_contracts}

## 历史审查记录（供参考）
{review_records}

---

请按以下要求进行审查：

1. 逐条核查【审查点清单】中的每一个审查点，判断合同是否满足要求
2. 结合【法律法规匹配结果】，识别合同条款是否存在违法或无效风险
3. 结合【产品价格差异】和【交付人员费用差异】，识别定价异常风险
4. 结合【对方企业背调】，识别主体资质风险
5. 结合【关联合同】，审查合同间条款一致性和履约依赖风险
6. 参考【历史审查记录】中的历史风险点，判断是否重复出现

对每个发现的风险点，按以下 JSON 格式输出，不要添加任何解释文字：

{
  "risk_points": [
    {
      "risk_id": "R-001",
      "category": "风险分类",
      "title": "风险点简述（15字以内）",
      "description": "详细描述风险内容及潜在影响",
      "contract_clause": "合同中的原文片段（引用依据）",
      "law_reference": "相关法律条款（如有）",
      "risk_level": "高/中/低",
      "suggestion": "修改建议或处理方式",
      "source": "审查点/法案/价格/人员/关联合同/企查查"
    }
  ]
}
```

##### 输出参数

```json
{
  "exec_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_id": "CT-2024-0088",
  "review_conclusion": "存在风险，建议修改后签署",
  "risk_count": {
    "high": 2,
    "medium": 3,
    "low": 1
  },
  "risk_points": [
    {
      "risk_id": "R-001",
      "category": "主体资质",
      "title": "乙方存在行政处罚记录",
      "description": "企查查显示乙方在2023年有2次行政处罚记录，涉及产品质量问题，签约存在履约风险",
      "contract_clause": "乙方：百纳科技有限公司",
      "law_reference": "中华人民共和国政府采购法 第二十二条",
      "risk_level": "高",
      "suggestion": "要求乙方提供处罚已整改证明，或更换合格供应商",
      "source": "企查查"
    },
    {
      "risk_id": "R-002",
      "category": "违约责任",
      "title": "违约金条款表述模糊",
      "description": "合同第八条约定违约金为"适当赔偿"，未明确计算方式及上限，发生争议时难以执行",
      "contract_clause": "第八条：一方违约应向对方支付适当赔偿",
      "law_reference": "中华人民共和国民法典 第五百八十五条",
      "risk_level": "高",
      "suggestion": "明确约定违约金计算方式，建议为合同总价的10%～20%",
      "source": "审查点"
    },
    {
      "risk_id": "R-003",
      "category": "价格条款",
      "title": "运维服务单价低于标准定价70%",
      "description": "合同约定运维服务单价15000元/年，公司标准定价50000元/年，差异率-70%，存在低价风险",
      "contract_clause": "第四条：运维服务费用15000元/年",
      "law_reference": null,
      "risk_level": "中",
      "suggestion": "核查报价审批记录，确认是否经过授权折扣审批",
      "source": "价格"
    }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `review_conclusion` | 总体审查结论：`通过` / `存在风险，建议修改后签署` / `不建议签署` |
| `risk_level` | 风险等级：`高`（必须处理）/ `中`（建议处理）/ `低`（知悉即可）|
| `source` | 风险来源，便于追溯是哪个子智能体发现的 |
| `contract_clause` | 合同原文引用，便于前端定位到 Word 文档中的具体位置 |

**执行完成后推送 WebSocket：**

```python
push(session_id, user_id,
     f"📋 合同审查完成：发现 {risk_count['high']} 个高风险、"
     f"{risk_count['medium']} 个中风险、{risk_count['low']} 个低风险",
     msg_type="result")
```

审查结果同时通过 websocket 发送至前端，在 Word 渲染视图中对应条款位置标注风险标记。







