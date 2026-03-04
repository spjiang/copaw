# CoPaw CLI 命令手册

> 工作目录默认为 `~/.copaw`，可通过环境变量 `COPAW_WORKING_DIR` 覆盖。

---

## 全局选项

```bash
copaw [OPTIONS] COMMAND [ARGS]...
```

| 选项 | 说明 |
|------|------|
| `--host TEXT` | 指定 API 主机（供 chats/cron 等命令连接） |
| `--port INTEGER` | 指定 API 端口 |
| `-h, --help` | 显示帮助 |

---

## `copaw init` — 初始化工作目录

创建 `~/.copaw/config.json`、`AGENTS.md` 等配置文件，并同步内置 skills。

```bash
copaw init [OPTIONS]
```

| 选项 | 说明 |
|------|------|
| `--force` | 强制覆盖已有的 `config.json` 和 MD 文件 |
| `--defaults` | 全部使用默认值，不弹出交互提示 |
| `--accept-security` | 跳过安全声明确认（配合 `--defaults` 用于脚本/Docker） |

**常用示例**

```bash
# 交互式初始化（首次使用）
copaw init

# 脚本/CI 环境下静默初始化
copaw init --defaults --accept-security
```

---

## `copaw app` — 启动服务

启动 CoPaw FastAPI 后端及 Web 控制台（http://127.0.0.1:8088）。

```bash
copaw app [OPTIONS]
```

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--host TEXT` | `127.0.0.1` | 监听主机 |
| `--port INTEGER` | `8088` | 监听端口 |
| `--reload` | — | 开启热重载（仅开发用） |
| `--workers INTEGER` | `1` | Worker 进程数 |
| `--log-level` | `info` | 日志级别：`critical/error/warning/info/debug/trace` |
| `--hide-access-paths TEXT` | `/console/push-messages` | 隐藏指定路径的访问日志（可重复） |

**常用示例**

```bash
# 默认启动（需在项目根目录执行）
cd /path/to/CoPaw && copaw app

# 指定端口，开启调试日志
copaw app --port 9000 --log-level debug

# 开发模式（修改代码自动重载）
copaw app --reload
```

> **注意**：须在项目根目录（含 `console/dist/`）执行，否则 Web 界面无法加载。

---

## `copaw models` — 模型与提供商管理

```bash
copaw models COMMAND
```

### 子命令列表

| 子命令 | 说明 |
|--------|------|
| `list` | 显示所有提供商及当前配置 |
| `config` | 交互式配置提供商和激活模型 |
| `set-llm` | 交互式切换当前使用的 LLM 模型 |
| `config-key [PROVIDER_ID]` | 配置指定提供商的 API Key |
| `add-provider` | 添加自定义提供商 |
| `remove-provider` | 删除自定义提供商 |
| `add-model` | 向任意提供商添加模型 |
| `remove-model` | 从提供商中删除模型 |
| `download` | 从 HuggingFace / ModelScope 下载本地模型 |
| `local` | 列出已下载的本地模型 |
| `remove-local` | 删除已下载的本地模型 |
| `ollama-list` | 列出所有 Ollama 模型 |
| `ollama-pull` | 下载 Ollama 模型 |
| `ollama-remove` | 删除 Ollama 模型 |

**常用示例**

```bash
# 查看所有提供商
copaw models list

# 设置 DeepSeek API Key
copaw models config-key deepseek

# 交互式切换为 deepseek-reasoner
copaw models set-llm

# 添加自定义提供商
copaw models add-provider

# 下载 Ollama 模型
copaw models ollama-pull llama3.2
```

---

## `copaw channels` — 消息频道管理

管理 iMessage / Discord / 钉钉 / 飞书 / QQ / Console 等频道配置。

```bash
copaw channels COMMAND
```

| 子命令 | 说明 |
|--------|------|
| `list` | 显示当前所有频道的配置状态 |
| `config` | 交互式配置频道参数 |
| `add` | 安装自定义频道到 `custom_channels/` 并写入配置 |
| `install` | 仅安装频道文件到工作目录 |
| `remove` | 删除自定义频道 |

**常用示例**

```bash
# 查看所有频道状态
copaw channels list

