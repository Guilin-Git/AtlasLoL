"""Logging JSON e correlation id por requisicao."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    """Uma linha JSON por evento, pronta para coleta posterior pelo Loki."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": correlation_id.get(),
            "msg": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if context:
            event.update(context)
        return json.dumps(event, ensure_ascii=False)


def configure_logging() -> None:
    """Configura o logger da aplicacao sem duplicar handlers em testes/reload."""
    logger = logging.getLogger("atlas.api")
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
