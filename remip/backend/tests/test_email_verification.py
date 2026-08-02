"""Email verification + password reset (M6). demo_mode defaults to True in
tests, so /auth/verify-email/request and /auth/forgot-password echo the raw
token in the response — see schemas/auth.py::MessageResponse.dev_token —
which is what makes these flows testable without a real mailbox."""
from tests.conftest import login


def _register(client, email, password="password123"):
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "full_name": "T"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_new_user_starts_unverified(client):
    email = "verify.new@example.com"
    _register(client, email)
    headers = login(client, email, "password123")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["email_verified"] is False


def test_verify_email_request_requires_auth(client):
    assert client.post("/api/v1/auth/verify-email/request").status_code == 401


def test_request_and_confirm_email_verification(client):
    email = "verify.confirm@example.com"
    _register(client, email)
    headers = login(client, email, "password123")

    request_response = client.post("/api/v1/auth/verify-email/request", headers=headers)
    assert request_response.status_code == 200
    token = request_response.json()["dev_token"]
    assert token

    confirm_response = client.post("/api/v1/auth/verify-email/confirm", json={"token": token})
    assert confirm_response.status_code == 200

    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["email_verified"] is True

    # Requesting again on an already-verified account is a no-op, no new token
    again = client.post("/api/v1/auth/verify-email/request", headers=headers)
    assert again.status_code == 200
    assert again.json()["dev_token"] is None


def test_confirm_email_verification_invalid_token_400(client):
    response = client.post("/api/v1/auth/verify-email/confirm", json={"token": "not-a-real-token"})
    assert response.status_code == 400


def test_confirm_email_verification_token_is_single_use(client):
    email = "verify.singleuse@example.com"
    _register(client, email)
    headers = login(client, email, "password123")
    token = client.post("/api/v1/auth/verify-email/request", headers=headers).json()["dev_token"]

    first = client.post("/api/v1/auth/verify-email/confirm", json={"token": token})
    assert first.status_code == 200
    second = client.post("/api/v1/auth/verify-email/confirm", json={"token": token})
    assert second.status_code == 400


def test_forgot_password_unknown_email_gives_generic_response_and_no_token(client):
    response = client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody-here@example.com"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dev_token"] is None
    assert "Se l'indirizzo esiste" in body["detail"]


def test_forgot_password_and_reset_password_flow(client):
    email = "reset.flow@example.com"
    _register(client, email, password="oldpassword123")

    forgot_response = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_response.status_code == 200
    token = forgot_response.json()["dev_token"]
    assert token

    reset_response = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword456"}
    )
    assert reset_response.status_code == 200

    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": "oldpassword123"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": "newpassword456"}
        ).status_code
        == 200
    )

    # the reset token cannot be replayed
    replay = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "anotherpass789"}
    )
    assert replay.status_code == 400


def test_reset_password_invalid_token_400(client):
    response = client.post(
        "/api/v1/auth/reset-password", json={"token": "bogus", "new_password": "whatever123"}
    )
    assert response.status_code == 400
