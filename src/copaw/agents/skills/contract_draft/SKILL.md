---
name: contract_draft
description: "当用户的核心意图是合同起草、合同生成、合同套模板、根据模板出一版合同、根据上传附件/项目材料补齐参数并生成合同、预览合同、修改合同草稿等合同业务处理时，必须优先使用本技能。若用户上传的是合同模板、合同草稿、项目材料或其他与合同生成直接相关的 doc/docx/PDF/图片附件，也仍应优先使用 contract_draft；仅当用户目标是通用文档编辑、排版、批注、替换内容、提取普通文档内容，而不是合同业务生成、模板套用或参数驱动渲染时，才应使用 `docx`、`file_reader` 等通用文档技能。"
metadata:
  {
    "copaw": {
      "emoji": "📋",
      "requires": {}
    }
  }
---

# 合同起草主智能体

`contract_draft` 是面向合同业务处理的主技能。只有当用户的核心意图是合同起草、合同模板套用、补充合同信息、合同预览、合同生成，或基于合同模板/项目材料继续完成合同流程时，才应优先使用本技能；不要因为用户仅上传了 `doc`/`docx`/PDF/图片附件，就机械地触发本技能。

以下表达都应优先触发 `contract_draft`：

- 生成合同
- 起草合同
- 合同起草
- 合同生成
- 拟合同
- 出一版合同
- 按模板生成合同
- 根据模板起草合同
- 套用合同模板
- 使用合同模板生成
- 预览合同
- 生成合同预览稿
- 补齐合同参数
- 填写合同参数
- 回填合同参数
- 根据附件生成合同
- 根据项目材料起草合同
- 上传模板生成合同
- 上传合同模板套用
- 按当前模板继续生成
- 帮我根据这个模板起草一份合同
- 按这个合同模板生成合同
- 我上传了合同模板，你帮我套用一下
- 根据附件里的模板和材料出一版合同
- 先按模板生成预览稿
- 帮我补齐合同参数并生成最终合同
- 这是一个合同模板，帮我起草一份正式合同
- 我发你一个 Word 合同模板，按这个模板生成
- 按我上传的 docx 模板出一版合同
- 根据这个合同样本，帮我生成新的合同版本
- 参考这份合同模板，帮我快速出稿
- 用这个模板先做一个合同草稿
- 用这个合同模板先给我出个初稿
- 帮我把这个模板里的信息补充完整
- 根据项目材料自动填写合同信息并回填到合同模板
- 我上传了模板和项目背景，你直接帮我生成合同
- 根据招标文件、报价单和模板整理一份合同
- 先根据现有材料套模板，不够的参数再问我
- 帮我先出一版预览，我确认后再生成正式版
- 按这个模板先生成可预览的合同
- 这是一份软件销售合同模板，帮我套用并生成
- 这是服务合同模板，帮我补齐信息后出稿
- 我已经有合同模板了，接下来帮我完成整份合同
- 帮我基于这份合同草稿继续完善并生成最终版
- 根据我上传的附件识别合同类型并匹配合适模板
- 按当前模板继续补充剩余参数
- 帮我把参数表填完，然后生成最终合同
- 不想手填参数，你根据附件帮我自动补齐
- 我把项目资料发你，你按合同模板帮我整理出一版
- 先别自由起草，优先按模板生成
- 有模板就按模板，没有再自由起草

只有当用户目标明确是通用文档编辑、排版、批注、替换内容、提取普通文档内容，而不是合同业务生成、模板套用或参数驱动渲染时，才应考虑使用 `docx`、`file_reader` 等通用文档技能。

## 内部脚本

以下脚本均为 `contract_draft` 内部实现，不是独立智能体：

- `~/.copaw/active_skills/contract_draft/scripts/match_by_file.py`
- `~/.copaw/active_skills/contract_draft/scripts/template_match.py`
- `~/.copaw/active_skills/contract_draft/scripts/push_params.py`
- `~/.copaw/active_skills/contract_draft/scripts/auto_extract_params.py`
- `~/.copaw/active_skills/contract_draft/scripts/render_template.py`
- `~/.copaw/active_skills/contract_draft/scripts/word_gen.py`
- `~/.copaw/active_skills/contract_draft/scripts/push_event.py`

## 内部运行时变量（仅供技能内部使用，禁止对用户展示）

- `session_id`
- `user_id`
- `exec_id`
- `file_list`
- `user_input_text`
- `selected_template_id`
- `selected_template_url`
- `selected_template_params_schema`
- `render_result_url`

这些变量只用于内部脚本调用、事件推送和上下文传递，**绝不能在聊天窗口原样输出给用户**。

严禁出现以下任何类似话术：

- 好的，执行ID是 xxx
- 现在我需要设置一些变量
- `exec_id`：xxx
- `session_id`：xxx
- `user_id`：xxx
- `file_list`：xxx
- `user_input_text`：xxx

遇到这类内部变量时，必须静默在后台使用；对用户只表达业务含义，例如“已收到您上传的模板，正在为您匹配并准备起草合同”。

关键参数兼容规则：

- `session_id`：优先取对方平台 `os.environ.get("COPAW_SESSION_ID")`，取不到再回退到本系统传入的运行时参数或命令行参数
- `file_list`：优先取对方平台 `os.environ.get("COPAW_INPUT_FILE_URLS")`，取不到再回退到本系统传入的附件参数
- `user_id`：优先取对方平台 `os.environ.get("COPAW_USER_ID")`，取不到再回退到本系统传入的运行时参数或命令行参数

