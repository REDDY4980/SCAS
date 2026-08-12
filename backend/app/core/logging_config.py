"""
Structured logging configuration.

AIB v1.0 Vol 12.11 — central logger records request id, user id, execution
time, errors, model version, HTTP status.
AIB v1.0 Vol 18.6 — never expose stack traces to end users; preserve logs
for troubleshooting.
"""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]

    # Quiet noisy third-party loggers unless explicitly debugging.
    for noisy in ("uvicorn.access", "httpx"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))
