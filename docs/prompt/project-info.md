# 项目背景

我现在在做一个合同起草智能体，整体仍然采用 `contract_draft` 主智能体编排，协同 `contract_template_match`、`contract_template_params`、`contract_template_llm` 三个子智能体完成合同起草。

新的目标不是只做“有附件就匹配、没附件就直接写”，而是要形成一套完整、严谨、可追踪的合同起草流程：

1. 无论用户是否上传附件，都要尽量进入“模板优先”的路线。
2. 无附件时，也要先识别用户意图，例如采购合同、销售合同、租赁合同等，再去模板库检索。
3. 匹配到模板后，要进行模板确认、参数提取、参数补齐、模板渲染。
4. 未上传模板且未匹配到平台模板，或者用户明确选择跳过模板时，再调用 `contract_template_llm` 走大模型自由起草。
5. 所有智能体都必须在开始、结束时推送 Redis；关键节点必须增加 `running` 状态推送。

## 总体协作架构

```text
contract_draft
  ├─ 判断附件 / 判断用户意图
  ├─ 调用 contract_template_match
  │    ├─ 有附件：从附件名 + 对话中提取关键词检索模板库
  │    └─ 无附件：从对话中识别合同类型/关键词检索模板库
  ├─ 若匹配到模板：模板确认 -> 调用 contract_template_params
  │    ├─ 根据 param_schema_json 生成参数表单
  │    ├─ 通过对话补齐参数
  │    └─ 调用模板渲染接口生成合同
  └─ 若未匹配到模板或用户跳过模板：调用 contract_template_llm 直接起草
```

## 公共运行约定

### 1. 运行时核心变量

#### 通用变量

- `session_id`：当前会话 ID
- `user_id`：当前用户 ID，取值方式为 `COPAW_USER_ID = os.environ.get("COPAW_USER_ID")`
- `exec_id`：当前执行链路 ID
- `run_id`：当前单次技能运行 ID
- `skill_name`：当前技能名称
- `file_list`：`os.environ.get("COPAW_INPUT_FILE_URLS")`，表示用户上传附件列表
- `user_input_text`：当前用户输入文本
- `template_list`：模板库匹配结果列表
- `selected_template_id`：最终确认的模板 ID
- `selected_template_url`：最终确认的模板 URL
- `selected_template_params_schema`：最终确认模板对应的 `param_schema_json`
- `render_result_url`：模板渲染接口返回的合同地址

#### 附件处理规则

`file_list` 可能为空，也可能包含多个附件，因此必须统一规范：

1. `file_list` 为空、空字符串、空数组、解析失败，统一视为“未上传附件”。
2. `file_list` 有多个附件时，默认取最新上传的一条作为本次合同模板候选附件。
3. 附件类型优先处理 `docx`、`doc`、`pdf`、`wps` 等合同文档；非合同文档要忽略，并推送 `running` 说明未发现可用合同附件。
4. 即使用户上传了附件，也不能直接跳过模板匹配；仍然要先尝试从平台模板库检索标准模板。

### 2. Redis 推送统一规范

所有技能都必须推送三类状态：

- `stage = start`：技能开始
- `stage = running`：关键节点
- `stage = end`：技能结束

