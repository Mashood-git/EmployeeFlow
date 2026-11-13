import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.main import app


class FakeDatabase:
    """Database substitute for isolated API tests."""

    def execute(self, statement):
        return 1


class FailingDatabase:
    """Simulates an unavailable database."""

    def execute(self, statement):
        raise SQLAlchemyError("Simulated database failure")


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: FakeDatabase()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["application"] == "EmployeeFlow"
    assert response.json()["status"] == "running"


def test_health_endpoint(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
    }


def test_health_endpoint_when_database_fails(client):
    app.dependency_overrides[get_db] = lambda: FailingDatabase()

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection failed"
