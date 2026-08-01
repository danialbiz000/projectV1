from tests.conftest import login


def _register_and_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    return login(client, email, "password123")


def test_list_users_requires_admin(client, user_headers):
    assert client.get("/api/v1/admin/users", headers=user_headers).status_code == 403


def test_list_users(client, admin_headers):
    response = client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2  # at least the seeded demo + admin users
    assert any(u["role"] == "admin" for u in body["items"])


def test_deactivate_and_reactivate_user(client, admin_headers):
    email = "admin.target@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    users = client.get("/api/v1/admin/users", headers=admin_headers, params={"limit": 200}).json()
    target_id = next(u["id"] for u in users["items"] if u["email"] == email)

    response = client.post(f"/api/v1/admin/users/{target_id}/deactivate", headers=admin_headers)
    assert response.status_code == 200

    # deactivated user can no longer authenticate
    login_response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    )
    assert login_response.status_code == 403

    reactivate = client.post(f"/api/v1/admin/users/{target_id}/reactivate", headers=admin_headers)
    assert reactivate.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": "password123"}
        ).status_code
        == 200
    )


def test_admin_cannot_deactivate_self(client, admin_headers):
    users = client.get("/api/v1/admin/users", headers=admin_headers).json()["items"]
    admin_id = next(u["id"] for u in users if u["role"] == "admin")
    response = client.post(f"/api/v1/admin/users/{admin_id}/deactivate", headers=admin_headers)
    assert response.status_code == 400


def test_deactivate_unknown_user_404(client, admin_headers):
    response = client.post("/api/v1/admin/users/nope/deactivate", headers=admin_headers)
    assert response.status_code == 404


def test_toggle_source_requires_admin(client, user_headers):
    response = client.post(
        "/api/v1/admin/sources/omi_it/toggle", params={"enabled": False}, headers=user_headers
    )
    assert response.status_code == 403


def test_toggle_source_disable_and_reenable(client, admin_headers):
    off = client.post(
        "/api/v1/admin/sources/omi_it/toggle", params={"enabled": False}, headers=admin_headers
    )
    assert off.status_code == 200
    assert off.json()["enabled"] is False
    sources = client.get("/api/v1/sources").json()
    assert next(s for s in sources if s["code"] == "omi_it")["enabled"] is False

    on = client.post(
        "/api/v1/admin/sources/omi_it/toggle", params={"enabled": True}, headers=admin_headers
    )
    assert on.status_code == 200
    assert on.json()["enabled"] is True


def test_toggle_source_cannot_enable_non_compliant_provider(client, admin_headers):
    response = client.post(
        "/api/v1/admin/sources/portal_generic/toggle",
        params={"enabled": True},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_toggle_source_unknown_provider_404(client, admin_headers):
    response = client.post(
        "/api/v1/admin/sources/no-such-provider/toggle",
        params={"enabled": True},
        headers=admin_headers,
    )
    assert response.status_code == 404
