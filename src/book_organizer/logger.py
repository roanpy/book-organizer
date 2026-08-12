import os
import sys

from loguru import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_log_dir() -> str:
    """Return a writable log directory without modifying the app bundle."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.expanduser("~"), ".book_organizer", "logs")
    return os.path.join(BASE_DIR, "logs")


LOG_DIR = get_log_dir()
os.makedirs(LOG_DIR, exist_ok=True)

# 移除默认的 handler
logger.remove()

# 1. 控制台输出 (Stderr, 彩色高亮)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

# 2. 文件输出 (按大小轮转, 保留历史)
logger.add(
    os.path.join(LOG_DIR, "book_organizer.log"),
    rotation="10 MB",  # 每个文件最多 10MB
    retention="10 days",  # 保留最近 10 天
    compression="zip",  # 历史日志压缩
    level="DEBUG",  # 文件中记录更详细的信息用于因为排查
    encoding="utf-8",
)

# 导出 logger 供其他模块使用
__all__ = ["get_log_dir", "logger"]
