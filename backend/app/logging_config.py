"""Centralized logging: stdout handler, optional JSON format, per-module verbosity."""
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exc"] = record.exc_text
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable formatter with colour-coded level badges."""

    _COLOURS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelname, "")
        level = f"{colour}{record.levelname:<8}{self._RESET}"
        ts = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        base = f"{ts} [{level}] {record.name}: {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging() -> None:
    """Install a single stdout handler and configure per-module log levels.

    Set LOG_FORMAT=json in the environment to emit one JSON object per line
    (useful for log aggregators like Loki / CloudWatch). Defaults to coloured
    text for local development.

    Noisy third-party loggers are silenced to WARNING.
    """
    use_json = os.getenv("LOG_FORMAT", "text").lower() == "json"
    formatter: logging.Formatter = JsonFormatter() if use_json else TextFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = [handler]

    # per-module verbosity
    logging.getLogger("bookspace").setLevel(logging.DEBUG)
    logging.getLogger("bookspace.api").setLevel(logging.INFO)
    logging.getLogger("bookspace.auth").setLevel(logging.INFO)
    logging.getLogger("bookspace.crud").setLevel(logging.DEBUG)
    logging.getLogger("bookspace.isbn").setLevel(logging.DEBUG)

    # silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "sqlalchemy.engine", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
