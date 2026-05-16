"""Centralized logging configuration: stdout handler, format, and per-module verbosity."""
import logging
import sys


def configure_logging() -> None:
    """Install a single stdout handler and configure per-module log levels.

    Replaces any handlers added by uvicorn/FastAPI before this runs.
    Noisy third-party loggers (httpx, sqlalchemy, uvicorn.access) are silenced to WARNING.
    """
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # replace any handlers added by uvicorn/fastapi before we configure
    root.handlers = [handler]

    # per-module verbosity
    logging.getLogger("bookspace.isbn").setLevel(logging.DEBUG)
    logging.getLogger("bookspace.crud").setLevel(logging.DEBUG)
    logging.getLogger("bookspace.auth").setLevel(logging.INFO)
    logging.getLogger("bookspace.api").setLevel(logging.INFO)

    # silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
