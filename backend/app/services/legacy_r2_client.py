"""Cloudflare R2 storage client (S3-compatible) for legacy image files."""

import logging
from io import BytesIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    if not settings.R2_ACCOUNT_ID or not settings.R2_ACCESS_KEY_ID:
        return None
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def upload_file(local_path: str, r2_key: str) -> str:
    """Upload a local file to R2. Returns public URL."""
    client = _get_client()
    if not client:
        raise RuntimeError("R2 not configured")
    client.upload_file(local_path, settings.R2_BUCKET_NAME, r2_key)
    return get_public_url(r2_key)


def upload_bytes(data: bytes, r2_key: str, content_type: str = "application/octet-stream") -> str:
    """Upload bytes directly to R2. Returns public URL."""
    client = _get_client()
    if not client:
        raise RuntimeError("R2 not configured")
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=r2_key,
        Body=data,
        ContentType=content_type,
    )
    return get_public_url(r2_key)


def download_bytes(r2_key: str) -> bytes:
    """Download file contents from R2 as bytes."""
    client = _get_client()
    if not client:
        raise RuntimeError("R2 not configured")
    response = client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=r2_key)
    return response["Body"].read()


def download_file(r2_key: str, local_path: str) -> None:
    """Download file from R2 to local path."""
    client = _get_client()
    if not client:
        raise RuntimeError("R2 not configured")
    client.download_file(settings.R2_BUCKET_NAME, r2_key, local_path)


def exists(r2_key: str) -> bool:
    """Check if a key exists in the R2 bucket."""
    client = _get_client()
    if not client:
        return False
    try:
        client.head_object(Bucket=settings.R2_BUCKET_NAME, Key=r2_key)
        return True
    except ClientError:
        return False


def get_public_url(r2_key: str) -> str:
    """Return the public URL for an R2 key."""
    base = settings.R2_PUBLIC_URL.rstrip("/")
    if not base:
        return f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{settings.R2_BUCKET_NAME}/{r2_key}"
    return f"{base}/{r2_key}"
