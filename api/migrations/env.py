"""Ambiente do Alembic; cada migration sera aplicada aqui de forma versionada."""

from __future__ import annotations

from alembic import context
from atlas_api.config import Settings
from sqlalchemy import create_engine, pool

config = context.config
database_url = Settings.from_environment().database_url

# Ainda nao ha modelo de dominio. A primeira migration sera escrita a mao para
# que sua intencao fique revisavel, em vez de aceitar um schema gerado cegamente.
target_metadata = None


def run_migrations_offline() -> None:
    if not database_url:
        raise RuntimeError("Defina ATLAS_DATABASE_URL ou os componentes da conexao antes de executar o Alembic.")
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not database_url:
        raise RuntimeError("Defina ATLAS_DATABASE_URL ou os componentes da conexao antes de executar o Alembic.")
    connectable = create_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
