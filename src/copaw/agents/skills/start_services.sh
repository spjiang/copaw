#!/bin/bash
# =============================================================================
# 合同类 Skills 服务启动脚本（通用版，不含任何硬编码路径）
#
# 使用方法：
#   bash ~/.copaw/active_skills/start_services.sh
#
# 环境变量（可选，不设置则使用默认值）：
#   TEMPLATE_DIR   合同模板根目录
#                  默认: ~/.copaw/contract_templates/
#   TEMPLATE_PORT  本地模板检索 API 端口
#                  默认: 9000
#   COPAW_PORT     CoPaw 服务端口（仅用于提示信息）
#                  默认: 8088
# =============================================================================

set -e

# ---------- 配置 ----------
TEMPLATE_DIR="${TEMPLATE_DIR:-$HOME/.copaw/contract_templates}"
TEMPLATE_PORT="${TEMPLATE_PORT:-9000}"
COPAW_PORT="${COPAW_PORT:-8088}"

# 脚本所在目录（active_skills/ 根目录）
SKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"

echo "=== 合同 Skills 服务启动 ==="
echo "  SKILLS_DIR   : $SKILLS_DIR"
echo "  TEMPLATE_DIR : $TEMPLATE_DIR"
echo "  TEMPLATE_PORT: $TEMPLATE_PORT"
echo ""

# ---------- 检查合同模板目录 ----------
if [ ! -d "$TEMPLATE_DIR" ]; then
  echo "⚠️  合同模板目录不存在: $TEMPLATE_DIR"
  echo ""
  echo "请将合同模板文件(.docx)放入该目录，或设置环境变量 TEMPLATE_DIR 指向正确路径。"
  echo "示例："
  echo "  mkdir -p $TEMPLATE_DIR"
  echo "  cp /path/to/your/合同模板/*.docx $TEMPLATE_DIR/"
  echo "  或："
  echo "  export TEMPLATE_DIR=/path/to/your/合同模板"
  echo "  bash $SKILLS_DIR/start_services.sh"
  echo ""
  exit 1
fi

TEMPLATE_COUNT=$(find "$TEMPLATE_DIR" -name "*.docx" -not -name ".*" 2>/dev/null | wc -l | tr -d ' ')
echo "  已找到 $TEMPLATE_COUNT 个 .docx 模板文件"

# ---------- 1. 启动本地模板检索 API ----------
if curl -s "http://localhost:${TEMPLATE_PORT}/api/template/list" > /dev/null 2>&1; then
  echo "[1/1] ✅ 本地模板 API 已在运行 (port $TEMPLATE_PORT)"
else
  echo "[1/1] 🚀 启动本地模板 API (port $TEMPLATE_PORT)..."
  export TEMPLATE_DIR
  export TEMPLATE_PORT
  nohup "$PYTHON" "$SKILLS_DIR/shared/local_template_api.py" "$TEMPLATE_PORT" \
    > /tmp/local_template_api.log 2>&1 &
  API_PID=$!
  echo "  PID: $API_PID  日志: /tmp/local_template_api.log"

  echo -n "  等待服务就绪"
  for i in {1..10}; do
    sleep 1
    echo -n "."
    if curl -s "http://localhost:${TEMPLATE_PORT}/api/template/list" > /dev/null 2>&1; then
      echo " ✅"
      break
    fi
  done

  if ! curl -s "http://localhost:${TEMPLATE_PORT}/api/template/list" > /dev/null 2>&1; then
    echo " ❌ 启动失败，请查看日志: /tmp/local_template_api.log"
    exit 1
  fi
fi

echo ""
echo "=== 启动完成 ==="
echo "  模板 API : http://localhost:${TEMPLATE_PORT}/api/template/list"
echo "  CoPaw   : http://localhost:${COPAW_PORT}"
echo ""
echo "停止服务: kill \$(lsof -ti:${TEMPLATE_PORT})"
