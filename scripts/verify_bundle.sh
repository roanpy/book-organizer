#!/bin/bash
# Verify the built BookOrganizer.app before installing or distributing it.

set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

APP_PATH="${1:-dist/BookOrganizer.app}"
PYTHON_BIN="${BOOK_ORGANIZER_VERIFY_PYTHON:-}"

if [ -z "$PYTHON_BIN" ]; then
    if [ -x "venv/bin/python" ]; then
        PYTHON_BIN="venv/bin/python"
    else
        PYTHON_BIN="python"
    fi
fi

if [ ! -d "$APP_PATH" ]; then
    echo "❌ 应用不存在: $APP_PATH"
    exit 1
fi

echo "🔎 校验应用包: $APP_PATH"

echo "  - 检查是否混入本机配置、数据库或凭据..."
matches=$(find "$APP_PATH" \
    \( -name "book_organizer_config.json" \
    -o -name "book_organizer_history.json" \
    -o -name "book_organizer.db" \
    -o -name "google_drive_token.json" \
    -o -name "client_secrets.json" \
    -o -name "client_secret*.json" \
    -o -name "secrets.json" \) \
    -print 2>/dev/null || true)
if [ -n "$matches" ]; then
    echo "❌ 应用包包含敏感本地文件:"
    printf '%s\n' "$matches"
    exit 1
fi

echo "  - 检查 Google Drive discovery 文件..."
if find "$APP_PATH" -path "*/googleapiclient/discovery_cache/documents" -type d | grep -q .; then
    if ! find "$APP_PATH" -name "drive.v3.json" -type f | grep -q .; then
        echo "❌ googleapiclient discovery_cache 存在，但缺少 drive.v3.json"
        exit 1
    fi
fi

echo "  - 检查预览静态资源..."
if ! find "$APP_PATH" -path "*/static/js/modules/preview.js" -type f | grep -q .; then
    echo "❌ 应用包缺少预览模块 static/js/modules/preview.js"
    exit 1
fi
if grep -R "cdn.jsdelivr\|unpkg.com\|cdnjs.cloudflare" "$APP_PATH"/Contents/Resources/static/js "$APP_PATH"/Contents/Resources/static/index.html >/dev/null 2>&1; then
    echo "❌ 预览/前端静态资源引用了 CDN，请保持离线打包"
    exit 1
fi

echo "  - 检查本地服务绑定地址..."
"$PYTHON_BIN" - <<'PY'
from pathlib import Path
import re
import sys

paths = [Path("src/server.py"), *Path("src/book_organizer").rglob("*.py")]
content = "\n".join(path.read_text(encoding="utf-8") for path in paths)
if re.search(r"host=[\"'](?:0\.0\.0\.0|::)[\"']", content):
    print("❌ 发现非本机绑定地址，请保持桌面应用只监听 127.0.0.1")
    sys.exit(1)
if "127.0.0.1" not in content:
    print("❌ 未找到 127.0.0.1 绑定配置")
    sys.exit(1)
PY

echo "  - 检查关键运行时模块导入..."
"$PYTHON_BIN" - <<'PY'
import bs4
import ddgs
import ebooklib
import fastapi
import fitz
import google_auth_oauthlib
import googleapiclient
import loguru
import ollama
import openai
import pikepdf
import pypdf
import webview

from book_organizer.config import build_synced_preferences

prefs = build_synced_preferences(
    {
        "gemini": {"api_key": "secret", "model_name": "gemini"},
        "custom_providers": {"demo": {"api_key": "secret", "model_name": "demo"}},
    }
)
assert "api_key" not in prefs["gemini"]
assert "api_key" not in prefs["custom_providers"]["demo"]
PY

if [ -n "${BOOK_ORGANIZER_VERIFY_URL:-}" ]; then
    echo "  - 检查运行中 /api/config 脱敏输出..."
    "$PYTHON_BIN" - <<'PY'
import json
import os
import sys
import urllib.request

url = os.environ["BOOK_ORGANIZER_VERIFY_URL"].rstrip("/") + "/api/config"
with urllib.request.urlopen(url, timeout=5) as response:
    data = json.load(response)

def contains_raw_api_key(value):
    if isinstance(value, dict):
        if "api_key" in value:
            return True
        return any(contains_raw_api_key(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_raw_api_key(item) for item in value)
    return False

if contains_raw_api_key(data):
    print("❌ /api/config 返回了原始 api_key 字段", file=sys.stderr)
    sys.exit(1)
PY
fi

echo "✅ 应用包校验通过"
