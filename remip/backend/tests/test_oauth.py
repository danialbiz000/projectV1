"""OAuth2 login (M6). No real Google credentials exist in this environment
(see services/oauth.py), so the exchange is verified against a local mock
HTTP client instead of the live network — the fake client's ``.get``/``.post``
still go through the real exchange_code() logic (URL building, JSON
parsing, dataclass construction), only the transport is substituted."""
import httpx
import pytest

import app.api.v1.oauth as oauth_api
import app.services.oauth as oauth_service
from app.core.config import get_settings
from tests.conftest import login


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://mock-provider")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("mock error", request=request, response=response)

    def json(self):
        return self._json


class _FakeClient:
    """Derives a stable fake identity from the authorization `code`, so
    calling back with the same code twice simulates the same external
    account logging in twice, and different codes simulate different
    accounts — without any shared mutable state between tests."""

    def __init__(self, *args, **kwargs):
        self._code: str | None = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, data=None, **kwargs):
        assert url == "http://mock-provider/token"
        self._code = data["code"]
        return _FakeResponse({"access_token": f"fake-token-{self._code}"})

    def get(self, url, headers=None, **kwargs):
        assert url == "http://mock-provider/userinfo"
        token = headers["Authorization"].removeprefix("Bearer ")
        code = token.removeprefix("fake-token-")
        return _FakeResponse(
            {"sub": f"ext-{code}", "email": f"oauth-{code}@example.com", "name": f"OAuth {code}"}
        )


class _FailingClient(_FakeClient):
    def post(self, url, data=None, **kwargs):
        return _FakeResponse({"error": "invalid_grant"}, status_code=400)


@pytest.fixture
def configured_google(monkeypatch):
    fake_settings = get_settings().model_copy(
        update={
            "oauth_google_client_id": "test-client-id",
            "oauth_google_client_secret": "test-client-secret",
            "oauth_google_authorize_url": "http://mock-provider/authorize",
            "oauth_google_token_url": "http://mock-provider/token",
            "oauth_google_userinfo_url": "http://mock-provider/userinfo",
        }
    )
    monkeypatch.setattr(oauth_service, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(oauth_api, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(oauth_service.httpx, "Client", _FakeClient)
    return fake_settings


@pytest.fixture
def configured_google_failing(configured_google, monkeypatch):
    monkeypatch.setattr(oauth_service.httpx, "Client", _FailingClient)
    return configured_google


def test_providers_empty_by_default(client):
    response = client.get("/api/v1/auth/oauth/providers")
    assert response.status_code == 200
    assert response.json()["providers"] == []


def test_authorize_unknown_provider_404(client):
    assert client.get("/api/v1/auth/oauth/google/authorize").status_code == 404


def test_callback_unknown_provider_404(client):
    response = client.get("/api/v1/auth/oauth/google/callback", params={"code": "x"})
    assert response.status_code == 404


def test_providers_lists_google_once_configured(client, configured_google):
    response = client.get("/api/v1/auth/oauth/providers")
    assert response.json()["providers"] == ["google"]


def test_authorize_returns_url_and_state(client, configured_google):
    response = client.get("/api/v1/auth/oauth/google/authorize")
    assert response.status_code == 200
    body = response.json()
    assert body["authorize_url"].startswith("http://mock-provider/authorize?")
    assert "client_id=test-client-id" in body["authorize_url"]
    assert body["state"]


def test_callback_creates_a_new_verified_user_and_returns_a_working_token(
    client, configured_google
):
    response = client.get("/api/v1/auth/oauth/google/callback", params={"code": "newuser-1"})
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["email"] == "oauth-newuser-1@example.com"
    assert me["email_verified"] is True


def test_callback_same_identity_twice_maps_to_the_same_user(client, configured_google):
    first = client.get("/api/v1/auth/oauth/google/callback", params={"code": "repeat-login"})
    second = client.get("/api/v1/auth/oauth/google/callback", params={"code": "repeat-login"})
    assert first.status_code == 200 and second.status_code == 200
    first_id = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {first.json()['access_token']}"}
    ).json()["id"]
    second_id = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {second.json()['access_token']}"}
    ).json()["id"]
    assert first_id == second_id


def test_callback_links_to_an_existing_account_with_the_same_email(client, configured_google):
    email = "oauth-linkcheck@example.com"
    register = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert register.status_code == 201
    existing_headers = login(client, email, "password123")
    existing_user_id = client.get("/api/v1/auth/me", headers=existing_headers).json()["id"]

    callback = client.get("/api/v1/auth/oauth/google/callback", params={"code": "linkcheck"})
    assert callback.status_code == 200
    linked_user_id = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {callback.json()['access_token']}"}
    ).json()["id"]
    assert linked_user_id == existing_user_id


def test_callback_provider_error_returns_400(client, configured_google_failing):
    response = client.get("/api/v1/auth/oauth/google/callback", params={"code": "bad-code"})
    assert response.status_code == 400
