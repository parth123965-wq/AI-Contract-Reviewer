import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from app.core.config import settings


class AIEngineJSONFormatter(logging.Formatter):
    """
    Structured JSON Formatter specifically for AI Engine / LLM operations.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "ai_engine",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": record.filename,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include custom extra metadata (e.g. model_name, tokens, node_name, prompt_id)
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


def setup_ai_engine_logging() -> logging.Logger:
    logger = logging.getLogger("ai_engine")
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(AIEngineJSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


ai_logger = setup_ai_engine_logging()


def get_ai_logger(name: str) -> logging.Logger:
    """
    Returns a child logger scoped under 'ai_engine.<name>'
    """
    return logging.getLogger(f"ai_engine.{name}")
