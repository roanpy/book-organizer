from fastapi import HTTPException

from book_organizer.logger import logger


def log_internal_error(operation: str, error: Exception) -> None:
    """Log enough to diagnose a failure without recording paths or secrets."""
    logger.error("{} failed ({})", operation, type(error).__name__)


def internal_error(
    operation: str,
    error: Exception,
    detail: str = "操作失败，请查看应用日志",
) -> HTTPException:
    log_internal_error(operation, error)
    return HTTPException(status_code=500, detail=detail)