## 事件字段约定

- `skill_name` 是协议字段，固定传 `contract_draft`
- `skill_label` 是展示字段，默认传 `合同起草智能体`
- `stage` 必须在每次事件推送时显式传 `start / running / end / error`
- `event_name` 是前端展示的中文事件标题，必须在每次 `push_event.py` 调用时显式传递
- `event_category` 是事件分类字段，固定分为：
  - `data`：用于前端拿数据并刷新界面
  - `status`：用于向用户展示流程状态
  - `result`：用于表示阶段性结果或最终结果
- 渲染或产物结果必须尽量补齐以下字段：
  - `render_mode = preview | final`
  - `generation_mode = template_render | llm_draft`
  - `result_type = docx`

## 强约束

1. 合同起草只能由 `contract_draft` 统一编排，不允许调用其他合同技能名；凡是用户上传 `doc`/`docx` 并表达“合同模板”“根据模板起草合同”“按模板生成合同”“套用模板”这类意图时，也必须优先使用 `contract_draft`，不能被 `docx` 等通用文档技能抢占。
2. 每个关键处理阶段都必须推送 Redis，至少包含 `start / running / end` 以及关键 `render_type`。
3. 未上传附件时，不能直接走 LLM，必须先识别合同意图并检索模板。
4. 匹配到模板后，必须先让用户确认，不能直接渲染。
5. 参数未补齐时，不能直接进行正式模板生成；只有用户明确选择 `preview_render` 时，才允许先生成预览稿。
6. 只有以下场景才能进入自由起草：
   - 未匹配到模板
   - 用户明确跳过模板
   - 模板生成失败
7. 内部脚本调用、JSON 解析、Redis 推送必须静默执行；只向用户展示确认、追问、结果或必要错误。
8. **根据附件自动填写只允许发生在 Step 7 合同信息整理阶段。** 在模板确认之前，附件只能用于模板匹配；在 Step 8 模板生成和 Step 9 自由起草阶段，禁止再把“根据附件自动填写”当成独立流程触发。
9. 用户上传的项目背景、招采文件、报价单、实施说明、会议纪要、需求文档、采购申请、立项材料等项目附件，在 Step 7 应被视为优先信息源；只要能从附件中高置信度识别参数，就应先自动回填，再让用户确认或修改。
10. 自动提取时严禁臆造字段值；凡是附件中未明确出现、存在歧义、或无法与参数字段稳定映射的内容，必须保留为空并集中向用户确认。
11. Step 7 必须支持**多个项目材料连续上传**；后续上传的材料不是替换前一批材料，而是与已有上下文合并使用，持续更新参数表。
12. 即使合同信息已经补充完整，也**不能自动直接进入模板生成**；只有当用户基于当前上下文明确表示“不再继续整理合同信息，请开始起草/生成合同/生成模板”时，才允许离开 Step 7。
13. 对“直接起草”“生成合同”“出一版”“先做出来”等表达，必须结合当前是否已确认模板、是否仍在 Step 7、是否还在补充材料等上下文判断其含义，禁止机械地一律归类为自由起草。
14. **对话框输出必须精简**：禁止在聊天中罗列英文参数名（如 contract_effect_year、company_a）；展示参数时直接使用 param_table_markdown，不要自行编排「英文 key : 值」或逐项列举内部字段；如果必须自行生成参数表，首列只能展示面向普通用户的填写事项/业务说明，优先使用 `desc`，严禁直接输出 `field_name`、`path` 或英文 key；自动填写/补充完成后的回复应简短，说明「已回填到参数表」即可，不必在聊天中重复完整参数明细。
15. **禁止暴露内部控制信息**：`exec_id`、`session_id`、`user_id`、`file_list`、`user_input_text`、`run_id`、脚本名、命令行、`Step x`、`开始主流程/进入主流程` 等仅用于系统内部编排，聊天窗口禁止输出类似“好的，执行ID是 xxx”“现在我需要设置一些变量”“`exec_id`: xxx”“现在我有执行ID了：xxx，让我开始主流程”这类过程话术；仅向用户输出业务语义结果（如已匹配模板、已更新参数、可开始生成合同）。

## 主流程

### Step 1：推送主流程开始

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft start {exec_id} agent_start '🚀 合同起草流程开始' '{\"user_input_text\":\"{user_input_text}\",\"file_list\":\"{file_list}\"}' '{\"message\":\"合同起草主流程开始\"}' {session_id} {user_id} '' '' '合同起草智能体' '合同起草开始'")
```

### Step 2：生成 `exec_id`

```bash
execute_shell_command("python3 -c \"import uuid; print(uuid.uuid4())\"")
```

### Step 3：检查附件

先读取 `file_list`，然后根据情况推送：

**有可用附件时**，推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} file_list_checked '' '{\"file_list\":\"{file_list}\"}' '{\"has_attachment\":true,\"attachment_count\":1}' {session_id} {user_id} '' '' '合同起草智能体' '附件检查完成'")
```

