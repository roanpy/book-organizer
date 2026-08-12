#!/bin/bash
# ==========================================
#      Book Organizer - Mac Build Script
# ==========================================
#
# 版本: 0.8.3 (2026-05-20)
# 功能: 构建独立 Mac 应用 (.app)
#
# 主要特性:
#   - 自动创建虚拟环境并安装依赖
#   - 使用 PyInstaller 打包为单一应用
#   - 自动优化体积 (删除不必要的模块, ~90MB 节省)
#   - 支持 UPX 压缩 (可选, 额外减小 30-40%)
#   - 包含所有 AI 引擎支持 (Gemini/DeepSeek/Ollama/自定义)
#   - 包含 Calibre PDF 转换支持
#
# 系统要求:
#   - macOS 12.0+
#   - Python 3.11+
#   - 约 2GB 磁盘空间 (构建时)
#
# 使用方法:
#   ./scripts/build_standalone.sh
#
# 输出:
#   dist/BookOrganizer.app
#
# ==========================================

set -e  # 遇到错误立即退出

echo "=========================================="
echo "   Book Organizer - Mac 应用构建 v0.8.3"
echo "=========================================="

# 导航到项目根目录
cd "$(dirname "$0")/.." || exit

select_build_python() {
    for candidate in python3.13 python3.12 python3.11 python3; do
        if command -v "$candidate" &> /dev/null; then
            if "$candidate" - <<'PY' &> /dev/null
import sys
version = sys.version_info[:2]
raise SystemExit(not ((3, 11) <= version <= (3, 13)))
PY
            then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

if [ -d "venv" ]; then
    PYTHON_BIN="venv/bin/python"
else
    if ! PYTHON_BIN="$(select_build_python)"; then
        echo "❌ 错误: 未找到兼容的 Python。请安装 Python 3.11、3.12 或 3.13。"
        exit 1
    fi
fi

echo "✓ 构建 Python: $("$PYTHON_BIN" --version)"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    "$PYTHON_BIN" -m venv venv
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source venv/bin/activate
python - <<'PY'
import sys
version = sys.version_info[:2]
if not ((3, 11) <= version <= (3, 13)):
    raise SystemExit(
        f"❌ 当前虚拟环境 Python {sys.version.split()[0]} 不受支持。"
        "请删除 venv 后使用 Python 3.11、3.12 或 3.13 重新构建。"
    )
PY

# 安装依赖
install_requirements_file() {
    local requirements_file="$1"
    if [ ! -f "$requirements_file" ]; then
        return 0
    fi

    echo "  安装 $requirements_file"
    if ! pip install -r "$requirements_file" -i https://pypi.tuna.tsinghua.edu.cn/simple; then
        echo "⚠️  清华源安装 $requirements_file 失败，回退到官方 PyPI..."
        pip install -r "$requirements_file"
    fi
}

echo "📥 安装依赖..."
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
install_requirements_file requirements.txt
install_requirements_file requirements-build.txt
pip check

echo "🔎 检查关键运行时模块..."
python - <<'PY'
import bs4
import ddgs
import ebooklib
import fastapi
import fitz
import loguru
import ollama
import openai
import pikepdf
import pypdf
import webview
PY

echo "🔐 检查本机敏感数据不会被打包..."
python - <<'PY'
from pathlib import Path

repo = Path.cwd()
sensitive_names = {
    "book_organizer_config.json",
    "book_organizer_history.json",
    "book_organizer.db",
    "google_drive_token.json",
    "client_secrets.json",
}
local_matches = [
    path
    for path in (repo / "data").glob("*")
    if path.name in sensitive_names or path.name.startswith("client_secret")
]
if local_matches:
    print("  本地 data/ 存在用户数据，但 spec 只会打包 data/README.md。")
PY

# 清理旧的构建文件
echo "🧹 清理旧的构建文件..."
rm -rf build dist

# 准备图标（如果存在）
ICON_OPTION=""
if [ -f "assets/icon.icns" ]; then
    echo "✓ 找到图标文件: assets/icon.icns"
    ICON_OPTION="--icon assets/icon.icns"
elif [ -f "assets/icon.png" ]; then
    echo "⚠️  找到 PNG 图标，但需要 .icns 格式"
    echo "💡 提示: 可以使用以下命令转换:"
    echo "   sips -s format icns assets/icon.png --out assets/icon.icns"
else
    echo "⚠️  未找到图标文件，将使用默认图标"
fi

# 检查 UPX 是否可用
UPX_OPTION=""
if command -v upx &> /dev/null; then
    echo "✓ UPX 已安装，将启用可执行文件压缩"
    UPX_DIR=$(dirname $(which upx))
    UPX_OPTION="--upx-dir $UPX_DIR"
else
    echo "⚠️  未找到 UPX，跳过可执行文件压缩"
    echo "💡 提示: 安装 UPX 可减小约 30-40% 体积:"
    echo "   brew install upx"
fi

# 使用 PyInstaller 构建应用
echo "🔨 构建 Mac 应用 (使用 spec 文件)..."
pyinstaller --noconfirm --clean BookOrganizer.spec

# 检查构建是否成功
if [ -d "dist/BookOrganizer.app" ]; then
    echo ""
    echo "🔧 优化打包体积..."

    clean_litellm_optional_modules() {
        local target_dir="$1"
        if [ -d "$target_dir/litellm" ]; then
            echo "  🔧 清理 LiteLLM 可选代理/UI模块..."
            rm -rf "$target_dir/litellm/experimental_mcp_client" 2>/dev/null || true
            rm -rf "$target_dir/litellm/proxy" 2>/dev/null || true
            rm -rf "$target_dir/litellm/tests" 2>/dev/null || true
            rm -rf "$target_dir/litellm/types/proxy" 2>/dev/null || true
            rm -f "$target_dir/litellm/integrations/test_httpx.py" 2>/dev/null || true
        fi
    }

    clean_google_discovery_docs() {
        local target_dir="$1"
        local documents="$target_dir/googleapiclient/discovery_cache/documents"
        if [ -d "$documents" ]; then
            echo "  🔧 清理 Gemini 依赖附带的未使用 Google API 定义..."
            find "$documents" -type f -delete
            find "$documents" -depth -type d -empty -delete
        fi
    }

    assert_no_user_data_packaged() {
        local target_dir="$1"
        if [ ! -d "$target_dir" ]; then
            return 0
        fi

        local matches
        matches=$(find "$target_dir" \
            \( -name "book_organizer_config.json" \
            -o -name "book_organizer_history.json" \
            -o -name "book_organizer.db" \
            -o -name "*.backup" \
            -o -name "google_drive_token.json" \
            -o -name "client_secrets.json" \
            -o -name "client_secret*.json" \) \
            -print 2>/dev/null)

        if [ -n "$matches" ]; then
            echo "❌ 构建产物包含本机敏感数据，已中止："
            printf '%s\n' "$matches"
            exit 1
        fi
    }

    # 检测实际的打包结构 (可能是 .app 或 onedir)
    if [ -d "dist/BookOrganizer.app" ]; then
        # macOS .app bundle 结构
        clean_litellm_optional_modules "dist/BookOrganizer.app/Contents/Resources"
        clean_litellm_optional_modules "dist/BookOrganizer.app/Contents/Frameworks"
        clean_google_discovery_docs "dist/BookOrganizer.app/Contents/Resources"
        clean_google_discovery_docs "dist/BookOrganizer.app/Contents/Frameworks"
        assert_no_user_data_packaged "dist/BookOrganizer.app/Contents/Resources"
        assert_no_user_data_packaged "dist/BookOrganizer.app/Contents/Frameworks"
    elif [ -d "dist/BookOrganizer/_internal" ]; then
        # onedir 结构
        clean_litellm_optional_modules "dist/BookOrganizer/_internal"
        clean_google_discovery_docs "dist/BookOrganizer/_internal"
        assert_no_user_data_packaged "dist/BookOrganizer/_internal"
    fi
    
    # PyInstaller 会先签名 bundle。上面的体积优化会删除 bundle 内文件，
    # 因此必须在优化完成后重新 ad-hoc 签名，否则 codesign 校验会报 file missing。
    if command -v codesign &> /dev/null; then
        echo "✍️  重新签名优化后的应用 (Ad-hoc)..."
        codesign --force --deep --sign - "dist/BookOrganizer.app"
        codesign --verify --deep --strict --verbose=2 "dist/BookOrganizer.app"
    fi

    echo "🔎 运行打包后校验..."
    ./scripts/verify_bundle.sh "dist/BookOrganizer.app"
    
    # 计算应用大小
    APP_SIZE=$(du -sh dist/BookOrganizer.app | cut -f1)
    
    echo ""
    echo "=========================================="
    echo "✅ 构建成功！"
    echo "应用位置: dist/BookOrganizer.app"
    echo "应用大小: $APP_SIZE"
    echo ""
    echo "📝 下一步:"
    echo "1. 测试应用: open dist/BookOrganizer.app"
    echo "2. 验证 AI 功能 (Gemini/DeepSeek/Ollama)"
    echo "3. 测试增强简介生成和显示"
    echo "4. 验证 PDF/EPUB 元数据读写功能"
    echo "5. 如果一切正常，复制到应用程序文件夹:"
    echo "   rm -rf /Applications/BookOrganizer.app && cp -R dist/BookOrganizer.app /Applications/"
    echo ""
    if [ ! -f "assets/icon.icns" ] && [ -f "assets/icon.png" ]; then
        echo "💡 优化建议:"
        echo "转换图标为 .icns 格式以获得更好的显示效果:"
        echo "   sips -s format icns assets/icon.png --out assets/icon.icns"
        echo ""
    fi
    echo "ℹ️  优化说明:"
    echo "此版本不包含云盘 SDK；PDF 导出文件可手动导入外部服务。"
    echo "如需进一步优化，可考虑使用 UPX 压缩。"
    echo "=========================================="
else
    echo ""
    echo "❌ 构建失败！请检查错误信息。"
    exit 1
fi
