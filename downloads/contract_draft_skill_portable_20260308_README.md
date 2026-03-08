# contract_draft 技能迁移包说明

## 包内容

- `contract_draft/`
  - `SKILL.md`
  - `scripts/`
    - `event_meta.py`
    - `match_by_file.py`
    - `push.py`
    - `push_event.py`
    - `push_params.py`
    - `redis_push.py`
    - `render_template.py`
    - `search_common.py`
    - `template_match.py`
    - `word_gen.py`

## 推荐落地目录

迁移到目标项目时，建议保持以下目录结构：

```text
~/.copaw/active_skills/
└── contract_draft/
    ├── SKILL.md
    └── scripts/
        ├── event_meta.py
        ├── match_by_file.py
        ├── push.py
        ├── push_event.py
        ├── push_params.py
        ├── redis_push.py
        ├── render_template.py
        ├── search_common.py
        ├── template_match.py
        └── word_gen.py
```

原因：

- `SKILL.md` 里的命令路径固定按 `~/.copaw/active_skills/contract_draft/...` 编写
- 直接按这个路径放置，迁移后无需改 prompt 指令

## 运行依赖

Python 依赖建议至少具备：

- `requests`
- `redis`
- `python-docx`
- `pdfplumber`

如需启用 Redis 事件推送，还需要目标环境可访问 Redis。

## 关键环境变量

- `COPAW_SESSION_ID`
- `COPAW_USER_ID`
- `COPAW_API_BASE`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `REDIS_DB`
- `TEMPLATE_SEARCH_API`
- `TEMPLATE_RENDER_API`
- `TEMPLATE_FILE_BASE_URL`
- `CONTRACT_STORAGE_DIR`
- `COPAW_INPUT_FILE_URLS`
- `COPAW_SKILL_LABEL`

## 迁移步骤

1. 将 `contract_draft/` 目录复制到目标机器的 `~/.copaw/active_skills/`
2. 安装依赖：`requests redis python-docx pdfplumber`
3. 配置目标环境变量，确保模板检索 API、模板渲染 API、文件存储目录、Redis 地址可用
4. 在目标项目中重新加载或重启 CoPaw 服务
5. 用下方冒烟测试确认技能脚本可独立工作

## 冒烟测试

### 1. 事件推送脚本

```bash
python3 ~/.copaw/active_skills/contract_draft/scripts/push_event.py \
  contract_draft running test-exec template_params_finished '' \
  '{"exec_id":"test-exec"}' \
  '{"param_schema_json":{"party_a_name":{"desc":"甲方名称","value":"测试甲方"}}}' \
  test-session default '' '' '合同起草智能体' '参数表单数据已就绪'
```

预期：

- 标准输出返回 `ok: true`
- 若 Redis 可用，流里会收到 `render_type=template_params_finished`

### 2. 参数推送脚本

```bash
python3 ~/.copaw/active_skills/contract_draft/scripts/push_params.py \
  /tmp/test_params.json test-exec test-session default
```

预期：

- 输出中包含 `param_schema_json`
- 输出中包含 `missing_fields`
- `template_params_finished` 事件里一定带 `output.param_schema_json`

### 3. 自由起草 Word 生成

```bash
python3 ~/.copaw/active_skills/contract_draft/scripts/word_gen.py \
  /tmp/copaw_draft_verify.md ~/.copaw/contracts/drafts verify-exec test-session default
```

预期：

- 生成 `.docx`
- 输出中包含 `file_url`

## 前端联调约定

- 前端应以 `render_type = template_params_finished` 作为动态表单刷新信号
- 每次收到该事件，都从 `output.param_schema_json` 读取最新 schema 和最新 `value`
- `template_params_required` 表示仍有缺参
- `template_params_completed` 表示当前参数已补齐

## 当前迁移测试结论

已在独立临时目录中验证以下脚本可脱离本仓库直接执行：

- `push_event.py`
- `push_params.py`
- `template_match.py`
- `word_gen.py`

说明该技能目录已具备可迁移性，可作为独立技能包交付。