**无可用附件时**，推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} attachment_missing '' '{\"file_list\":\"{file_list}\"}' '{\"message\":\"未发现可用合同附件\"}' {session_id} {user_id} '' '' '合同起草智能体' '未发现合同附件'")
```

### Step 4：模板检索

#### 有附件

调用内部附件匹配脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/match_by_file.py {session_id} {user_id} {exec_id} '{file_ref}'")
```

#### 无附件

如果用户意图明确，调用语义匹配脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/template_match.py {session_id} {user_id} {exec_id} '{user_input_text}'")
```

如果用户意图不明确，必须推送并追问：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} user_intent_required '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"message\":\"需要用户补充合同类型\"}' {session_id} {user_id} '' '' '合同起草智能体' '需要补充合同类型'")
```

向用户回复：

```text
请问您要起草哪一类合同？例如采购合同、销售合同、租赁合同、服务合同等。
```

### Step 5：处理模板检索结果

如果脚本返回 `need_user_intent = true`，继续追问，不进入后续流程。

如果脚本返回 `total > 0`：

1. 推送 `template_selection_required`
2. 向用户展示模板列表
3. 等待用户确认序号

推送示例：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} template_selection_required '' '{\"template_count\":{template_count}}' '{\"message\":\"需要用户确认模板\"}' {session_id} {user_id} '' '' '合同起草智能体' '等待确认模板'")
```

展示模板时优先输出：

- 模板名称 `title`
- 模板描述 `description`
- 分类 `category`
- 模型版本 `version`
- 参数数量：必须基于该模板 `param_schema_json` 的实际参数个数（叶子字段数）展示，禁止直接使用其他来源的估算值

推荐回复格式：

```markdown
已为您匹配到以下合同模板，请选择要使用的模板：

1. **软件产品销售合同**
   模板名称：软件产品销售合同
   说明：软通智慧向甲方提供软件产品的销售合同，涵盖软件产品交付、安装验收、维护服务、培训、价款支付、权利保证、保密约定等条款。适用于企业间软件产品采购场景，明确了双方权利义务、知识产权保护、违约责任及争议解决方式。
   类型：销售合同
   模型版本：v1.0
   参数数量：20

请回复序号确认；如需跳过模板直接起草，请回复：`0`
```

### Step 6：用户确认模板

如果用户回复 `0`、`跳过模板`、`直接起草`、`跳过`，，必须：

1. 推送 `template_skipped`
2. 进入 Step 9 自由起草

如果用户确认模板，必须记录：

- `selected_template_id`
- `selected_template_url`
- `selected_template_params_schema`
- `selected_template_file_path`

并推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} template_selected '' '{\"selected_template_id\":\"{selected_template_id}\"}' '{\"selected_template_url\":\"{selected_template_url}\"}' {session_id} {user_id} '' '' '合同起草智能体' '已确认模板'")
```

### Step 7：参数整理与补齐

用户确认模板后，先把该模板原始的 `param_schema_json` 写入临时文件：

```text
/tmp/copaw_params_{exec_id}.json
```

文件内容直接使用 `selected_template_params_schema` 原始数据，不要转换结构。然后调用内部参数推送脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_params.py /tmp/copaw_params_{exec_id}.json {exec_id} {session_id} {user_id}")
```

该脚本的职责只有两件事：

1. 读取确认模板对应的原始 `param_schema_json`
2. 在 Redis 推送的 `output` 中原样输出 `param_schema_json`，并附带可直接渲染表格的 `param_table` 与可直接回复给用户的 `param_table_markdown`

不要把 `param_schema_json` 转成 `params` 数组、表单结构或其他加工格式。

事件语义要求：

1. 必须先推送 `template_params_finished`，表示前端可以读取 `output.param_schema_json`、`output.param_table` 和 `output.param_table_markdown`，并开始或刷新动态表单 / 参数表格渲染
2. 再根据是否仍有缺参，继续推送 `template_params_required` 或 `template_params_completed`

模板确认后的首轮用户提示要求：

1. 第一次进入 Step 7 时，除了展示参数总表，还必须明确告诉用户：现在进入的是“合同信息整理阶段”
2. 必须明确告诉用户：如果不想手工逐项填写，可以直接上传项目资料，我会根据资料自动分析并填写合同信息
3. 必须明确告诉用户：自动填写后的结果会先回填表格，再由用户确认或修改

推荐首轮提示：

````markdown
已为您确认模板，接下来进入合同信息整理阶段。

您可以直接在右侧参数表中批量修改；如果您不想逐项手填，也可以现在上传项目背景材料、报价单、招标文件、需求说明或会议纪要，我会根据材料内容自动分析并填写合同信息，先回填到表格，再由您确认或修改。

{param_table_markdown}
````

#### Step 7A：根据上传项目附件自动填写合同信息

如果当前会话存在已上传的项目材料、背景文档、招投标文件、报价单、清单、邮件纪要、需求说明、采购申请、立项材料或其他业务附件，**必须在 Step 7 内优先执行一次“根据附件自动填写”**，然后再决定如何向用户追问。

这个子阶段的目标是：让用户尽量少手填，系统先根据附件内容自动填写能确定的合同信息，再把结果渲染到右侧参数表和聊天中的 Markdown 参数表，供用户直接修改。

触发条件：

1. 已确认模板，且已拿到 `selected_template_params_schema`
2. 当前处于合同信息整理阶段
3. 当前对话中存在可用附件，尤其是项目背景材料、合同补充材料、商务文件、采购信息、联系人信息、付款说明、产品清单等

作用域强约束：

1. 只能在 Step 7 使用
2. 不能在模板确认前把附件内容当作最终参数直接落库
3. 不能在 Step 8 / Step 9 再单独开启“重新自动抽参”流程
4. 若用户后续继续上传项目材料，系统允许基于最新材料继续覆盖并更新已有参数值

执行要求：

1. 先推送 `template_params_auto_extract_started`
2. 基于当前模板参数字段逐项阅读和理解附件内容，优先利用字段名、`desc`、当前上下文、已识别合同类型做语义映射
3. 必须优先尝试一次性抽取多个字段，不要只抽一个参数
4. 只对高置信度字段直接回写；低置信度字段保留为空，稍后集中向用户确认
5. 每个自动回填的值，都必须能在附件内容、用户显式输入或已确认参数中找到依据
6. 自动回填后，更新 `/tmp/copaw_params_{exec_id}.json`，要求保持原始 `param_schema_json` 结构不变，只修改对应字段的 `value`
7. 实际执行时，优先调用内部自动填写脚本：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/auto_extract_params.py /tmp/copaw_params_{exec_id}.json {exec_id} {session_id} {user_id} '{file_list}'")
```

