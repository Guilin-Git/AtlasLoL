"""Operacoes de infraestrutura do PostgreSQL usadas pela API."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


class DatabaseUnavailable(RuntimeError):
    """A API nao tem configuracao ou conexao valida com o PostgreSQL."""


def _engine(database_url: str | None):
    if not database_url:
        raise DatabaseUnavailable("ATLAS_DATABASE_URL nao foi definida")
    return create_engine(
        database_url,
        connect_args={"connect_timeout": 3},
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )


def banco_disponivel(database_url: str | None) -> bool:
    """Retorna se uma conexao nova ao PostgreSQL consegue executar SELECT 1.

    O engine e descartado ao fim porque, neste momento, ele e usado somente
    pelo healthcheck. Os endpoints de dominio terao uma sessao compartilhada
    quando os primeiros modelos e migrations forem definidos.
    """
    try:
        engine = _engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except (DatabaseUnavailable, SQLAlchemyError):
        return False
    finally:
        if "engine" in locals():
            engine.dispose()
    return True


def buscar_conta_riot(
    database_url: str | None,
    *,
    game_name: str,
    tag_line: str,
) -> Mapping[str, object] | None:
    """Busca no catalogo local sem gastar uma requisicao da Riot API."""
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT id, puuid, game_name, tag_line, current_platform,
                           last_refreshed_at
                    FROM riot_accounts
                    WHERE lower(game_name) = lower(:game_name)
                      AND lower(tag_line) = lower(:tag_line)
                    """
                ),
                {"game_name": game_name.strip(), "tag_line": tag_line.strip()},
            )
            return result.mappings().one_or_none()
    except SQLAlchemyError as error:
        raise DatabaseUnavailable("falha ao consultar o catalogo Riot") from error
    finally:
        engine.dispose()


def obter_conta_riot(
    database_url: str | None, *, puuid: str
) -> Mapping[str, object] | None:
    """Busca um perfil Riot pelo identificador estavel usado nas partidas."""
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT id, puuid, game_name, tag_line, current_platform,
                           last_refreshed_at
                    FROM riot_accounts
                    WHERE puuid = :puuid
                    """
                ),
                {"puuid": puuid},
            )
            return result.mappings().one_or_none()
    except SQLAlchemyError as error:
        raise DatabaseUnavailable("falha ao consultar o catalogo Riot") from error
    finally:
        engine.dispose()
