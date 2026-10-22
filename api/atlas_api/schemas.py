"""Contratos HTTP expostos pela API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RiotAccountResponse(BaseModel):
    """Perfil Riot disponivel no catalogo local do AtlasLoL."""

    id: UUID
    puuid: str
    game_name: str | None
    tag_line: str | None
    current_platform: str | None
    last_refreshed_at: datetime | None