1. 该脚本会自动完成以下动作：
   - 合并当前轮附件与此前已上传的项目材料
   - 自动填写高置信度合同信息并回写 `/tmp/copaw_params_{exec_id}.json`
   - 自动重新执行 `push_params.py`
   - 通过 Redis 刷新 `output.param_schema_json`、`output.param_table`、`output.param_table_markdown`
2. 然后推送 `template_params_auto_extract_finished`
3. 再根据最新结果继续推送 `template_params_finished`，并决定是否推送 `template_params_required` 或 `template_params_completed`

多附件与持续上传规则：

1. 用户一次上传多个项目材料时，必须把这些附件视为同一轮合同信息整理输入，联合分析，不要只读取第一个文件
2. 用户在 Step 7 后续再次上传材料时，必须把它视为“继续补充合同信息”的新一轮输入，而不是重启整个合同流程
3. 新上传材料应在已有参数基础上继续更新 `/tmp/copaw_params_{exec_id}.json`
4. 如果新附件与旧附件之间冲突，允许按“最新上传材料优先”覆盖当前参数值；最终以用户结束 Step 7 时的参数表为准
5. 每新增一轮附件后，都必须重新执行自动填写、重新执行 `push_params.py`，并重新展示完整参数总表

自动提取映射规则：

1. 同一附件里出现公司名称、法定代表人、联系人、电话、邮箱、地址、签约日期、交付日期、金额、税率、付款节点、产品清单、补充附件说明等，必须尽量一轮映射到多个参数
2. 字段名不完全一致时，允许结合 `field_name`、`desc`、同组字段语义进行等价匹配
3. 如果附件中有表格、清单、分期付款、日期、金额大小写等结构化信息，应优先提取为对应参数值，而不是要求用户手工复述
4. 如果一个值明显属于多个字段候选，先不要写入；统一列为待确认项
5. 对金额、日期、税率、比例、地址、联系人等常见商务字段，应优先保持附件原文表达；必要时再做轻度标准化

写回参数文件要求：

1. 不要把整个参数文件改造成别的结构
2. 只允许在原始 `param_schema_json` 上回写 `value`
3. 未确定的字段保持空值
4. 每次自动抽取完成后，Redis 中的 `output.param_schema_json`、`output.param_table`、`output.param_table_markdown` 都必须反映最新值

自动填写后的对话要求：

1. 不要直接对用户说“请一个个填写参数”
2. 必须先告诉用户：已根据上传项目材料自动填写了一批合同信息，并已同步到参数表
3. 必须在聊天窗口重新展示最新的 `param_table_markdown`
4. `param_table_markdown` 面向普通用户阅读，首列应理解为“填写事项/说明”，不能把内部参数名当作展示标题或展示内容
5. 然后明确告诉用户：可以直接在右侧表格中批量修改，也可以继续让我根据附件和上下文补充剩余参数
6. 如果仍缺少字段，再集中列出缺失项和存疑项，不要拆成多轮机械追问

自动填写后的推荐回复模板：

````markdown
我已根据您上传的项目材料，自动填写并回填了一批合同信息，您现在可以直接在右侧参数表中修改。

{param_table_markdown}

当前仍需要您确认或补充的项目如下：
{missing_fields_human_readable}

如果您愿意，我也可以继续根据附件内容和上下文，帮您补充剩余参数；您也可以直接在右侧表格一次改多个字段。
````

#### Step 7B：无附件或自动填写不足时引导用户上传项目资料

如果当前处于 Step 7，且满足以下任一情况，必须主动引导用户上传项目资料，而不是立刻进入低效的一问一答：

1. 当前没有可用附件
2. 已有附件，但自动填写后仍有较多关键缺失字段
3. 用户明确表示“项目很多、不想手填、希望系统自动分析并填写”

引导目标：

1. 明确告诉用户：**上传项目资料只在合同信息整理阶段可用**
2. 明确告诉用户：上传后系统会基于材料内容自动分析、提取、赋值，并回填到右侧参数表
3. 明确告诉用户：用户仍然可以在表格中继续修改最终值

