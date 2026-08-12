#!/bin/bash
# Verify the built BookOrganizer.app before installing or distributing it.

set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

APP_PATH="${1:-dist/BookOrganizer.app}"
PYTHON_BIN="${BOOK_ORGANIZER_VERIFY_PYTHON:-}"

if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        PYTHON_BIN="python"
    fi
fi

if [ ! -d "$APP_PATH" ]; then
    echo "❌ 应用不存在: $APP_PATH"
    exit 1
fi

echo "🔎 校验应用包: $APP_PATH"

echo "  - 检查许可证与第三方声明..."
if ! find "$APP_PATH" -name LICENSE -type f | grep -q . || \
   ! find "$APP_PATH" -name THIRD_PARTY_NOTICES.md -type f | grep -q .; then
    echo "❌ 应用包缺少 LICENSE 或 THIRD_PARTY_NOTICES.md"
    exit 1
fi
if ! find "$APP_PATH" -path "*ebooklib-*.dist-info/licenses/LICENSE.txt" -type f | grep -q . || \
   ! find "$APP_PATH" -path "*pymupdf-*.dist-info/COPYING" -type f | grep -q .; then
    echo "❌ 应用包缺少 EbookLib 或 PyMuPDF 的上游许可证"
    exit 1
fi
for license_file in \
    Loguru-0.7.3.txt \
    Primp-1.2.3.txt \
    PyObjC-12.2.2.txt \
    Tokenizers-0.23.1.txt; do
    if ! find "$APP_PATH" -path "*/licenses/$license_file" -type f | grep -q .; then
        echo "❌ 应用包缺少补充许可证: $license_file"
        exit 1
    fi
done
APP_PATH="$APP_PATH" "$PYTHON_BIN" - <<'PY'
import importlib.metadata
import os
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

app = Path(os.environ["APP_PATH"])
installed = {
    canonicalize_name(distribution.metadata["Name"]): distribution
    for distribution in importlib.metadata.distributions()
    if distribution.metadata["Name"]
}
pending = []
for requirements_file in ("requirements.txt", "requirements-desktop.txt"):
    for line in Path(requirements_file).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-")):
            requirement = Requirement(line)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(canonicalize_name(requirement.name))

missing = []
checked = set()
while pending:
    normalized_name = pending.pop()
    if normalized_name in checked or normalized_name not in installed:
        continue
    checked.add(normalized_name)
    distribution = installed[normalized_name]
    metadata_file = next(
        Path(file) for file in distribution.files or []
        if str(file).endswith(".dist-info/METADATA")
    )
    if not any(app.rglob(metadata_file.parts[0])):
        missing.append(distribution.metadata["Name"])
    for dependency in distribution.requires or []:
        requirement = Requirement(dependency)
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            pending.append(canonicalize_name(requirement.name))
if missing:
    raise SystemExit("❌ 应用包缺少依赖许可证元数据: " + ", ".join(missing))
PY
proxy_metadata=$(find "$APP_PATH" -path "*proxy_tools-0.1.0.dist-info/METADATA" -type f -print -quit)
if [ -z "$proxy_metadata" ] || ! grep -q '^License: MIT$' "$proxy_metadata"; then
    echo "❌ 应用包缺少 Proxy Tools 0.1.0 的 MIT 元数据声明"
    exit 1
fi

echo "  - 检查未使用的 Google API 定义未被打包..."
if find "$APP_PATH" -path "*/googleapiclient/discovery_cache/documents/*.json" -type f | grep -q .; then
    echo "❌ 应用包包含未使用的 Google API discovery 文档"
    exit 1
fi

echo "  - 检查是否混入本机配置、数据库或凭据..."
matches=$(find "$APP_PATH" \
    \( -name "book_organizer_config.json" \
    -o -name "book_organizer_history.json" \
    -o -name "book_organizer.db" \
    -o -name "*.backup" \
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

echo "  - 检查未复制源码缓存..."
if find "$APP_PATH/Contents/Resources" \
    \( -path "*/book_organizer/__pycache__/*" -o -path "*/book_organizer/*.pyc" \) \
    -type f 2>/dev/null | grep -q .; then
    echo "❌ 应用包包含源码目录中的 Python 缓存"
    exit 1
fi
if grep -R -a -F "$HOME/" "$APP_PATH" >/dev/null 2>&1 || \
   grep -R -a -E '/private/var/folders/[^[:space:]]*/book-organizer-build\.' \
       "$APP_PATH" >/dev/null 2>&1; then
    echo "❌ 应用包包含本机用户目录或临时构建路径"
    exit 1
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
import defusedxml
import ebooklib
import fastapi
import fitz
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
