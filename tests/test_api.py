from fastapi.testclient import TestClient

from api.atlas_api import main


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