允许引导用户上传的资料类型包括但不限于：

- 项目背景材料
- 招标文件 / 投标文件
- 报价单 / 清单 / 采购单
- 需求说明 / 立项材料
- 会议纪要 / 邮件确认
- 联系人信息、付款条款、交付要求相关文档

固定引导要求：

1. 不能泛泛地说“请补充参数”
2. 要优先建议用户上传项目资料，让系统自动分析
3. 要明确说明这是为了减少手工填写成本
4. 要明确说明提取结果会先回填表格，再由用户确认

推荐引导话术：

````markdown
如果您觉得手动逐项填写太麻烦，可以直接在当前合同信息整理阶段上传一份项目资料，例如项目背景材料、招标文件、报价单、需求说明或会议纪要。

我会根据您上传的材料自动分析其中的合同关键信息，并尽量完成自动填写和回填，然后把结果回填到右侧参数表，供您直接确认或修改。

您上传后，我会优先帮您自动提取以下类型的信息：合同主体、联系人、签署日期、金额、税率、付款方式、交付要求、产品/服务清单等。
````

#### Step 7C：持续上传项目材料并循环更新合同信息

Step 7 不是一次性的。只要用户仍然处于合同信息整理阶段，主智能体就必须允许用户持续上传新的项目材料，并在每一轮上传后继续自动填写、更新信息、刷新表格。

循环处理要求：

1. 用户上传新的项目材料后，优先将该动作识别为 `continue_fill + upload_material_for_auto_extract`
2. 立即把新材料并入当前上下文，与之前附件一起分析
3. 重新执行根据附件自动填写
4. 回写 `/tmp/copaw_params_{exec_id}.json`
5. 重新执行 `push_params.py`
6. 重新展示最新 `param_table_markdown`
7. 明确告诉用户哪些参数已更新、哪些参数仍待确认

Step 7 的退出条件：

1. 用户明确表示“不要继续整理信息了，开始生成合同”
2. 用户明确表示“按当前参数开始模板生成”
3. 用户明确表示“这些参数够了，直接生成预览稿/正式稿”
4. 用户明确表示“不要模板了，改为自由起草”

只要用户还在持续上传项目材料、继续补充上下文、要求“再分析一下附件”“继续根据资料自动填写”，就**不能**进入 Step 8 或 Step 9。

Step 7 循环中的固定回复要求：

1. 每轮处理后都要告诉用户：可以继续上传更多项目材料，我会继续更新参数
2. 每轮处理后都要告诉用户：如果不再需要继续整理合同信息，可以明确回复“开始渲染模板”或“转自由起草”
3. 不要因为当前缺参变少了，就自动替用户结束合同信息整理阶段

推荐循环提示模板：

````markdown
我已根据您最新上传的项目材料，更新了一轮合同参数，最新结果已同步到右侧参数表。

{param_table_markdown}

如果您还有其他项目材料，可以继续上传，我会继续分析并更新参数。

如果您确认现在不需要继续整理合同信息了，也可以直接告诉我：
- 开始模板生成
- 先生成预览稿
- 不用模板了，改为自由起草
````

如果脚本返回有 `missing_fields`：

1. 如果当前存在可用附件且尚未执行自动填写，必须先执行上面的 Step 7A，再决定是否追问用户
2. 不要直接继续机械追问，必须先向用户展示当前参数总览，优先使用表格化方式说明“填写事项 / 当前值 / 状态”；不要展示“参数名称”这类技术化列名，更不能把 `field_name`、`path`、英文 key 直接给用户看
3. 必须主动询问用户下一步意愿，并将意愿归类为以下三种之一：
   - `continue_fill`：继续补充剩余参数
   - `preview_render`：按当前已填写参数先生成预览稿
   - `switch_to_llm`：放弃模板生成，转自由起草
4. 如果用户表达不明确，必须继续追问，直到意愿明确后再进入后续分支
5. 每次用户补充信息后，更新 `/tmp/copaw_params_{exec_id}.json`
6. 每次参数文件更新后，都必须重新执行 `push_params.py`

后续补充信息时，默认优先采用“批量收集”而不是“一次只问一个字段”：

1. 主智能体先基于 `output.param_table_markdown` 在聊天对话框中展示参数总览表；如果该字段不存在，再退回基于 `output.param_table.rows` 自行生成 Markdown 表格
2. 如果已有附件自动填写结果，先告诉用户“系统已自动填写一批合同信息，可直接在表格中修改”，再引导用户一次填写多个字段
3. 用户如果只愿意逐条回答，才退回单字段追问模式
4. 每次用户补充信息后，都要把最新 `value` 回写到 `/tmp/copaw_params_{exec_id}.json`，并重新执行 `push_params.py`，让 Redis 中的 `output.param_schema_json`、`output.param_table` 与 `output.param_table_markdown` 始终携带用户最新采集到的值，供前端实时刷新表单，并供聊天窗口同步展示
5. 如果用户表示“我上传个项目材料你帮我整理”“我发附件你来填”“根据资料自动回填”等意图，必须把它识别为 Step 7 的合法补充信息动作，并优先引导其上传附件，而不是让其继续手填

批量填写时，允许用户使用以下任一格式：

- Markdown 表格
- JSON 对象
- 多行键值对，例如 `甲方名称=软通智慧`
- 自然语言批量描述，例如“甲方是软通智慧，乙方是某某公司，签约日期是 2026-03-08”

