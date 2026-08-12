#!/bin/bash
# ==========================================
#   Book Organizer - Web 服务器启动脚本
# ==========================================

set -e  # 遇到错误立即退出

# 导航到项目根目录
cd "$(dirname "$0")/.." || exit

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "⚠️  虚拟环境不存在，正在创建..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ 创建虚拟环境失败，请检查 python3 是否安装"
        exit 1
    fi
    echo "✅ 虚拟环境创建成功"
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source ./venv/bin/activate

# 检查依赖是否安装。只检查 fastapi 会漏掉 EPUB/PDF 解析依赖，
# 导致目录识别静默失败。
if ! python - <<'PY' 2>/dev/null
import bs4
import ddgs
import ebooklib
import fastapi
import fitz
import google_auth_oauthlib
import googleapiclient
import loguru
import pikepdf
import pypdf
PY
then
    echo "📥 安装依赖..."
    pip install -r requirements.txt
fi

# 启动服务器
echo "=========================================="
echo "🚀 启动 Book Organizer Web 界面..."
echo "=========================================="
HOST="${BOOK_ORGANIZER_HOST:-127.0.0.1}"
echo "📍 服务地址: http://${HOST}:18000"
echo "⏹️  停止服务: 按 Ctrl+C"
echo "=========================================="
echo ""

# 设置 PYTHONPATH 以便正确导入模块
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# 检查端口占用并清理
PID=$(lsof -ti:18000 || true)
if [ -n "$PID" ]; then
    echo "⚠️  端口 18000 被占用 (PID: $PID)，正在清理..."
    kill -9 $PID
    sleep 1
    echo "✅ 端口已释放"
fi

# 仅启动 Web 服务 (不自动打开浏览器，开发模式)
echo "🌐 正在启动 Web 服务 (开发模式)..."
python3 -m uvicorn server:app --host "$HOST" --port 18000 --reload
