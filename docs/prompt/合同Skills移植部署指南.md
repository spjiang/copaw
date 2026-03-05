# 合同 Skills 移植部署指南

> 本文档说明如何将「合同起草」相关 Skills 从一个 CoPaw 项目复制到任意其他 CoPaw 实例并直接使用。
> Skills 内部**不含任何硬编码路径**，所有可变路径均通过环境变量控制。

---

## 一、技术架构概览

```
用户对话
  │
  ▼
contract_draft (SKILL.md)          ← 主入口：解析意图、调度各子 skill
  ├─ contract_template_match       ← 模板检索（文字描述 → TF-IDF 匹配）
  │    └─ scripts/template_match.py
  ├─ match_by_file.py              ← 文件上传匹配（精准命中 or 内容相似度）
  ├─ contract_template_params      ← 提取合同参数（甲乙方、金额、周期等）
  └─ contract_draft_llm            ← LLM 起草正文 + 生成 Word 文件

shared/                            ← 公共模块（所有 skill 脚本共用）
  ├─ push.py          实时进度推送（WebSocket）
  ├─ db.py            执行日志写入 SQLite
  ├─ word_gen.py      Markdown → Word (.docx) 转换
  └─ local_template_api.py  本地模板检索 HTTP 服务（TF-IDF）
```

### 外部服务依赖

| 服务 | 说明 | 启动方式 |
|------|------|----------|
| **本地模板 API** | 扫描 `.docx` 模板文件，提供向量检索接口 | `start_services.sh` 自动启动 |
| **CoPaw 服务** | 主应用，负责 LLM 调用和 WebSocket | 正常启动 CoPaw 即可 |

---

## 二、移植前的准备

### 2.1 Python 依赖

在目标机器上安装以下 Python 包：

```bash
pip install python-docx requests
```

> `pdfplumber` 为可选依赖，若需支持用户上传 PDF 文件则安装：
> ```bash
> pip install pdfplumber
> ```

### 2.2 合同模板文件

Skills 需要读取 `.docx` 格式的合同模板文件进行相似度匹配。

有两种方式提供模板文件（任选其一）：

**方式 A：放到默认目录（推荐，零配置）**
```bash
mkdir -p ~/.copaw/contract_templates
cp /path/to/your/合同模板/*.docx ~/.copaw/contract_templates/
```

**方式 B：保留现有目录，通过环境变量指定**
```bash
# 在 shell 配置文件（~/.zshrc 或 ~/.bashrc）中添加：
export TEMPLATE_DIR=/path/to/your/合同模板
```

---

## 三、Skills 目录结构

需要复制的文件清单（来源：当前项目的 `active_skills` 或 `src/copaw/agents/skills/`）：

```
active_skills/
├── contract_draft/
│   └── SKILL.md
├── contract_draft_llm/
│   ├── SKILL.md
│   └── scripts/
├── contract_template_match/
│   ├── SKILL.md
│   └── scripts/
│       ├── template_match.py
│       └── match_by_file.py
├── contract_template_params/
│   ├── SKILL.md
│   └── scripts/
├── shared/
│   ├── __init__.py
│   ├── push.py
│   ├── db.py
│   ├── word_gen.py
│   └── local_template_api.py
└── start_services.sh          ← 通用启动脚本
```

---

## 四、移植步骤

### 步骤 1：复制 Skills 到目标机器

```bash
# 在目标机器上创建目录
mkdir -p ~/.copaw/active_skills

# 从源机器复制（也可以用 scp / git / U盘等方式传输）
rsync -av --exclude="__pycache__" --exclude="*.pyc" \
  contract_draft \
  contract_draft_llm \
  contract_template_match \
  contract_template_params \
  shared \
  start_services.sh \
  ~/.copaw/active_skills/

# 赋予启动脚本执行权限
chmod +x ~/.copaw/active_skills/start_services.sh
```

### 步骤 2：放置合同模板文件

```bash
mkdir -p ~/.copaw/contract_templates
cp /path/to/your/合同模板/*.docx ~/.copaw/contract_templates/
```

验证文件已就位：
```bash
ls ~/.copaw/contract_templates/*.docx
```

### 步骤 3：安装 Python 依赖

```bash
pip install python-docx requests
```

### 步骤 4：启动本地模板 API 服务

```bash
bash ~/.copaw/active_skills/start_services.sh
```

