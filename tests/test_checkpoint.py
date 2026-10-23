from unittest.mock import Mock

import pytest

from collector import checkpoint as cp


class ConexaoFalsa:
    def __init__(self, row=None):
        self.row = row
        self.calls = []
        self.commits = 0
        self.closed = False

    def execute(self, query, parameters=()):
        self.calls.append((query, parameters))
        return self

    def fetchone(self):
        return self.row

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def test_conecta_checkpoint_com_componentes(monkeypatch):
    conectar = Mock(return_value=ConexaoFalsa())
    monkeypatch.delenv("ATLAS_DATABASE_URL", raising=False)
    monkeypatch.setenv("ATLAS_DATABASE_HOST", "127.0.0.1")
    monkeypatch.setenv("ATLAS_DATABASE_PORT", "5432")
    monkeypatch.setenv("ATLAS_DATABASE_NAME", "atlas")
    monkeypatch.setenv("ATLAS_DATABASE_USER", "atlas_app")
    monkeypatch.setenv("ATLAS_DATABASE_PASSWORD", "senha%com*simbolos")
    monkeypatch.setattr(cp.psycopg, "connect", conectar)

    cp.CheckpointStore.from_environment()

    conectar.assert_called_once_with(
        host="127.0.0.1",
        dbname="atlas",
        user="atlas_app",
        password="senha%com*simbolos",
        port=5432,
        connect_timeout=5,
    )


def test_url_direta_tem_precedencia_sobre_componentes(monkeypatch):
    conectar = Mock(return_value=ConexaoFalsa())
    monkeypatch.setenv("ATLAS_DATABASE_URL", "postgresql://exemplo")
    monkeypatch.setattr(cp.psycopg, "connect", conectar)

    cp.CheckpointStore.from_environment()

    conectar.assert_called_once_with("postgresql://exemplo", connect_timeout=5)


def test_componentes_ausentes_interrompem_coleta_segura(monkeypatch):
    for name in (
        "ATLAS_DATABASE_URL",
        "ATLAS_DATABASE_HOST",
        "ATLAS_DATABASE_NAME",
        "ATLAS_DATABASE_USER",
        "ATLAS_DATABASE_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(cp.CheckpointUnavailable, match="componentes"):
        cp.CheckpointStore.from_environment()


def test_checkpoint_persiste_tentativa_progresso_e_falha():
    connection = ConexaoFalsa()
    store = cp.CheckpointStore(connection)

    store.registrar_tentativa("BR1_1", "checkpoint-v1")
    store.marcar_artefatos(
        "BR1_1", patch="25.14", match_pronto=True, timeline_pronta=True
    )
    store.marcar_falha("BR1_2", "HTTP 404", permanente=True)
    store.close()

    assert connection.commits == 3
    assert connection.closed is True
    assert "attempt_count" in connection.calls[0][0]
    assert connection.calls[1][1] == ("25.14", True, True, True, True, "BR1_1")
    assert connection.calls[2][1] == ("permanent_failure", "HTTP 404", "BR1_2")


def test_obter_retorna_estado_ou_nada():
    connection = ConexaoFalsa(row=("complete", "25.14"))
    store = cp.CheckpointStore(connection)

    assert store.obter("BR1_1") == cp.Checkpoint("BR1_1", "complete", "25.14")

    connection.row = None
    assert store.obter("BR1_2") is None
