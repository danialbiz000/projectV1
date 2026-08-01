"""Object storage for immutable artifacts (listing-version snapshots today).

Uses S3-compatible storage (MinIO in docker-compose) when configured via
`REMIP_S3_ENDPOINT_URL`; otherwise falls back to local disk under
`snapshot_local_dir`, so snapshotting never requires an external service —
consistent with the zero-external-services local dev flow (README).
"""
from __future__ import annotations

import logging
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings

logger = logging.getLogger("remip.storage")

LOCAL_SCHEME = "file://"
S3_SCHEME = "s3://"


def _s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


def _ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except (ClientError, BotoCoreError):
        client.create_bucket(Bucket=bucket)


def save_snapshot(key: str, data: bytes, content_type: str = "application/json") -> str:
    """Persist `data` under `key`; returns a storage key that get_snapshot
    can resolve back (s3://bucket/key or file://path)."""
    settings = get_settings()
    if settings.s3_endpoint_url:
        client = _s3_client()
        _ensure_bucket(client, settings.s3_bucket)
        client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
        return f"{S3_SCHEME}{settings.s3_bucket}/{key}"

    path = Path(settings.snapshot_local_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return f"{LOCAL_SCHEME}{path}"


def get_snapshot(storage_key: str) -> bytes | None:
    if not storage_key:
        return None
    if storage_key.startswith(S3_SCHEME):
        bucket, _, key = storage_key[len(S3_SCHEME) :].partition("/")
        try:
            response = _s3_client().get_object(Bucket=bucket, Key=key)
            return response["Body"].read()  # type: ignore[no-any-return]
        except (ClientError, BotoCoreError):
            logger.warning("snapshot not found in S3: %s", storage_key)
            return None
    if storage_key.startswith(LOCAL_SCHEME):
        path = Path(storage_key[len(LOCAL_SCHEME) :])
        return path.read_bytes() if path.exists() else None
    return None
