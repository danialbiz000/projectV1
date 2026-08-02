"""GDPR self-service export (Art. 20) and erasure (Art. 17), M6."""
from sqlalchemy import select

from app.db.base import SessionLocal
from app.models import NotificationPreference, User, Watchlist, WatchlistItem
from tests.conftest import login


def _register_and_login(client, email, password="password123"):
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "full_name": "GDPR"}
    )
    assert response.status_code == 201, response.text
    return login(client, email, password)


def test_export_requires_auth(client):
    assert client.get("/api/v1/users/me/export").status_code == 401


def test_export_includes_profile_and_watchlist(client):
    email = "gdpr.export@example.com"
    headers = _register_and_login(client, email)

    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    watchlists = client.get("/api/v1/watchlists", headers=headers).json()
    client.post(
        f"/api/v1/watchlists/{watchlists[0]['id']}/items",
        headers=headers,
        json={"kind": "listing", "listing_id": listing_id, "note": "casa dei sogni"},
    )

    export = client.get("/api/v1/users/me/export", headers=headers)
    assert export.status_code == 200
    body = export.json()
    assert body["profile"]["email"] == email
    assert len(body["watchlists"]) >= 1
    items = [i for w in body["watchlists"] for i in w["items"]]
    assert any(i["note"] == "casa dei sogni" for i in items)
    assert body["notification_preference"] is None  # nobody has customized it yet


def test_delete_account_requires_auth(client):
    assert client.delete("/api/v1/users/me").status_code == 401


def test_delete_account_anonymizes_and_revokes_access(client):
    email = "gdpr.delete@example.com"
    headers = _register_and_login(client, email, password="tobeerased123")

    client.put(
        "/api/v1/notifications/preferences",
        headers=headers,
        json={"frequency": "daily_digest", "muted_types": []},
    )
    watchlists = client.get("/api/v1/watchlists", headers=headers).json()
    watchlist_id = watchlists[0]["id"]
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    client.post(
        f"/api/v1/watchlists/{watchlist_id}/items",
        headers=headers,
        json={"kind": "listing", "listing_id": listing_id},
    )

    delete_response = client.delete("/api/v1/users/me", headers=headers)
    assert delete_response.status_code == 200

    # the same access token is dead immediately (is_active flips to False)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    # the original credentials no longer work either (email was scrubbed)
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": "tobeerased123"}
        ).status_code
        == 401
    )

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is None  # the row no longer matches the original email

        anonymized = db.scalars(
            select(User).where(User.full_name == "", User.is_active.is_(False))
        ).all()
        assert any(u.email.startswith("deleted-") for u in anonymized)
        deleted_user = next(u for u in anonymized if u.email.startswith("deleted-"))

        assert (
            db.scalar(
                select(Watchlist).where(Watchlist.user_id == deleted_user.id)
            )
            is None
        )
        assert (
            db.scalar(
                select(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist_id)
            )
            is None
        )
        assert (
            db.scalar(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == deleted_user.id
                )
            )
            is None
        )