统一 JSON 结构如下：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_draft",
  "stage": "start | running | end",
  "render_type": "具体事件类型",
  "input": { ... },
  "output": { ... },
  "timestamp": "...",
  "runtime_ms": 0
}
```

### 3. render_type 命名建议

建议全链路统一以下关键节点名称，避免前端渲染和日志检索混乱：

- `agent_start`
- `agent_end`
- `file_list_checked`
- `attachment_detected`
- `attachment_missing`
- `user_intent_identified`
- `user_intent_required`
- `template_candidates_found`
- `template_selection_required`
- `template_selected`
- `template_not_found`
- `template_skipped`
- `template_params_required`
- `template_params_updated`
- `template_params_completed`
- `template_render_started`
- `template_render_success`
- `template_render_failed`
- `llm_draft_started`
- `llm_draft_success`
- `llm_draft_failed`

## 严格决策矩阵

| 是否上传附件 | 是否识别出合同意图 | 是否匹配到平台模板 | 用户是否确认模板 | 最终路径 |
| --- | --- | --- | --- | --- |
| 是 | 可识别 | 是 | 是 | `contract_template_params` -> 模板渲染 |
| 是 | 可识别 | 是 | 否，选择跳过 | `contract_template_llm` |
| 是 | 可识别/不可识别 | 否 | 不涉及 | `contract_template_llm` |
| 否 | 可识别 | 是 | 是 | `contract_template_params` -> 模板渲染 |
| 否 | 可识别 | 是 | 否，选择跳过 | `contract_template_llm` |
| 否 | 可识别 | 否 | 不涉及 | `contract_template_llm` |
| 否 | 不可识别 | 不涉及 | 不涉及 | 先追问用户合同类型，再继续 |

说明：

1. “未上传附件”不代表直接走大模型，必须先尝试识别合同意图并检索模板库。
2. “匹配到模板”也不能直接使用，必须给用户一次确认机会。
3. “未匹配到模板”才进入 LLM 自由起草路径。
4. 用户在任何模板确认或参数补齐阶段都可以主动选择“跳过模板、直接起草”，此时进入 `contract_template_llm`。

## 主智能体：contract_draft

`contract_draft` 是唯一入口，负责总编排、分支判断、子技能调用、最终结果输出。

### 1. 开始事件

主智能体启动时必须推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_draft",
  "stage": "start",
  "render_type": "agent_start",
  "input": {
    "user_input_text": "用户当前输入",
    "file_list": "os.environ.get(\"COPAW_INPUT_FILE_URLS\")"
  },
  "output": {
    "message": "合同起草主流程开始"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

### 2. Step 1：判断是否上传附件

先读取：

```python
file_list = os.environ.get("COPAW_INPUT_FILE_URLS")
```

然后推送 `running`：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_draft",
  "stage": "running",
  "render_type": "file_list_checked",
  "input": {
    "file_list": "原始 file_list"
  },
  "output": {
    "has_attachment": true,
    "attachment_count": 1
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

分支规则如下。

#### Case A：用户已上传附件

1. 记录 `has_attachment = true`
2. 取最新上传的合同附件作为 `latest_attachment_url`
3. 推送 `attachment_detected`
4. 调用 `contract_template_match`

#### Case B：用户未上传附件

1. 记录 `has_attachment = false`
2. 推送 `attachment_missing`
3. 不允许直接结束流程，而是进入“用户意图识别”
4. 若用户当前只说“帮我起草一份合同”，信息不足，必须追问：
   - 您要起草哪一类合同？
   - 是采购合同、销售合同、租赁合同、服务合同，还是其他类型？
5. 若用户已经明确表达“采购”“销售”“租赁”等关键词，则直接进入 `contract_template_match`

### 3. Step 2：意图识别与模板检索分派

#### 有附件时

有附件并不代表直接使用附件本身渲染，而是：

1. 从附件文件名提取关键词
2. 结合用户对话补充合同类型信息
3. 调用 `contract_template_match` 去平台模板库检索

#### 无附件时

要从对话中提取：

- 合同类型，如采购合同、销售合同、房屋租赁合同、技术服务合同
- 业务关键词，如软件采购、设备采购、产品销售、系统集成、房屋租赁

再调用 `contract_template_match` 去模板库检索。

若识别出意图，主智能体应推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_draft",
  "stage": "running",
  "render_type": "user_intent_identified",
  "input": {
    "user_input_text": "帮我起草一份软件采购合同"
  },
  "output": {
    "contract_type": "采购合同",
    "keyword_list": ["采购", "软件", "软件采购"]
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

若无法识别，推送 `user_intent_required`，并向用户追问合同类型。

### 4. Step 3：处理模板匹配结果

`contract_template_match` 返回后，主智能体根据 `template_list` 做严格分支：

#### Case A：匹配到多条模板

1. 向用户展示模板列表
2. 让用户二次确认选择哪一个模板
3. 推送 `template_selection_required`
4. 用户选中后，记录：
   - `selected_template_id`
   - `selected_template_url`
   - `selected_template_params_schema`
5. 推送 `template_selected`
6. 调用 `contract_template_params`

#### Case B：只匹配到 1 条模板

也必须给用户一次确认，不建议无感知自动使用。推荐回复：

`已为您匹配到 1 份合同模板：xxx，是否按该模板起草？`

用户确认后：

1. 记录 `selected_template_id`
2. 记录 `selected_template_url`
3. 记录 `selected_template_params_schema`
4. 推送 `template_selected`
5. 调用 `contract_template_params`

用户如果回复“跳过模板，直接起草”，则推送 `template_skipped`，调用 `contract_template_llm`。

#### Case C：未匹配到平台模板

此时不再走模板参数渲染，而是进入 LLM 自由起草路线：

1. 推送 `template_not_found`
2. 明确告知用户：当前未匹配到标准合同模板，将根据您的需求直接起草
3. 调用 `contract_template_llm`

### 5. Step 4：处理最终结果

主智能体需要统一收口：

#### 模板渲染成功

输出渲染后的合同地址，结束主流程。

#### LLM 起草成功

输出大模型起草结果，结束主流程。

#### 子流程失败

若子流程失败，要把失败原因推送到 Redis，并给用户可理解的错误提示。

### 6. 结束事件

主智能体结束时必须推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_draft",
  "stage": "end",
  "render_type": "agent_end",
  "input": {
    "selected_template_id": "xxx",
    "final_mode": "template_render | llm_draft"
  },
  "output": {
    "result_url": "最终合同地址",
    "result_type": "docx"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

## 子智能体一：contract_template_match

这个子智能体负责“模板候选检索”，不负责最终生成合同。

### contract_template_match 输入

- `session_id`
- `exec_id`
- `run_id`
- `file_list`
- `user_input_text`

### contract_template_match 输出

- `has_attachment`
- `contract_type`
- `keyword_list`
- `template_list`
- `need_user_confirm`

### contract_template_match 开始事件

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_match",
  "stage": "start",
  "render_type": "agent_start",
  "input": {
    "file_list": "原始附件列表",
    "user_input_text": "用户输入"
  },
  "output": {
    "message": "开始匹配合同模板"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

### contract_template_match 核心处理逻辑

#### Step 1：确定匹配来源

##### 有附件

从最新附件提取：

- `user_upload_contract_template_url`
- `user_upload_contract_template_file_name`

再从文件名和用户对话中抽取关键词，例如：

- `5-软件产品销售合同.docx` -> `["销售", "软件产品", "销售合同"]`
- `设备采购协议.docx` -> `["采购", "设备采购", "采购合同"]`

推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_match",
  "stage": "running",
  "render_type": "attachment_detected",
  "input": {
    "file_list": "原始 file_list"
  },
  "output": {
    "user_upload_contract_template_url": "http://xxx/xxx.docx",
    "user_upload_contract_template_file_name": "设备采购协议.docx"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

##### 无附件

从会话语义中提取合同意图，例如：

- 用户输入：`帮我写一份销售合同`
- 得到：`contract_type = 销售合同`
- 关键词：`["销售", "销售合同"]`

若无法提取合同类型或关键词，必须推送 `user_intent_required` 并返回主智能体继续追问，不允许盲目查库。

#### Step 2：模板库查询

数据库模板名称检索（PostgreSQL）：

- IP：`10.156.196.158`
- Port：`5432`
- User：`user_t8ZA3i`
- Password：`password_DTXtQH`

原始检索思路保留，但建议升级为“多关键词模糊匹配”，而不是只查一个 `keyword_name`。

推荐 SQL 思路如下：

```sql
SELECT
    id,
    title,
    file_path,
    param_schema_json
