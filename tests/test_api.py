from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from api.atlas_api import main
from api.atlas_api.config import Settings

CONTA_RIOT = {
    "id": UUID("00000000-0000-0000-0000-000000000001"),
    "puuid": "puuid-teste",
    "game_name": "Like Bruce Wayne",
    "tag_line": "Ligui",
    "current_platform": "BR1",
    "last_refreshed_at": datetime(2026, 10, 22, tzinfo=UTC),
}


def test_health_retorna_sucesso_e_correlation_id(monkeypatch) -> None:
    monkeypatch.setattr(main, "banco_disponivel", lambda _: True)

    response = TestClient(main.app).get(
        "/health", headers={"X-Correlation-ID": "teste-123"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert response.headers["X-Correlation-ID"] == "teste-123"


def test_health_indica_banco_indisponivel(monkeypatch) -> None:
    monkeypatch.setattr(main, "banco_disponivel", lambda _: False)

    response = TestClient(main.app).get("/health")

    assert response.status_code == 503
    assert response.json()["detail"]["database"] == "unavailable"


def test_busca_conta_riot_no_catalogo(monkeypatch) -> None:
    monkeypatch.setattr(main, "buscar_conta_riot", lambda *_args, **_kwargs: CONTA_RIOT)

    response = TestClient(main.app).get(
        "/riot-accounts/search?game_name=Like%20Bruce%20Wayne&tag_line=Ligui"
    )

    assert response.status_code == 200
    assert response.json()["puuid"] == "puuid-teste"
    assert response.json()["current_platform"] == "BR1"


def test_busca_conta_riot_ausente_retorna_404(monkeypatch) -> None:
    monkeypatch.setattr(main, "buscar_conta_riot", lambda *_args, **_kwargs: None)

    response = TestClient(main.app).get(
        "/riot-accounts/search?game_name=Inexistente&tag_line=BR1"
    )

    assert response.status_code == 404


def test_consulta_conta_riot_por_puuid(monkeypatch) -> None:
    monkeypatch.setattr(main, "obter_conta_riot", lambda *_args, **_kwargs: CONTA_RIOT)

    response = TestClient(main.app).get("/riot-accounts/puuid-teste")

    assert response.status_code == 200
    assert response.json()["game_name"] == "Like Bruce Wayne"


def test_configura_url_de_componentes_sem_expor_senha(monkeypatch) -> None:
    monkeypatch.delenv("ATLAS_DATABASE_URL", raising=False)
    monkeypatch.setenv("ATLAS_DATABASE_USER", "atlas_app")
    monkeypatch.setenv("ATLAS_DATABASE_PASSWORD", "senha@com:simbolos")
    monkeypatch.setenv("ATLAS_DATABASE_HOST", "postgres")
    monkeypatch.setenv("ATLAS_DATABASE_PORT", "5432")
    monkeypatch.setenv("ATLAS_DATABASE_NAME", "atlas")

    database_url = Settings.from_environment().database_url

    assert database_url is not None
    parsed = make_url(database_url)
    assert parsed.username == "atlas_app"
    assert parsed.password == "senha@com:simbolos"
    assert parsed.host == "postgres"
