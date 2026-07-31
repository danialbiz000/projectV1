import os

os.environ["REMIP_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REMIP_SEED_ON_STARTUP"] = "false"
os.environ["REMIP_SECRET_KEY"] = "test-secret-not-for-production-0123456789abcdef"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base, SessionLocal, engine  # noqa: E402
from app.db.seed import (  # noqa: E402
    DEMO_ADMIN_EMAIL,
    DEMO_PASSWORD,
    DEMO_USER_EMAIL,
    seed_database,
)
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db, listings_per_neighborhood=4)
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def user_headers(client):
    return login(client, DEMO_USER_EMAIL)


@pytest.fixture(scope="session")
def admin_headers(client):
    return login(client, DEMO_ADMIN_EMAIL)
