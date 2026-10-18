"""Ponto de entrada HTTP da API AtlasLoL."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request, Response, status

from api.atlas_api.config import Settings
from api.atlas_api.database import banco_disponivel
from api.atlas_api.logging import configure_logging, correlation_id

configure_logging()
log = logging.getLogger("atlas.api")
app = FastAPI(title="AtlasLoL API", version="0.1.0")


@app.middleware("http")
async def registrar_requisicao(request: Request, call_next) -> Response:
    """Inclui um id rastreavel na resposta e no unico log da requisicao."""
    request_id = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
    token = correlation_id.set(request_id)
    started_at = time.perf_counter()
    response: Response | None = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        status_code = response.status_code if response else 500
        log.info(
            "request finished",
            extra={
                "context": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": elapsed_ms,
                }
            },
        )
        if response is not None:
            response.headers["X-Correlation-ID"] = request_id
        correlation_id.reset(token)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Prova que esta instancia da API consegue falar com o PostgreSQL."""
    settings = Settings.from_environment()
    if not banco_disponivel(settings.database_url):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "database": "unavailable"},
        )
    return {"status": "ok", "database": "ok"}
