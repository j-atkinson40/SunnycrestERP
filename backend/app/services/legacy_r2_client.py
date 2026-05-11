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


def delete_object(r2_key: str) -> None:
    """Delete an object from R2."""
    client = _get_client()
    if not client:
        raise RuntimeError("R2 not configured")
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=r2_key)


def generate_signed_url(r2_key: str, expires_in: int = 3600) -> str:
    """Generate a time-limited signed URL for private R2 object access."""
    client = _get_client()
    if not client:
        raise RuntimeError("R2 not configured")
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": r2_key},
        ExpiresIn=expires_in,
    )


def generate_presigned_upload_url(
    r2_key: str,
    *,
    content_type: str = "application/octet-stream",
    expires_in: int = 900,
    max_size_bytes: int | None = None,
) -> dict:
    """Generate a presigned PUT URL for direct R2 uploads.

    Phase R-6.2a — file intake adapter. Browser PUTs the file bytes
    directly to R2 without proxying through the Bridgeable backend.
    The presigned URL has a short TTL (15 min default) so the upload
    must happen promptly; classification cascade fires post-completion.

    Returns ``{"url": str, "method": "PUT", "headers": {...}, "key": str}``.
    The headers dict carries the Content-Type the browser MUST send to
    match the signed request — boto3 includes Content-Type in the
    signature when the param is set.
    """
    client = _get_client()
    if not client:
        raise RuntimeError("R2 not configured")
    params: dict = {
        "Bucket": settings.R2_BUCKET_NAME,
        "Key": r2_key,
        "ContentType": content_type,
    }
    if max_size_bytes is not None:
        # boto3 doesn't enforce ContentLength in the presigned URL;
        # the server-side completion endpoint re-validates size via
        # head_object on the resulting key.
        pass
    url = client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires_in,
    )
    return {
        "url": url,
        "method": "PUT",
        "headers": {"Content-Type": content_type},
        "key": r2_key,
    }


def head_object(r2_key: str) -> dict | None:
    """Return head metadata for an R2 object, or None if missing.

    Used by the file intake adapter's completion endpoint to verify
    the uploaded object's actual size + content-type matches the
    presigned-URL contract.
    """
    client = _get_client()
    if not client:
        return None
    try:
        response = client.head_object(
            Bucket=settings.R2_BUCKET_NAME, Key=r2_key
        )
        return {
            "size_bytes": response.get("ContentLength"),
            "content_type": response.get("ContentType"),
            "etag": response.get("ETag"),
        }
    except ClientError:
        return None


def get_public_url(r2_key: str) -> str:
    """Return the public URL for an R2 key."""
    base = settings.R2_PUBLIC_URL.rstrip("/")
    if not base:
        return f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{settings.R2_BUCKET_NAME}/{r2_key}"
    return f"{base}/{r2_key}"
