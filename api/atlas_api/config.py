"""Configuracao da aplicacao obtida exclusivamente do ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# No servidor as variaveis ja chegam pelo ambiente. Localmente, este arquivo
# permite executar a API e o Alembic a partir do .env ignorado pelo Git.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Valores necessarios para executar a API, sem segredos no codigo."""

    database_url: str | None

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(database_url=os.getenv("ATLAS_DATABASE_URL"))
