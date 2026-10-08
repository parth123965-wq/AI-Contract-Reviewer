import logging
import json
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List
from app.core.config import settings


class RecentLogBuffer(logging.Handler):
    def __init__(self, capacity: int = 1000) -> None:
        super().__init__()
        self.records: deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(self.format(record))
        except Exception:
            self.handleError(record)

    def get_records(self, limit: int) -> List[str]:
        self.acquire()
        try:
            return list(self.records)[-limit:]
        finally:
            self.release()


class AppJSONFormatter(logging.Formatter):
    """
    Structured JSON Formatter for Backend App API service.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "ai_engine" if record.name.startswith("ai_engine") else "backend_app",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": record.filename,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields if passed in log call
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message"
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}
        if extra:
            log_data["extra"] = extra

        return json.dumps(log_data)


recent_log_buffer = RecentLogBuffer()


def setup_app_logging() -> logging.Logger:
    logger = logging.getLogger("app")
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(AppJSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    recent_log_buffer.setFormatter(AppJSONFormatter())
    if recent_log_buffer not in logger.handlers:
        logger.addHandler(recent_log_buffer)

    return logger


app_logger = setup_app_logging()


def get_app_logger(name: str) -> logging.Logger:
    """
    Returns a child logger scoped under 'app.<name>'
    """
    return logging.getLogger(f"app.{name}")


def get_recent_logs(limit: int) -> List[str]:
    return recent_log_buffer.get_records(limit)
