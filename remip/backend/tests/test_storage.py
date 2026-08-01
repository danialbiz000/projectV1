"""services/storage.py: local-disk path is exercised for real (matches the
test/dev environment, which has no S3_ENDPOINT_URL configured); the S3 path
is verified against a mocked boto3 client so its request shape is correct
without requiring a live MinIO server."""
from unittest.mock import MagicMock, patch

from app.services.storage import get_snapshot, save_snapshot


def test_local_disk_roundtrip(tmp_path, monkeypatch):
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("REMIP_SNAPSHOT_LOCAL_DIR", str(tmp_path))
    monkeypatch.delenv("REMIP_S3_ENDPOINT_URL", raising=False)
    config.get_settings.cache_clear()
    try:
        key = save_snapshot("listings/abc/v1.json", b'{"price": 100}')
        assert key.startswith("file://")
        assert (tmp_path / "listings" / "abc" / "v1.json").exists()
        assert get_snapshot(key) == b'{"price": 100}'
    finally:
        config.get_settings.cache_clear()


def test_get_snapshot_missing_local_file_returns_none():
    assert get_snapshot("file:///nonexistent/path/whatever.json") is None


def test_get_snapshot_empty_key_returns_none():
    assert get_snapshot("") is None


def test_get_snapshot_unknown_scheme_returns_none():
    assert get_snapshot("ftp://somewhere/file") is None


@patch("app.services.storage._s3_client")
def test_save_snapshot_uses_s3_when_configured(mock_client_factory, monkeypatch):
    from app.core import config

    monkeypatch.setenv("REMIP_S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("REMIP_S3_BUCKET", "test-bucket")
    config.get_settings.cache_clear()
    mock_client = MagicMock()
    mock_client_factory.return_value = mock_client
    try:
        key = save_snapshot("listings/abc/v1.json", b"{}")
        assert key == "s3://test-bucket/listings/abc/v1.json"
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "listings/abc/v1.json"
        assert call_kwargs["Body"] == b"{}"
    finally:
        monkeypatch.delenv("REMIP_S3_ENDPOINT_URL", raising=False)
        monkeypatch.delenv("REMIP_S3_BUCKET", raising=False)
        config.get_settings.cache_clear()


@patch("app.services.storage._s3_client")
def test_get_snapshot_reads_from_s3(mock_client_factory):
    mock_client = MagicMock()
    body = MagicMock()
    body.read.return_value = b'{"ok": true}'
    mock_client.get_object.return_value = {"Body": body}
    mock_client_factory.return_value = mock_client

    data = get_snapshot("s3://test-bucket/listings/abc/v1.json")
    assert data == b'{"ok": true}'
    mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="listings/abc/v1.json")
