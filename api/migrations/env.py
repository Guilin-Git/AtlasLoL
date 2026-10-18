"""Ambiente do Alembic; cada migration sera aplicada aqui de forma versionada."""

from __future__ import annotations

import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()
config = context.config
database_url = os.getenv("ATLAS_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Ainda nao ha modelo de dominio. A primeira migration sera escrita a mao para
# que sua intencao fique revisavel, em vez de aceitar um schema gerado cegamente.
target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("Defina ATLAS_DATABASE_URL antes de executar o Alembic.")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not config.get_main_option("sqlalchemy.url"):
        raise RuntimeError("Defina ATLAS_DATABASE_URL antes de executar o Alembic.")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
