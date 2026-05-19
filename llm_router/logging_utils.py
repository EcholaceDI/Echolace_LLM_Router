from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, MutableMapping, Optional


def _utc_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, set):
        return sorted(value)
    return str(value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": _utc_iso8601(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Pull structured fields from `extra=...` where possible.
        for key, value in record.__dict__.items():
            if key.startswith("_"):
                continue
            if key in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }:
                continue
            payload[key] = value

        return json.dumps(payload, default=_json_default, ensure_ascii=False)


def configure_logging(
    *,
    level: Optional[str] = None,
    format: Optional[str] = None,
    stream: Any = None,
) -> None:
    """
    Configure llm_router logging once.

    Environment variables:
    - ECHOLACE_LOG_LEVEL: INFO (default), DEBUG, WARNING, ERROR
    - ECHOLACE_LOG_FORMAT: "json" or "text" (default)
    """

    root_logger = logging.getLogger("llm_router")
    if getattr(root_logger, "_echolace_configured", False):
        return

    stream = stream or sys.stdout
    level_name = (level or os.getenv("ECHOLACE_LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)

    format_mode = (format or os.getenv("ECHOLACE_LOG_FORMAT") or "text").lower()
    handler = logging.StreamHandler(stream)
    if format_mode == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
    root_logger.propagate = False
    setattr(root_logger, "_echolace_configured", True)


def get_logger(name: str = "llm_router") -> logging.Logger:
    """
    Returns a logger and ensures base configuration is applied.
    """
    configure_logging()
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    fields: Optional[Mapping[str, Any]] = None,
) -> None:
    extra: MutableMapping[str, Any] = {"event": event}
    if fields:
        extra.update(fields)
    logger.log(level, event, extra=extra)
