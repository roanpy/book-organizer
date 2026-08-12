# -*- coding: utf-8 -*-
"""
Web 服务器模块 - 基于 FastAPI 构建的 REST API 服务

这是重构后的 server.py，主要负责应用的初始化、路由挂载和生命周期管理。
具体的业务逻辑已拆分到 routers/ 目录下的各个模块中。
"""

import datetime
import multiprocessing
import os
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 使用 spawn 模式，避免 fork 导致子进程继承父进程的文件锁
try:
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass  # 已设置过，忽略

# 导入路由模块
from book_organizer.config import load_config
from book_organizer.database import UNIFIED_DB_NAME, close_db
from book_organizer.library_path_repair import start_auto_library_path_repair
from book_organizer.local_utils import init_learned_rules_async
from book_organizer.routers import (
    analysis as analysis_router,
)
from book_organizer.routers import (
    book_ops as book_ops_router,
)
from book_organizer.routers import (
    config as config_router,
)
from book_organizer.routers import (
    integrations as integrations_router,
)
from book_organizer.routers import (
    library as library_router,
)
from book_organizer.routers import (
    local as local_router,
)
from book_organizer.routers import (
    metadata as metadata_router,
)
from book_organizer.routers import (
    preview as preview_router,
)
from book_organizer.routers import (
    records as records_router,
)
from book_organizer.routers import (
    sync as sync_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB, only auto-sync CONFIG files (not database)
    print("Starting up...")

    # 异步初始化本地规则学习（延迟 3 秒，不阻塞启动）
    try:
        init_learned_rules_async(delay_seconds=3.0)
    except Exception as e:
        print(f"[Startup] 本地规则初始化跳过: {e}")

    # 换机或同步盘挂载名变化后，数据库中可能存在旧绝对路径。
    # 后台只做可唯一匹配的路径修复，不删除记录，不阻塞启动。
    try:
        start_auto_library_path_repair(delay_seconds=4.0)
    except Exception as e:
        print(f"[Startup] 图书路径自动适配跳过: {e}")

    # 只自动读取配置文件，数据库同步改为用户手动确认。
    try:
        config = load_config()
        sync_config = config.get("sync", {})

        if sync_config.get("enabled") and sync_config.get("path"):
            sync_path = os.path.expanduser(sync_config["path"])
            if os.path.exists(sync_path):
                print(
                    "[Startup] iCloud sync enabled, cloud config is merged by load_config..."
                )

                local_app_dir = os.path.join(os.path.expanduser("~"), ".book_organizer")

                # 数据库不再自动同步；真实差异由 /api/config/sync/validate
                # 使用逻辑指纹判断，避免仅因 SQLite mtime 变化误报。
                data_dir = config.get("data_dir")
                if data_dir and os.path.exists(data_dir):
                    local_db_path = os.path.join(data_dir, UNIFIED_DB_NAME)
                else:
                    local_db_path = os.path.join(local_app_dir, UNIFIED_DB_NAME)
                cloud_db_path = os.path.join(sync_path, UNIFIED_DB_NAME)

                if os.path.exists(local_db_path) and os.path.exists(cloud_db_path):
                    print("[Startup] Database sync check will compare logical content")

                print(
                    "[Startup] Config sync ready (database sync requires manual action)"
                )
    except Exception as e:
        print(f"[Startup] Auto-sync error (non-fatal): {e}")

    yield
    # Shutdown: Close DB and release lock (no sync on shutdown)
    print("Shutting down database connection and releasing lock...")
    close_db()


app = FastAPI(lifespan=lifespan)
LOCAL_HOST = "127.0.0.1"


@app.middleware("http")
async def disable_desktop_asset_cache(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# Redirect stdout/stderr to log file for debugging/windowed mode
if getattr(sys, "frozen", False):
    # Ensure .book_organizer directory exists
    log_dir = os.path.join(os.path.expanduser("~"), ".book_organizer")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    # Use line buffering (buffering=1) to ensure logs are written immediately
    sys.stdout = open(log_path, "a", buffering=1)
    sys.stderr = open(log_path, "a", buffering=1)

    print(f"--- Book Organizer Started at {datetime.datetime.now()} ---")
    print(f"Log path: {log_path}")
    print(f"App location: {os.getcwd()}")


def get_static_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "static")
    return "static"


# Mount static files
app.mount("/static", StaticFiles(directory=get_static_dir()), name="static")


@app.get("/")
async def read_index() -> FileResponse:
    return FileResponse(os.path.join(get_static_dir(), "index.html"))


# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):18[0-9]{3}$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(config_router.router)
app.include_router(library_router.router)
app.include_router(preview_router.router)
app.include_router(book_ops_router.router)
app.include_router(metadata_router.router)
app.include_router(local_router.router)
app.include_router(records_router.router)
app.include_router(analysis_router.router)
app.include_router(integrations_router.router)
app.include_router(sync_router.router)


def main():
    """Run the desktop shell and shut down background services cleanly."""
    server = None
    server_thread = None
    try:
        multiprocessing.freeze_support()

        import webview

        def get_server_port(start_port=18000, max_port=18050):
            import urllib.error
            import urllib.request

            for port in range(start_port, max_port):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex((LOCAL_HOST, port)) != 0:
                        return port, False

                try:
                    req = urllib.request.Request(
                        f"http://{LOCAL_HOST}:{port}/api/config"
                    )
                    with urllib.request.urlopen(req, timeout=1) as response:
                        if response.status == 200:
                            return port, True
                except Exception:
                    pass
            return 18000, False

        server_port, is_running = get_server_port()

        def start_server():
            nonlocal server
            import uvicorn

            config = uvicorn.Config(
                app, host=LOCAL_HOST, port=server_port, log_level="error"
            )
            server = uvicorn.Server(config)
            server.run()

        if not is_running:
            # Start server in a separate thread
            server_thread = threading.Thread(target=start_server, name="api-server")
            server_thread.start()
            time.sleep(1)
        else:
            print(f"Port {server_port} busy by BookOrganizer, assuming server running.")

        # Create native window with persistent storage
        print("Creating webview window with Bundle ID: com.peter.bookorganizer")
        webview.create_window(
            "Book Organizer",
            f"http://{LOCAL_HOST}:{server_port}",
            width=1200,
            height=800,
        )
        webview.start()

    except Exception as e:
        # Last resort crash logging
        crash_log = os.path.join(os.path.expanduser("~"), "book_organizer_crash.log")
        with open(crash_log, "a") as f:
            import traceback

            f.write(f"\n--- CRASH AT {os.getcwd()} ---\n")
            f.write(str(e))
            f.write("\n")
            traceback.print_exc(file=f)
        return 1
    finally:
        analysis_router.shutdown_analysis()
        if server:
            server.should_exit = True
        if server_thread:
            server_thread.join(timeout=5)
            if server_thread.is_alive() and server:
                server.force_exit = True
                server_thread.join(timeout=2)
        close_db()
    return 0


if __name__ == "__main__":
    sys.exit(main())