# 交互式配置飞书/钉钉等频道
copaw channels config
```

---

## `copaw skills` — Skills 管理

```bash
copaw skills COMMAND
```

| 子命令 | 说明 |
|--------|------|
| `list` | 列出所有 skill 及启用/禁用状态 |
| `config` | 交互式启用/禁用 skill |

**自定义 Skill 目录**

| 路径 | 说明 |
|------|------|
| `~/.copaw/customized_skills/` | 放置自定义 skill（目录 + `SKILL.md`） |
| `~/.copaw/active_skills/` | 当前已激活的 skill（由 init/skills config 同步） |

**常用示例**

```bash
# 查看所有 skill 状态
copaw skills list

# 交互式启用/禁用 skill
copaw skills config
```

> 新增自定义 skill 后，运行 `copaw init --defaults --accept-security` 同步激活。

---

## `copaw chats` — 会话管理

通过 HTTP API 管理聊天会话（需要 `copaw app` 正在运行）。

```bash
copaw chats COMMAND [OPTIONS]
```

| 子命令 | 说明 |
|--------|------|
| `list` | 列出所有会话 |
| `get <chat_id>` | 查看指定会话详情（含消息历史） |
| `create` | 创建新会话 |
| `update <chat_id>` | 修改会话名称 |
| `delete <chat_id>` | 删除指定会话 |

### `chats list` 选项

| 选项 | 说明 |
|------|------|
| `--user-id TEXT` | 按用户 ID 过滤 |
| `--channel TEXT` | 按频道过滤：`console/imessage/dingtalk/discord/qq/feishu` |
| `--base-url TEXT` | 覆盖 API 地址 |

### `chats create` 选项

| 选项 | 说明 |
|------|------|
| `-f, --file FILE` | 从 JSON 文件创建（与内联参数互斥） |
| `--name TEXT` | 会话名称（默认 `New Chat`） |
| `--session-id TEXT` | Session ID，格式建议 `channel:user_id` |
| `--user-id TEXT` | 用户 ID |
| `--channel TEXT` | 频道名称（默认 `console`） |

**常用示例**

```bash
# 列出所有会话
copaw chats list

# 按飞书频道过滤
copaw chats list --channel feishu

# 按用户过滤
copaw chats list --user-id alice

# 查看指定会话的消息历史
copaw chats get <chat_id>

# 创建会话
copaw chats create --session-id "feishu:ou_xxx" --user-id alice --name "飞书对话"

# 删除会话
copaw chats delete <chat_id>
```

---

## `copaw cron` — 定时任务管理

通过 HTTP API 管理定时任务（需要 `copaw app` 正在运行）。

```bash
copaw cron COMMAND [OPTIONS]
```

| 子命令 | 说明 |
|--------|------|
| `list` | 列出所有定时任务 |
| `get <job_id>` | 查看指定任务详情 |
| `state <job_id>` | 查看任务运行时状态 |
| `create` | 创建定时任务 |
| `delete <job_id>` | 永久删除任务 |
| `pause <job_id>` | 暂停任务（不再按计划执行） |
| `resume <job_id>` | 恢复已暂停的任务 |
| `run <job_id>` | 立即触发一次执行（忽略计划时间） |

### `cron create` 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-f, --file FILE` | — | 从 JSON 文件创建（与内联参数互斥） |
| `--type [text\|agent]` | — | `text`：发送固定内容；`agent`：让 Agent 回答后发送结果 |
| `--name TEXT` | — | 任务显示名称 |
| `--cron TEXT` | — | Cron 表达式（5 字段：分 时 日 月 周） |
| `--channel TEXT` | — | 发送频道（`feishu/dingtalk/discord/qq/console`） |
| `--target-user TEXT` | — | 目标用户 ID |
| `--target-session TEXT` | — | 目标 Session ID |
| `--text TEXT` | — | 发送内容或 Agent 提问 |
| `--timezone TEXT` | — | 时区（如 `Asia/Shanghai`） |
| `--enabled/--no-enabled` | `enabled` | 创建后是否立即启用 |
| `--mode [stream\|final]` | — | `stream`：增量推送；`final`：仅发送最终结果 |

