#!/bin/bash
# ==========================================
#      Book Organizer - Release Packaging
# ==========================================

set -e

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

# 2. 重新签名 (Ad-hoc signing)
# 这有助于解决某些权限问题，虽然没有开发者证书不会通过 Gatekeeper，
# 但能确保二进制文件的完整性。
echo "✍️  正在对应用进行签名 (Ad-hoc)..."
codesign --force --deep --sign - "$APP_PATH"

# 3. 打包为 ZIP
# 使用 ditto 或 zip -y 来保留符号链接和权限
RELEASE_DIR="releases"
mkdir -p "$RELEASE_DIR"
VERSION=$(date +%Y-%m-%d)
ZIP_NAME="BookOrganizer_Mac_$VERSION.zip"
ZIP_PATH="$RELEASE_DIR/$ZIP_NAME"

echo "📦 正在压缩为 ZIP..."
# -c: create archive, -k: PKZip format, --keepParent: include the parent directory name
ditto -c -k --keepParent --rsrc "$APP_PATH" "$ZIP_PATH"

echo ""
echo "=========================================="
echo "✅ 打包完成！"
echo "文件位置: $ZIP_PATH"
echo "=========================================="
echo "⚠️  注意: 当前为 Ad-hoc 签名，未使用 Developer ID 签名和 notarization。"
echo "在其他电脑上打开时如果提示'损坏'或'无法打开'，请在终端运行:"
echo "sudo xattr -cr /Applications/BookOrganizer.app"
echo "=========================================="