FROM public.contract_templates
WHERE
    title ILIKE '%采购%'
    OR title ILIKE '%销售%'
    OR title ILIKE '%租赁%';
```

实际执行时，建议根据 `keyword_list` 动态生成查询条件，返回 `template_list`。

#### Step 3：模板匹配结果处理

##### 匹配到模板

若 `template_list` 非空，推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_match",
  "stage": "running",
  "render_type": "template_candidates_found",
  "input": {
    "keyword_list": ["采购", "软件采购"]
  },
  "output": {
    "template_count": 3,
    "template_list": [
      {
        "template_id": "1",
        "title": "软件采购合同",
        "template_url": "http://10.156.196.158:19000/copaw-files/xxx.docx",
        "param_schema_json": { }
      }
    ]
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

若匹配结果大于 1 条，必须要求用户二次确认。

若只匹配 1 条，也建议做一次确认，避免误用模板。

##### 未匹配到模板

若 `template_list` 为空，推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_match",
  "stage": "running",
  "render_type": "template_not_found",
  "input": {
    "keyword_list": ["销售", "软件产品"]
  },
  "output": {
    "template_count": 0,
    "template_list": []
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

此时返回主智能体，由主智能体决定走 `contract_template_llm`。

### contract_template_match 结束事件

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_match",
  "stage": "end",
  "render_type": "agent_end",
  "input": {
    "user_input_text": "用户输入",
    "file_list": "原始 file_list"
  },
  "output": {
    "contract_type": "采购合同",
    "keyword_list": ["采购", "软件采购"],
    "template_count": 3
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

## 子智能体二：contract_template_params

这个子智能体负责“模板参数提取 + 参数补齐 + 模板渲染”，只在用户确认模板后调用。

### contract_template_params 输入

- `session_id`
- `exec_id`
- `run_id`
- `selected_template_id`
- `selected_template_url`
- `selected_template_params_schema`
- `user_input_text`

### contract_template_params 输出

- `filled_params_json`
- `render_result_url`
- `render_success`

### contract_template_params 开始事件

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "start",
  "render_type": "agent_start",
  "input": {
    "template_id": "xxx",
    "template_url": "http://xxx/xxx.docx"
  },
  "output": {
    "message": "开始处理模板参数"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

### contract_template_params 核心处理逻辑

#### Step 1：加载模板参数结构

优先读取已匹配模板对应的 `param_schema_json`。

若 `param_schema_json` 非空，则直接作为参数表单基准结构。

若 `param_schema_json` 为空，才允许降级为“从模板占位符中自动提取参数”。

推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "running",
  "render_type": "template_params_required",
  "input": {
    "template_id": "xxx"
  },
  "output": {
    "param_schema_json": { },
    "required_param_count": 8
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

#### Step 2：根据对话提取参数值

要充分利用：

- 用户当前输入
- 历史对话
- 已明确表达的公司名称、合同金额、签署日期、标的名称、服务范围等信息

进行参数赋值。

对于已提取出的参数，推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "running",
  "render_type": "template_params_updated",
  "input": {
    "template_id": "xxx"
  },
  "output": {
    "filled_param_count": 5,
    "missing_param_count": 3
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

#### Step 3：缺失参数追问

若参数未补齐，必须继续向用户提问，而不是直接调用渲染接口。

例如：

- 甲方公司名称是什么？
- 乙方公司名称是什么？
- 合同金额是多少？
- 签署日期是什么时候？

缺参时推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "running",
  "render_type": "template_params_required",
  "input": {
    "template_id": "xxx"
  },
  "output": {
    "missing_fields": ["company_a", "company_b", "sign_date"]
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

#### Step 4：参数补齐完成

当所有必填参数补齐后，推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "running",
  "render_type": "template_params_completed",
  "input": {
    "template_id": "xxx"
  },
  "output": {
    "filled_params_json": {
      "contract_effect_year": "2024",
      "company_a": "北京华夏科技有限公司",
      "company_b": "软通智慧信息技术有限公司"
    }
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

#### Step 5：调用模板渲染接口

调用合同模板渲染 API：

`POST http://10.17.55.121:8012/render`

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `template_url` | string | 是 | docx 模板 HTTP 下载地址 |
| `text` | string | 是 | JSON 文本，解析后作为渲染参数 |

