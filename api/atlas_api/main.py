"""Ponto de entrada HTTP da API AtlasLoL."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Mapping
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response, status

from api.atlas_api.config import Settings
from api.atlas_api.database import (
    DatabaseUnavailable,
    banco_disponivel,
    buscar_conta_riot,
    obter_conta_riot,
)
from api.atlas_api.logging import configure_logging, correlation_id
from api.atlas_api.schemas import RiotAccountResponse

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


def _conta_ou_erro(
    account: Mapping[str, object] | None,
) -> Mapping[str, object]:
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conta Riot nao encontrada no catalogo local",
        )
    return account


@app.get("/riot-accounts/search", response_model=RiotAccountResponse, tags=["riot"])
def buscar_riot_account(
    game_name: Annotated[str, Query(min_length=1, max_length=100)],
    tag_line: Annotated[str, Query(min_length=1, max_length=10)],
) -> Mapping[str, object]:
    """Encontra um perfil ja presente no catalogo, sem chamar a Riot API."""
    try:
        account = buscar_conta_riot(
            Settings.from_environment().database_url,
            game_name=game_name,
            tag_line=tag_line,
        )
    except DatabaseUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="catalogo Riot temporariamente indisponivel",
        ) from error
    return _conta_ou_erro(account)


@app.get("/riot-accounts/{puuid}", response_model=RiotAccountResponse, tags=["riot"])
def obter_riot_account(
    puuid: Annotated[str, Path(min_length=1, max_length=128)],
) -> Mapping[str, object]:
    """Encontra um perfil pelo PUUID, o identificador estavel da Riot."""
    try:
        account = obter_conta_riot(
            Settings.from_environment().database_url,
            puuid=puuid,
        )
    except DatabaseUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="catalogo Riot temporariamente indisponivel",
        ) from error
    return _conta_ou_erro(account)
