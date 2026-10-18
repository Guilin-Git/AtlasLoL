"""Operacoes de infraestrutura do PostgreSQL usadas pela API."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def banco_disponivel(database_url: str | None) -> bool:
    """Retorna se uma conexao nova ao PostgreSQL consegue executar SELECT 1.

    O engine e descartado ao fim porque, neste momento, ele e usado somente
    pelo healthcheck. Os endpoints de dominio terao uma sessao compartilhada
    quando os primeiros modelos e migrations forem definidos.
    """
    if not database_url:
        return False

    engine = create_engine(
        database_url,
        connect_args={"connect_timeout": 3},
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()
    return True
