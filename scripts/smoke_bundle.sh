#!/bin/bash
# Start the packaged app, verify its local API, then require a clean shutdown.

set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
APP_PATH="${1:-dist/BookOrganizer.app}"
EXECUTABLE="$APP_PATH/Contents/MacOS/BookOrganizer"
LOG_FILE="${TMPDIR:-/tmp}/book-organizer-smoke.log"

if [ ! -x "$EXECUTABLE" ]; then
    echo "❌ 应用可执行文件不存在: $EXECUTABLE"
    exit 1
fi

if lsof -nP -iTCP:18000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "❌ 端口 18000 已被占用，请先退出正在运行的 Book Organizer"
    exit 1
fi

BOOK_ORGANIZER_SMOKE_EXIT_SECONDS=3 "$EXECUTABLE" >"$LOG_FILE" 2>&1 &
pid=$!
cleanup() {
    kill -KILL "$pid" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 30); do
    if curl -fsS --max-time 1 http://127.0.0.1:18000/api/config >/dev/null 2>&1; then
        echo "✅ 应用启动与本地 API 检查通过"
        for _ in $(seq 1 30); do
            if ! kill -0 "$pid" 2>/dev/null; then
                wait "$pid"
                trap - EXIT
                echo "✅ 应用正常退出检查通过"
                exit 0
            fi
            sleep 0.25
        done
        echo "❌ 应用未在预期时间内正常退出"
        exit 1
    fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
done

echo "❌ 应用启动检查失败"
tail -50 "$LOG_FILE" || true
exit 1