**常用示例**

```bash
# 每天早上 9 点通过飞书发送早报摘要（agent 模式）
copaw cron create \
  --type agent \
  --name "早报" \
  --cron "0 9 * * *" \
  --channel feishu \
  --target-user ou_xxxxxxxx \
  --target-session "feishu:sw:xxxx" \
  --text "请抓取今日新闻头条并用中文总结" \
  --timezone "Asia/Shanghai"

# 列出所有任务
copaw cron list

# 立即触发一次
copaw cron run <job_id>

# 暂停 / 恢复
copaw cron pause <job_id>
copaw cron resume <job_id>

# 删除任务
copaw cron delete <job_id>
```

---

## `copaw env` — 环境变量管理

管理工作目录中的环境变量（存储在 `~/.copaw/.env`）。

```bash
copaw env COMMAND
```

| 子命令 | 说明 |
|--------|------|
| `list` | 列出所有已设置的环境变量 |
| `set KEY VALUE` | 设置环境变量 |
| `delete KEY` | 删除环境变量 |

**常用示例**

```bash
# 设置 Tavily 搜索 API Key
copaw env set TAVILY_API_KEY tvly-xxxxxxxx

# 查看所有变量
copaw env list

# 删除变量
copaw env delete TAVILY_API_KEY
```

---

## `copaw clean` — 清理工作目录

删除工作目录（`~/.copaw`）中的数据。

```bash
copaw clean [OPTIONS]
```

| 选项 | 说明 |
|------|------|
| `--yes` | 跳过确认提示直接执行 |
| `--dry-run` | 仅列出将被删除的内容，不实际删除 |

**常用示例**

```bash
# 预览将被删除的内容
copaw clean --dry-run

# 确认清理
copaw clean --yes
```

---

## `copaw uninstall` — 卸载 CoPaw

删除 CLI 包装脚本和 PATH 配置项。

```bash
copaw uninstall [OPTIONS]
```

| 选项 | 说明 |
|------|------|
| `--purge` | 同时删除所有数据（config、chats、模型等） |
| `--yes` | 跳过确认提示 |

---

## 快速参考卡

| 场景 | 命令 |
|------|------|
| 首次安装后初始化 | `copaw init` |
| 静默初始化（脚本） | `copaw init --defaults --accept-security` |
| 启动服务 | `cd /path/to/CoPaw && copaw app` |
| 配置 DeepSeek Key | `copaw models config-key deepseek` |
| 切换 LLM 模型 | `copaw models set-llm` |
| 配置飞书频道 | `copaw channels config` |
| 查看 skill 列表 | `copaw skills list` |
| 创建定时早报 | `copaw cron create --type agent ...` |
| 查看聊天记录 | `copaw chats list` |
| 设置环境变量 | `copaw env set KEY VALUE` |

---

## 目录结构参考

```
~/.copaw/
├── config.json              # 主配置（频道、LLM、Agent 参数）
├── AGENTS.md                # Agent 系统提示
├── SOUL.md                  # Agent 人格设定
├── PROFILE.md               # 用户画像
├── MEMORY.md                # 长期记忆
├── HEARTBEAT.md             # 心跳任务提示
├── active_skills/           # 已激活的 skills（自动同步）
├── customized_skills/       # 自定义 skills（手动放置）
├── chats.json               # 会话数据
├── logs/                    # 日志
└── media/                   # 频道收发的媒体文件
```