成功输出示例：
```
=== 合同 Skills 服务启动 ===
  SKILLS_DIR   : /Users/xxx/.copaw/active_skills
  TEMPLATE_DIR : /Users/xxx/.copaw/contract_templates
  TEMPLATE_PORT: 9000

  已找到 12 个 .docx 模板文件
[1/1] 🚀 启动本地模板 API (port 9000)...
  PID: 12345  日志: /tmp/local_template_api.log
  等待服务就绪......... ✅

=== 启动完成 ===
  模板 API : http://localhost:9000/api/template/list
  CoPaw   : http://localhost:8088
```

> 每次重启机器后需重新执行此命令，或配置为开机自启动（见附录）。

### 步骤 5：启动 CoPaw

按照目标 CoPaw 项目的正常方式启动即可，无需修改任何源码。

### 步骤 6：验证

访问以下 URL 确认模板 API 正常工作：

```
http://localhost:9000/api/template/list
```

返回示例：
```json
{
  "total": 12,
  "templates": [
    { "template_id": "xxx", "template_name": "产品采购合同-硬件采购", ... },
    ...
  ]
}
```

然后在 CoPaw 聊天界面输入：`帮我起草一份硬件采购合同` —— 即可验证完整流程。

---

## 五、环境变量汇总

以下环境变量均有合理默认值，**不配置也能正常运行**，仅在需要自定义时设置：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `TEMPLATE_DIR` | `~/.copaw/contract_templates` | 合同模板 `.docx` 文件根目录 |
| `TEMPLATE_PORT` | `9000` | 本地模板检索 API 端口 |
| `COPAW_API_BASE` | `http://127.0.0.1:8088` | CoPaw 服务地址（用于 WebSocket 进度推送） |
| `CONTRACT_STORAGE_DIR` | `~/.copaw/contracts` | 生成的 Word 合同文件存放目录 |
| `AGENT_LOG_DB` | `~/.copaw/agent_logs.db` | 执行日志 SQLite 数据库路径 |

一次性设置所有变量示例（写入 `~/.zshrc`）：
```bash
export TEMPLATE_DIR=/data/合同模板
export COPAW_API_BASE=http://127.0.0.1:8088
export CONTRACT_STORAGE_DIR=/data/contracts
```

---

## 六、CoPaw 源码是否需要修改？

| 功能 | 是否需要改源码 | 说明 |
|------|--------------|------|
| 合同起草 Skill 主流程 | **不需要** | 纯 SKILL.md 编排 |
| 模板检索 | **不需要** | 独立 HTTP 服务 + Python 脚本 |
| Word 文件生成 | **不需要** | `shared/word_gen.py` 独立脚本 |
| WebSocket 进度推送 | **不需要** | 推送失败时静默降级，不影响主流程 |
| 文件上传（聊天附件按钮） | **需要** | 见下方说明 |

### 关于文件上传（聊天附件）

若目标 CoPaw **已有** `/api/files/upload` 接口和聊天附件上传按钮，则无需任何操作。

若**没有**，则需要在目标 CoPaw 中补充以下两处修改（均为最小改动）：

**① 添加文件上传路由** `src/copaw/app/routers/files.py`：
```python
import shutil, uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse

router = APIRouter(prefix="/api/files", tags=["files"])
UPLOAD_DIR = Path.home() / ".copaw" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return JSONResponse({"url": f"/api/files/download/{filename}", "name": file.filename, "size": dest.stat().st_size})

@router.get("/download/{filename}")
async def download_file(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(path), filename=filename)
```

**② 在路由注册文件中引入**（`src/copaw/app/routers/__init__.py` 或应用入口）：
```python
from .files import router as files_router
app.include_router(files_router)
```

**③ 在聊天前端启用附件上传按钮**：在 `console/src/pages/Chat/index.tsx` 中，为 `AgentScopeRuntimeWebUI` 组件的 `sender.attachments` 添加 `customRequest` 配置，指向 `/api/files/upload`。

---

## 七、停止服务

```bash
# 停止本地模板 API（默认端口 9000）
kill $(lsof -ti:9000)

# 或查找 PID 手动 kill
ps aux | grep local_template_api
```

---

## 附录：开机自启动配置（macOS LaunchAgent）

创建 `~/Library/LaunchAgents/com.copaw.contract.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>             <string>com.copaw.contract</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/YOUR_USERNAME/.copaw/active_skills/start_services.sh</string>
  </array>
  <key>RunAtLoad</key>         <true/>
  <key>KeepAlive</key>         <false/>
  <key>StandardOutPath</key>   <string>/tmp/copaw_contract_boot.log</string>
  <key>StandardErrorPath</key> <string>/tmp/copaw_contract_boot.log</string>
</dict>
</plist>
```

加载：
```bash
launchctl load ~/Library/LaunchAgents/com.copaw.contract.plist
```
