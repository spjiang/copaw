#!/bin/bash
# 合同起草/对比服务启动脚本

PROJECT_DIR="/Users/jiangshengping/wwwroot/rtzh/wwwroot/CoPaw"
PYTHON="/Users/jiangshengping/miniconda3/bin/python"
SKILLS_SRC="$PROJECT_DIR/src/copaw/agents/skills"
ACTIVE_DIR=~/.copaw/active_skills

echo "=== 启动合同服务 ==="

# 1. 启动本地模板检索 API（读取真实合同模板文件）
if curl -s http://localhost:9000/api/template/list > /dev/null 2>&1; then
  echo "[1/2] 本地模板 API 已在运行"
else
  echo "[1/2] 启动本地模板 API (port 9000)..."
  # 设置模板目录环境变量
  export TEMPLATE_DIR="$PROJECT_DIR/docs/合同/合同模板"
  nohup "$PYTHON" "$SKILLS_SRC/shared/local_template_api.py" \
    > /tmp/local_template_api.log 2>&1 &
  echo "  PID: $!  日志: /tmp/local_template_api.log"
  sleep 3
fi

# 2. 同步 skills 到 active_skills
echo "[2/2] 同步 skills..."
for skill in contract_draft contract_template_match contract_template_params contract_draft_llm shared; do
  rm -rf "$ACTIVE_DIR/$skill"
  cp -r "$SKILLS_SRC/$skill" "$ACTIVE_DIR/$skill"
done
echo "  Skills 同步完成"

echo ""
echo "=== 启动完成 ==="
echo "  模板 API:  http://localhost:9000/api/template/list"
echo "  CoPaw:     http://localhost:8088"
