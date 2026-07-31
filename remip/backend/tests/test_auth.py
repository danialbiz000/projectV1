def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_login_me_flow(client):
    email = "nuovo.utente@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Nuovo Utente"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "user"

    # duplicate email rejected
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert response.status_code == 409

    # wrong password rejected
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "sbagliata9"}
    )
    assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    )
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == email
    assert response.json()["onboarding_completed"] is False

    response = client.post("/api/v1/auth/onboarding", json={"goal": "buy"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is True


def test_protected_routes_require_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/watchlists").status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/api/v1/auth/me", headers=bad).status_code == 401


def test_weak_password_rejected(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "corta@example.com", "password": "corta"}
    )
    assert response.status_code == 422


def test_admin_endpoints_forbidden_for_users(client, user_headers):
    assert client.get("/api/v1/admin/stats", headers=user_headers).status_code == 403