批量填写解析要求：

1. 必须优先尝试从用户一轮回复中提取多个字段，不要默认只更新一个值
2. 必须结合字段名、字段说明 `desc`、上下文语义判断“用户这句话对应哪个参数”
3. 对高置信度字段直接回写
4. 对低置信度或存在歧义的字段，集中列出后一次性请用户确认，不要拆成很多轮
5. 每次完成一轮解析后，都要重新推送 `template_params_finished`

对话框展示要求：

1. 每次出现 `template_params_finished` 后，聊天窗口都必须展示最新的 Markdown 参数表
2. 表格中必须同时展示“已填写”和“待填写”项，不能只列缺失字段
3. 当用户补充了一批参数后，必须重新展示更新后的完整表格，而不是只回复“已更新”
4. 若需要自行生成 Markdown 表格，首列只能展示 `desc` 对应的业务说明/填写事项；禁止输出 `contract_effect_year`、`company_a` 这类内部字段名，即使它们存在于 schema 中
5. 如果字段很多，可以优先展示完整表格；若确实过长，可先展示前若干项并明确说明“其余字段已同步到右侧参数总表”
6. 如果本轮参数来自附件自动提取，必须明确提示“以下内容已根据上传项目材料自动提取，您可直接在右侧表格修改”

缺参时推荐用户提示模板：

````markdown
我已为您整理出当前合同模板需要填写的参数总表，并同步了最新数据。

建议您优先直接按表格一次填写多个字段，这样会比一问一答更快。

如果您觉得手工填写太麻烦，也可以直接上传项目背景材料、招标文件、报价单、需求说明或会议纪要；我会在当前合同信息整理阶段根据材料内容自动分析并回填信息，您再在右侧表格中确认或修改即可。

{param_table_markdown}

当前仍缺少：
{missing_fields_human_readable}

您可以直接这样回复我：

```text
甲方名称=xxx
乙方名称=xxx
签署日期=2026-03-08
付款方式=验收后7个工作日内付款
```

您希望我下一步怎么处理？

1. 继续补充剩余参数
2. 按当前已填内容先生成预览稿
3. 放弃模板生成，转自由起草

请直接回复 `1`、`2` 或 `3`，也可以直接告诉我您想怎么做。
````

用户意愿识别规则：

- 如果用户回复 `1`、`继续补充`、`继续填写`、`补充信息`、`继续完善`，归类为 `continue_fill`
- 如果用户回复 `2`、`先预览`、`先渲染看看`、`先出一版`、`按当前内容生成`、`先根据当前参数起草一份合同`，归类为 `preview_render`
- 如果用户回复 `3`、`自由起草`、`重新起草`、`不要模板了`、`不用模板了`、`跳过模板直接写`，归类为 `switch_to_llm`
- 如果用户回复“我上传资料你帮我整理”“我发项目材料你来填”“根据附件自动回填”“你先从资料里自动填写”等，归类为 Step 7 内的 `continue_fill + upload_material_for_auto_extract`，优先进入根据附件自动填写，而不是普通文字追问

上下文判定优先规则：

1. 如果模板尚未确认，用户说“直接起草”“先出一版”，优先判断为跳过模板或自由起草意图
2. 如果模板已确认，且当前仍在 Step 7，用户说“直接生成”“开始起草”“出合同吧”“写一份合同”“起草一份合同”“直接根据当前内容起草一份合同”，优先判断为**结束合同信息整理并进入模板生成**，而不是直接进入自由起草
3. 在 Step 7 中，“起草一份合同”默认含义是“按当前已提好的参数进行模板生成”；除非用户同时明确表示不要模板，否则禁止把这句话识别为自由起草
4. 如果模板已确认，但用户明确说“不要模板了”“不用这个模板”“改成你直接写一版”“别走模板了，直接写”，才归类为 `switch_to_llm`
5. 如果用户一边上传新材料，一边说“你继续整理”“再分析一下这个附件”，仍归类为 Step 7 持续补充信息，不能进入渲染
6. 如果用户表达同时包含“继续传资料”和“先出一版/起草一份合同”，必须追问当前这一步究竟是继续补充信息、模板预览生成、还是放弃模板自由起草
7. 若上下文显示用户仍在补充附件或修订信息，默认保持在 Step 7，不要擅自结束合同信息整理阶段

固定对话要求：

- 不要自由发挥生成多套问法，优先使用“状态说明 + Markdown 参数总表 + 缺失字段摘要 + 选项确认”的固定模板
- 每次只做一轮明确引导，等用户表达意愿后再进入下一步
- 若用户表达混杂，例如“先预览一下，不行就直接起草”，优先追问确认当前这一步是 `preview_render` 还是“按当前参数正式模板生成”；只有用户明确否定模板时，才允许转 `switch_to_llm`

各分支处理规则：

- `continue_fill`：若当前仍有可用附件可继续分析，优先先做附件辅助自动填写，再结合用户补充；支持用户持续上传多个项目材料并循环更新信息；只有当用户明确要求“一个个问”或当前字段歧义过大时，才逐项追问；每采集到一轮新信息，都必须回写文件并重新执行 `push_params.py`
- `preview_render`：允许在参数未补齐时进入预览生成；但必须明确告知用户这是预览稿，不是最终定稿
- `switch_to_llm`：只有在用户明确放弃模板的前提下才进入 Step 9 自由起草；若已有用户已填写的参数，必须作为自由起草的重要输入上下文继续使用；同时必须记录 `draft_entry_reason`

