#!/bin/bash
# ==========================================
#      Book Organizer - Release Packaging
# ==========================================

set -euo pipefail

# 获取脚本所在目录的上一级目录（项目根目录）
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "   Book Organizer - 打包发布版本"
echo "=========================================="

# 1. 运行构建脚本
if [ "${SKIP_BUILD:-0}" != "1" ]; then
    echo "🔨 正在构建应用..."
    ./scripts/build_standalone.sh
else
    echo "⏭️  跳过构建，使用现有应用..."
fi

# 检查构建是否成功
APP_PATH="dist/BookOrganizer.app"
if [ ! -d "$APP_PATH" ]; then
    echo "❌ 构建失败: 找不到 $APP_PATH"
    exit 1
fi

SIGN_IDENTITY="${BOOK_ORGANIZER_SIGN_IDENTITY:--}"
NOTARY_PROFILE="${BOOK_ORGANIZER_NOTARY_PROFILE:-}"

if [ "$SIGN_IDENTITY" = "-" ]; then
    echo "✍️  使用 Ad-hoc 签名（仅适合本机测试）..."
    codesign --force --deep --sign - "$APP_PATH"
else
    echo "✍️  使用 Developer ID 签名: $SIGN_IDENTITY"
    codesign --force --deep --options runtime --timestamp --sign "$SIGN_IDENTITY" "$APP_PATH"
fi
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

if [ -n "$NOTARY_PROFILE" ]; then
    if [ "$SIGN_IDENTITY" = "-" ]; then
        echo "❌ 公证需要 Developer ID Application 证书。"
        exit 1
    fi
    echo "🔏 提交 Apple 公证..."
    NOTARY_ZIP="${TMPDIR:-/tmp}/BookOrganizer-notary.zip"
    ditto -c -k --keepParent --rsrc "$APP_PATH" "$NOTARY_ZIP"
    xcrun notarytool submit "$NOTARY_ZIP" \
        --keychain-profile "$NOTARY_PROFILE" --wait
    find "$NOTARY_ZIP" -delete
    xcrun stapler staple "$APP_PATH"
    xcrun stapler validate "$APP_PATH"
fi

# 3. 打包为 ZIP
# 使用 ditto 或 zip -y 来保留符号链接和权限
RELEASE_DIR="releases"
mkdir -p "$RELEASE_DIR"
VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
ZIP_NAME="BookOrganizer-macOS-arm64-v$VERSION.zip"
ZIP_PATH="$RELEASE_DIR/$ZIP_NAME"

echo "📦 正在压缩为 ZIP..."
# -c: create archive, -k: PKZip format, --keepParent: include the parent directory name
ditto -c -k --keepParent --rsrc "$APP_PATH" "$ZIP_PATH"

echo ""
echo "=========================================="
echo "✅ 打包完成！"
echo "文件位置: $ZIP_PATH"
echo "=========================================="
if [ "$SIGN_IDENTITY" = "-" ]; then
    echo "⚠️  当前是未公证的本地测试包，不应作为正式公开版本分发。"
elif [ -z "$NOTARY_PROFILE" ]; then
    echo "⚠️  已使用 Developer ID 签名，但尚未公证。"
else
    echo "✅ 已完成 Developer ID 签名与 Apple 公证。"
fi
echo "=========================================="