调用前先推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "running",
  "render_type": "template_render_started",
  "input": {
    "template_id": "xxx",
    "template_url": "http://xxx/xxx.docx"
  },
  "output": {
    "message": "开始调用模板渲染接口"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

调用示例：

```bash
curl -X POST http://10.17.55.121:8012/render \
  -H "Content-Type: application/json" \
  -d '{
    "template_url": "http://your-domain.com/templates/合同模板.docx",
    "text": "{\"contract_effect_year\":\"2024\",\"company_a\":\"北京华夏科技有限公司\",\"company_b\":\"软通智慧信息技术有限公司\"}"
  }'
```

接口成功响应示例：

```json
{
  "success": true,
  "url": "http://10.156.196.158:9000/yuanti/docxtpl/xxx.docx",
  "message": "ok"
}
```

#### Step 6：渲染结果处理

##### 渲染成功

推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "running",
  "render_type": "template_render_success",
  "input": {
    "template_id": "xxx",
    "template_url": "http://xxx/xxx.docx"
  },
  "output": {
    "render_result_url": "http://10.156.196.158:9000/yuanti/docxtpl/xxx.docx"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

##### 渲染失败

推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "running",
  "render_type": "template_render_failed",
  "input": {
    "template_id": "xxx",
    "template_url": "http://xxx/xxx.docx"
  },
  "output": {
    "error_message": "渲染接口调用失败"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

渲染失败后返回主智能体，由主智能体决定是否回退到 `contract_template_llm`。

### contract_template_params 结束事件

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_params",
  "stage": "end",
  "render_type": "agent_end",
  "input": {
    "template_id": "xxx",
    "template_url": "http://xxx/xxx.docx"
  },
  "output": {
    "render_success": true,
    "render_result_url": "http://10.156.196.158:9000/yuanti/docxtpl/xxx.docx"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

## 子智能体三：contract_template_llm

这个子智能体只在以下场景调用：

1. 用户未上传附件，且没有匹配到平台模板
2. 用户上传了附件，但仍然没有匹配到平台模板
3. 用户明确表示“跳过模板，直接起草”
4. 模板渲染失败，主智能体决定回退到自由起草

### contract_template_llm 输入

- `session_id`
- `exec_id`
- `run_id`
- `user_input_text`
- `contract_type`
- `business_context`

### contract_template_llm 输出

- `draft_content`
- `result_url` 或 `result_text`

### contract_template_llm 开始事件

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_llm",
  "stage": "start",
  "render_type": "agent_start",
  "input": {
    "user_input_text": "用户需求",
    "contract_type": "采购合同"
  },
  "output": {
    "message": "开始使用大模型起草合同"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

### contract_template_llm 核心处理逻辑

#### Step 1：开始起草

先推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_llm",
  "stage": "running",
  "render_type": "llm_draft_started",
  "input": {
    "contract_type": "采购合同"
  },
  "output": {
    "message": "正在根据用户需求自由起草合同"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

#### Step 2：生成合同内容

根据用户描述生成完整合同正文，至少包含：

- 合同标题
- 合同主体
- 标的或服务内容
- 合同金额与支付方式
- 履行期限
- 双方权利义务
- 违约责任
- 争议解决
- 签署页

#### Step 3：生成结果

若能生成文件地址，则返回 `result_url`；

若暂时不能生成文件，则至少返回结构化合同正文。

成功后推送：

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_llm",
  "stage": "running",
  "render_type": "llm_draft_success",
  "input": {
    "contract_type": "采购合同"
  },
  "output": {
    "result_type": "docx",
    "result_url": "最终合同地址"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

失败时推送 `llm_draft_failed`。

### contract_template_llm 结束事件

```json
{
  "session_id": "xxx",
  "user_id": "xxx",
  "exec_id": "xxx",
  "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "skill_name": "contract_template_llm",
  "stage": "end",
  "render_type": "agent_end",
  "input": {
    "contract_type": "采购合同"
  },
  "output": {
    "result_type": "docx | markdown",
    "result_url": "最终合同地址"
  },
  "timestamp": "...",
  "runtime_ms": 0
}
```

## 推荐的用户交互原则

### 1. 无附件时先引导合同类型

当用户没有上传附件，也没有明确说清楚合同类型时，必须先问清楚，不允许直接编造模板查询条件。

推荐话术：

`请问您要起草哪一类合同？例如采购合同、销售合同、租赁合同、服务合同等。`

### 2. 匹配到模板时必须确认

不论匹配到 1 条还是多条模板，都建议做一次用户确认，至少保证用户知道当前将使用哪个模板。

### 3. 参数不全时必须继续追问

如果模板参数缺失，不能直接调用渲染接口，否则会导致模板渲染结果残缺。

### 4. 用户随时可跳过模板

只要用户明确说“跳过模板”“直接起草”，就可以终止模板路线，切换到 `contract_template_llm`。

## 异常与边界场景

### 1. 附件为空或解析失败

- 推送 `attachment_missing` 或 `file_list_checked`
- 继续识别用户意图
- 不直接报错结束

### 2. 用户意图不明确

- 推送 `user_intent_required`
- 明确追问合同类型
- 不直接进入模板检索

### 3. 查询到模板但用户迟迟不确认

- 保持等待
- 不自动推进到模板参数阶段

### 4. `param_schema_json` 为空

- 允许降级为占位符提取
- 同时推送 `template_params_required`

### 5. 模板渲染失败

- 推送 `template_render_failed`
- 允许主智能体回退到 `contract_template_llm`

### 6. 大模型起草失败

- 推送 `llm_draft_failed`
- 返回可理解的错误提示给用户

## 最终方案结论

新的严谨流程应当固定为：

1. `contract_draft` 统一入口，先判定附件，再判定意图。
2. `contract_template_match` 负责基于附件或语义提取关键词，去模板库匹配并返回候选模板列表。
3. 匹配到模板后，必须进行一次用户确认。
4. 用户确认模板后，`contract_template_params` 负责参数提取、参数补齐、模板渲染，并在关键节点推送 `running` 状态。
5. 未上传模板且未匹配到模板，或用户主动跳过模板，或模板渲染失败时，进入 `contract_template_llm`，由大模型自由起草。
6. 所有智能体统一执行 `start -> running -> end` 的 Redis 推送规范，确保前端与日志都能完整感知流程状态。