### Step 8：模板生成

进入 Step 8 的前提不是“合同信息自动填写完成”本身，而是**用户明确结束合同信息整理阶段，并要求按当前信息开始模板生成**。

进入 Step 8 前必须先做上下文确认：

1. 模板已确认
2. 当前不再处于“继续上传项目材料 / 继续自动填写”状态
3. 用户明确表达了以下任一意图：
   - 开始模板生成
   - 生成合同
   - 写一份合同
   - 起草一份合同
   - 直接根据当前内容起草一份合同
   - 按当前参数出正式稿
   - 先生成预览稿
4. 若用户说“直接起草”，必须结合上下文判断：
   - 若当前模板已确认且仍在 Step 7，默认解释为“按当前参数进入模板生成”
   - 若用户同时明确表示不要模板，才进入 Step 9 自由起草

Step 8 关键判定补充：

1. 在合同信息整理阶段，用户说“写一份合同”“起草一份合同”“根据当前内容起草一份合同”，应视为**开始模板生成**的口语化表达
2. 上述表达的本质含义是：用户认为当前信息已经足够，希望系统基于当前信息生成合同文件
3. 因此必须调用模板生成 API，而不是进入自由起草逻辑
4. 只有用户明确补充“不要模板”“不用这个模板”“你直接自由写一版”时，才改走 Step 9

如果所有参数已补齐，但用户尚未明确表示“开始生成/渲染”，不要自动渲染；必须先给出一次确认提示。

模板生成前推荐确认话术：

```text
当前合同信息已整理完成。如您不需要继续补充信息，我可以按当前内容开始模板生成。
如果您还有新的项目材料，也可以继续上传，我会先更新信息后再生成合同。
```

在用户明确确认后，调用**模板系统渲染接口**。本步骤只适用于**已经匹配到并确认合同模板**的场景，禁止把自由起草也走到这里。

可通过内部渲染脚本统一转调模板系统 API：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/render_template.py '{selected_template_url}' /tmp/copaw_params_{exec_id}.json {exec_id} {session_id} {user_id}")
```

该脚本当前对应的是模板系统合同生成接口，输入前提必须满足：

1. `selected_template_url` 已存在，且是模板系统返回的 `.docx` 模板地址
2. 参数文件 `/tmp/copaw_params_{exec_id}.json` 已完成整理
3. 本次生成目标是“基于已匹配模板渲染合同”，而不是自由起草

如果用户在缺参时明确选择 `preview_render`，允许先按当前已填参数生成预览稿。预览稿仍然属于**模板系统预览生成**，不是自由起草，此时调用：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/render_template.py '{selected_template_url}' /tmp/copaw_params_{exec_id}.json {exec_id} {session_id} {user_id} preview")
```

预览生成对用户的提示要求：

```text
我会先按您当前已填写的信息生成一份预览稿，未填写的字段可能保持为空或以模板默认占位呈现。您确认后，我可以继续帮您补充合同信息并生成正式版。
```

如果渲染成功：

1. 记录 `render_result_url`
2. 若本次为正式渲染，推送主流程结束事件
3. 返回文件地址给用户

如果本次为预览生成成功：

1. 返回预览文件地址给用户
2. 明确告知该结果是预览稿，不是最终定稿
3. 继续询问用户是：
   - 继续补齐参数后生成正式版
   - 保持当前内容直接转自由起草
   - 结束本轮预览

预览稿返回给前端时，必须保证结果中能区分：

- `render_mode = preview`
- `generation_mode = template_render`
- `result_type = docx`

如果渲染失败：

1. 推送 `template_render_failed`
2. 告知用户可选择继续补充信息后重试，或转自由起草
3. 只有在用户明确选择放弃模板时，才进入 Step 9 自由起草

### Step 9：自由起草

只有以下场景允许进入本步骤：

- 模板未匹配到
- 用户明确跳过模板
- 模板生成失败
- 模板已确认，但用户明确表示“不要模板了，改为你直接起草”

上下文判定强约束：

1. 模板已确认且用户仍在上传材料、修订信息、要求继续自动填写时，禁止进入自由起草
2. 模板已确认后，用户说“直接起草/出一版/写一份合同/起草一份合同”但未明确否定模板时，优先判断为模板生成意图，而不是自由起草
3. 只有用户明确拒绝模板路线时，才允许把该意图识别为 `switch_to_llm`

**自由起草强约束：禁止在聊天窗口流式展示起草过程。** 自由起草必须在后台静默执行，并且必须与 Step 8 的模板系统生成严格区分。自由起草不允许再调用模板系统渲染接口；而是要先确定本地待保存的合同文件，再调用**自由起草模板保存接口**完成合同文件生成与落库。聊天窗口不显示中间 token 流。

进入自由起草前，必须先明确并记录 `draft_entry_reason`，只能取以下值之一：

- `template_not_found`
- `template_skipped_by_user`
- `template_render_failed`
- `user_selected_llm_after_partial_fill`

