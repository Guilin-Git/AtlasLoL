"""Estado durável de coleta; o bronze continua sendo a fonte dos artefatos."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import psycopg


class CheckpointUnavailable(RuntimeError):
    """O coletor não conseguiu obter o estado necessário para trabalhar seguro."""


@dataclass(frozen=True)
class Checkpoint:
    """Estado resumido de uma partida no ciclo de coleta."""

    match_id: str
    status: str
    patch: str | None


class CheckpointStore:
    """Persistência do ciclo de coleta no PostgreSQL.

    Cada método confirma sua alteração antes de retornar. Assim, uma queda logo
    após uma escrita atômica no bronze deixa no máximo um checkpoint atrasado;
    a próxima execução o reconcilia sem baixar o artefato novamente.
    """

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    @classmethod
    def from_environment(cls) -> CheckpointStore:
        database_url = os.getenv("ATLAS_DATABASE_URL")
        try:
            if database_url:
                connection = psycopg.connect(database_url, connect_timeout=5)
            else:
                required = {
                    "host": os.getenv("ATLAS_DATABASE_HOST"),
                    "dbname": os.getenv("ATLAS_DATABASE_NAME"),
                    "user": os.getenv("ATLAS_DATABASE_USER"),
                    "password": os.getenv("ATLAS_DATABASE_PASSWORD"),
                }
                if not all(required.values()):
                    raise CheckpointUnavailable(
                        "defina ATLAS_DATABASE_URL ou os componentes do PostgreSQL"
                    )
                connection = psycopg.connect(
                    **required,
                    port=int(os.getenv("ATLAS_DATABASE_PORT", "5432")),
                    connect_timeout=5,
                )
        except (psycopg.Error, ValueError) as error:
            raise CheckpointUnavailable("não foi possível conectar ao PostgreSQL") from error
        return cls(connection)

    def obter(self, match_id: str) -> Checkpoint | None:
        try:
            row = self._connection.execute(
                """
                SELECT status, patch
                FROM collector_match_checkpoints
                WHERE match_id = %s
                """,
                (match_id,),
            ).fetchone()
        except psycopg.Error as error:
            raise CheckpointUnavailable("falha ao ler checkpoint") from error
        if row is None:
            return None
        return Checkpoint(match_id=match_id, status=row[0], patch=row[1])

    def registrar_tentativa(self, match_id: str, collector_version: str) -> None:
        self._executar_confirmando(
            """
            INSERT INTO collector_match_checkpoints (
                match_id, status, attempt_count, first_attempt_at,
                last_attempt_at, collector_version, updated_at
            )
            VALUES (%s, 'pending', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s,
                    CURRENT_TIMESTAMP)
            ON CONFLICT (match_id) DO UPDATE SET
                status = 'pending',
                completed_at = NULL,
                attempt_count = collector_match_checkpoints.attempt_count + 1,
                last_attempt_at = CURRENT_TIMESTAMP,
                collector_version = EXCLUDED.collector_version,
                updated_at = CURRENT_TIMESTAMP
            """,
            (match_id, collector_version),
        )

    def marcar_artefatos(
        self,
        match_id: str,
        *,
        patch: str,
        match_pronto: bool,
        timeline_pronta: bool,
    ) -> None:
        completo = match_pronto and timeline_pronta
        self._executar_confirmando(
            """
            UPDATE collector_match_checkpoints
            SET patch = %s,
                match_stored_at = CASE
                    WHEN %s THEN COALESCE(match_stored_at, CURRENT_TIMESTAMP)
                    ELSE match_stored_at
                END,
                timeline_stored_at = CASE
                    WHEN %s THEN COALESCE(timeline_stored_at, CURRENT_TIMESTAMP)
                    ELSE timeline_stored_at
                END,
                status = CASE WHEN %s THEN 'complete' ELSE 'pending' END,
                completed_at = CASE
                    WHEN %s THEN COALESCE(completed_at, CURRENT_TIMESTAMP)
                    ELSE NULL
                END,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE match_id = %s
            """,
            (patch, match_pronto, timeline_pronta, completo, completo, match_id),
        )

    def marcar_falha(self, match_id: str, error: str, *, permanente: bool) -> None:
        self._executar_confirmando(
            """
            UPDATE collector_match_checkpoints
            SET status = %s,
                last_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE match_id = %s
            """,
            ("permanent_failure" if permanente else "pending", error, match_id),
        )

    def _executar_confirmando(self, query: str, parameters: tuple[Any, ...]) -> None:
        try:
            self._connection.execute(query, parameters)
            self._connection.commit()
        except psycopg.Error as error:
            self._connection.rollback()
            raise CheckpointUnavailable("falha ao gravar checkpoint") from error

    def close(self) -> None:
        self._connection.close()
