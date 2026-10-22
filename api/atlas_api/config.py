"""Configuracao da aplicacao obtida exclusivamente do ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from sqlalchemy import URL

# No servidor as variaveis ja chegam pelo ambiente. Localmente, este arquivo
# permite executar a API e o Alembic a partir do .env ignorado pelo Git.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Valores necessarios para executar a API, sem segredos no codigo."""

    database_url: str | None

    @classmethod
    def from_environment(cls) -> Settings:
        database_url = os.getenv("ATLAS_DATABASE_URL")
        if database_url:
            return cls(database_url=database_url)

        components = {
            "username": os.getenv("ATLAS_DATABASE_USER"),
            "password": os.getenv("ATLAS_DATABASE_PASSWORD"),
            "host": os.getenv("ATLAS_DATABASE_HOST"),
            "database": os.getenv("ATLAS_DATABASE_NAME"),
        }
        if not all(components.values()):
            return cls(database_url=None)

        port = int(os.getenv("ATLAS_DATABASE_PORT", "5432"))
        url = URL.create(
            "postgresql+psycopg",
            username=components["username"],
            password=components["password"],
            host=components["host"],
            port=port,
            database=components["database"],
        )
        return cls(database_url=url.render_as_string(hide_password=False))
