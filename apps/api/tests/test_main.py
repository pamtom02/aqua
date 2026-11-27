import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app

client = TestClient(app)


def test_health_check(monkeypatch):
    monkeypatch.setattr("app.main.check_database_connection", lambda: {"status": "ok"})
    """Prueba GET /health comprobando código 200 y cuerpo básico."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert len(data) > 0


def test_404_format():
    """Prueba el formato unificado para rutas inexistentes."""
    response = client.get("/api/v1/ruta-falsa-que-no-existe")
    assert response.status_code == 404
    data = response.json()

    # Verifica que coincida con el esquema ErrorResponse definido previamente
    assert "error" in data
    assert "message" in data


def test_validation_error_format():
    """Prueba el formato unificado para errores 422 inyectando un tipo inválido."""
    # Forzamos 422 usando la ruta del catálogo que existe y exige enteros
    response = client.get("/api/v1/lakes?page=letras")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    assert "message" in data
    assert "details" in data


def test_missing_configuration(monkeypatch):
    from app.start import prepare
    monkeypatch.setattr("app.start.database", None)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        prepare()
