"""Unit tests for app.core.rate_limit — exercised directly (not through the
app's TestClient) so a low limit can be used without disturbing the rest of
the suite, which relies on generous limits set in conftest.py. No Redis is
reachable in this environment, so this also exercises the in-memory
fallback path, not just the interface."""
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limit import enforce_rate_limit


def _fake_request(client_host: str = "1.2.3.4") -> Request:
    return Request(
        {
            "type": "http",
            "client": (client_host, 12345),
            "headers": [],
        }
    )


def test_allows_requests_under_the_limit():
    bucket = f"test-under-{time.time_ns()}"
    request = _fake_request()
    for _ in range(3):
        enforce_rate_limit(bucket, request, limit_per_minute=3)


def test_blocks_requests_over_the_limit():
    bucket = f"test-over-{time.time_ns()}"
    request = _fake_request()
    for _ in range(3):
        enforce_rate_limit(bucket, request, limit_per_minute=3)
    with pytest.raises(HTTPException) as exc_info:
        enforce_rate_limit(bucket, request, limit_per_minute=3)
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "60"


def test_buckets_are_independent_per_key():
    request = _fake_request()
    bucket_a = f"test-a-{time.time_ns()}"
    bucket_b = f"test-b-{time.time_ns()}"
    enforce_rate_limit(bucket_a, request, limit_per_minute=1)
    # A different bucket name has its own counter even for the same client
    enforce_rate_limit(bucket_b, request, limit_per_minute=1)


def test_buckets_are_independent_per_client_ip():
    bucket = f"test-ip-{time.time_ns()}"
    enforce_rate_limit(bucket, _fake_request("9.9.9.1"), limit_per_minute=1)
    enforce_rate_limit(bucket, _fake_request("9.9.9.2"), limit_per_minute=1)
    with pytest.raises(HTTPException):
        enforce_rate_limit(bucket, _fake_request("9.9.9.1"), limit_per_minute=1)


def test_uses_x_forwarded_for_when_present():
    bucket = f"test-xff-{time.time_ns()}"
    request = Request(
        {
            "type": "http",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.1")],
        }
    )
    enforce_rate_limit(bucket, request, limit_per_minute=1)
    with pytest.raises(HTTPException):
        # Same forwarded client, different proxy hop — still the same bucket
        enforce_rate_limit(
            bucket,
            Request(
                {
                    "type": "http",
                    "client": ("10.0.0.2", 12345),
                    "headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.2")],
                }
            ),
            limit_per_minute=1,
        )