进入本步骤前必须推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} llm_draft_started '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"message\":\"开始自由起草合同\"}' {session_id} {user_id} '' '' '合同起草智能体' '开始自由起草'")
```

然后直接在本技能内生成完整合同 Markdown，保存到本地临时文件，用于后续调用自由起草模板保存接口：

```text
/tmp/copaw_draft_{exec_id}.md
```

使用：

```text
write_file(path="/tmp/copaw_draft_{exec_id}.md", content="{contract_md}")
```

起草要求：

1. 输出必须是完整合同 Markdown，不要附加解释。
2. 至少包含：合同标题、合同主体、标的/服务内容、金额与支付、履行期限、权利义务、违约责任、争议解决、签署页。
3. 若已有模板参数或用户明确信息，必须优先使用，不得遗漏。

然后调用**自由起草模板保存脚本**，由脚本内部去请求自由起草模板保存接口，而不是在技能文档中直接拼裸 `curl`：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/free_draft_save.py /tmp/copaw_draft_{exec_id}.docx {exec_id} {session_id} {user_id} '{draft_entry_reason}' '{corrections_json}'")
```

自由起草接口说明：

1. 该接口名称为**自由起草模板保存接口**
2. 只在 `draft_entry_reason` 已确定且用户明确放弃模板路线后调用
3. `file` 必须是本地文件路径，表示待保存/待处理的合同文档
4. `corrections` 用于传入本轮自由起草已确认的关键结构化修正信息，例如合同名称、金额、主体名称等
5. 该接口与 Step 8 的模板系统渲染接口属于两条不同链路，绝不能复用
6. `SKILL.md` 中只描述“调用哪个脚本”，不要把接口细节散落在技能流程中
7. 当前接口成功返回格式示例为：`{"url":"http://...docx"}`，脚本需从返回 JSON 中提取 `url` 作为最终结果地址

自由起草执行要求补充：

1. 若当前只有 Markdown 草稿，必须先转换为本地 docx 文件，再作为 `file` 上传
2. 返回结果若包含可下载 URL / 文件 ID / 保存结果，应统一作为自由起草产物回传前端
3. Redis 事件中仍需标记 `generation_mode = llm_draft`，避免与模板生成混淆
4. `free_draft_save.py` 脚本内部负责：
   - 组装 `multipart/form-data`
   - 调用 `http://10.17.96.197:8088/api/contracts/smart-create1`
   - 统一处理超时、异常、返回值解析
   - 按现有事件规范推送成功/失败结果

如果**自由起草模板保存接口调用成功**，推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft running {exec_id} llm_draft_success '' '{\"user_input_text\":\"{user_input_text}\"}' '{\"result_type\":\"docx\",\"result_url\":\"{file_url}\"}' {session_id} {user_id} '' '' '合同起草智能体' '自由起草完成'")
```

自由起草结果返回给前端时，必须保证结果中能区分：

- `render_mode = final`
- `generation_mode = llm_draft`
- `result_type = docx`
- `draft_entry_reason`

如果失败，推送 `llm_draft_failed`，并给用户返回可理解错误。

### Step 10：主流程结束

最终成功后必须推送：

```bash
execute_shell_command("python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py contract_draft end {exec_id} agent_end '✅ 合同起草流程完成' '{\"selected_template_id\":\"{selected_template_id}\",\"final_mode\":\"template_render_or_llm\"}' '{\"result_url\":\"{result_url}\",\"result_type\":\"docx\"}' {session_id} {user_id} '' '' '合同起草智能体' '合同起草完成'")
```

向用户输出：

```text
✅ 合同起草完成！

📄 文件地址：{result_url}

如需继续修改，请直接告诉我需要调整的条款或参数。
```

## 决策矩阵

- 未上传附件 + 意图不明确：先追问合同类型
- 未上传附件 + 意图明确 + 匹配到模板：模板确认 -> 补充合同信息 -> 等用户明确结束信息整理 -> 正式生成或预览生成
- 未上传附件 + 意图明确 + 未匹配到模板：自由起草
- 已上传附件 + 匹配到模板：模板确认 -> 根据附件自动填写 -> 支持持续上传材料并循环更新信息 -> 用户明确结束信息整理 -> 正式生成或预览生成
- 已上传附件 + 未匹配到模板：自由起草
- 任意阶段用户主动跳过模板：自由起草
- 模板生成失败：由用户选择继续补充信息后重试或转自由起草
- 模板已确认 + 用户仍在上传资料/要求继续分析：保持 Step 7，不进入渲染
- 模板已确认 + 用户说“开始起草/生成合同/写一份合同/起草一份合同”但未否定模板：优先走模板生成
- 模板已确认 + 用户明确说“不要模板了，你直接写”：自由起草

## 禁止事项

- 禁止再调用 `contract_template_match`
- 禁止再调用 `contract_template_params`
- 禁止再调用 `contract_draft_llm`
- 禁止在未确认模板时直接渲染
- 禁止在缺参时未经用户同意直接进入正式渲染
- 禁止在可检索模板时跳过模板阶段
- 禁止在 Step 7 之外把根据附件自动填写当作独立流程启用
- 禁止用户仍在持续上传项目材料时擅自结束 Step 7
- 禁止把模板已确认场景下的“直接起草/先出一版/写一份合同/起草一份合同”机械识别成自由起草
- 禁止自由起草时在聊天窗口流式展示，必须后台静默执行并只返回 docx URL
