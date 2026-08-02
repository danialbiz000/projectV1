"""Generic OAuth2 authorization-code login (M6).

No real provider credentials exist in this environment — the same caveat
documented for the data adapters in docs/INTEGRATIONS.md — so every
provider reports as "not configured" (see ``configured_providers``) until
``REMIP_OAUTH_<PROVIDER>_CLIENT_ID``/``_CLIENT_SECRET`` are set. The
exchange logic below is real (authorization code → access token → userinfo,
over HTTP via httpx) and is exercised in tests against a local mock
provider rather than the live Google endpoint — the same "build the real
integration, verify it against a controlled substitute when the live
network isn't reachable" approach used for adapters/eurostat.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings


class OAuthError(Exception):
    pass


@dataclass(frozen=True)
class OAuthProviderConfig:
    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str


@dataclass(frozen=True)
class OAuthIdentity:
    provider_account_id: str
    email: str
    full_name: str


def configured_providers(settings: Settings | None = None) -> dict[str, OAuthProviderConfig]:
    """Providers with both a client id and secret set. Empty in this
    deployment by default — see the module docstring."""
    settings = settings or get_settings()
    providers: dict[str, OAuthProviderConfig] = {}
    if settings.oauth_google_client_id and settings.oauth_google_client_secret:
        providers["google"] = OAuthProviderConfig(
            name="google",
            client_id=settings.oauth_google_client_id,
            client_secret=settings.oauth_google_client_secret,
            authorize_url=settings.oauth_google_authorize_url,
            token_url=settings.oauth_google_token_url,
            userinfo_url=settings.oauth_google_userinfo_url,
            scope="openid email profile",
        )
    return providers


def build_authorize_url(provider: OAuthProviderConfig, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": provider.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
    }
    return f"{provider.authorize_url}?{urlencode(params)}"


def exchange_code(provider: OAuthProviderConfig, code: str, redirect_uri: str) -> OAuthIdentity:
    """Authorization code → access token → userinfo. Raises OAuthError on
    any failure (bad code, provider outage, malformed userinfo) so the
    caller can turn it into a clean 400 instead of a 500."""
    try:
        with httpx.Client(timeout=10) as client:
            token_response = client.post(
                provider.token_url,
                data={
                    "client_id": provider.client_id,
                    "client_secret": provider.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            userinfo_response = client.get(
                provider.userinfo_url, headers={"Authorization": f"Bearer {access_token}"}
            )
            userinfo_response.raise_for_status()
            data = userinfo_response.json()
        return OAuthIdentity(
            provider_account_id=str(data["sub"]),
            email=data["email"],
            full_name=data.get("name", ""),
        )
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise OAuthError(f"OAuth exchange with '{provider.name}' failed: {exc}") from exc
