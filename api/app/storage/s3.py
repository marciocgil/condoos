"""S3-compatible object storage. Keys are always prefixed by condominium id."""

import uuid
from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def document_key(condominium_id: uuid.UUID, sha256: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"cond/{condominium_id}/docs/{sha256}.{ext}"


def _client(endpoint: str | None) -> "S3Client":
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=s.s3_region,
        aws_access_key_id=s.s3_access_key_id.get_secret_value(),
        aws_secret_access_key=s.s3_secret_access_key.get_secret_value(),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@lru_cache
def s3_client() -> "S3Client":
    return _client(get_settings().s3_endpoint_url)


@lru_cache
def s3_public_client() -> "S3Client":
    """Client used only to sign URLs that the browser will open."""
    s = get_settings()
    return _client(s.s3_public_endpoint_url or s.s3_endpoint_url)


def ensure_bucket() -> None:
    client = s3_client()
    bucket = get_settings().s3_bucket
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)


def put_object(key: str, body: bytes, content_type: str) -> None:
    s3_client().put_object(
        Bucket=get_settings().s3_bucket, Key=key, Body=body, ContentType=content_type
    )


def get_object(key: str) -> bytes:
    response = s3_client().get_object(Bucket=get_settings().s3_bucket, Key=key)
    body: bytes = response["Body"].read()
    return body


def presigned_get_url(key: str) -> str:
    s = get_settings()
    return s3_public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": s.s3_bucket, "Key": key},
        ExpiresIn=s.s3_presign_ttl_seconds,
    )


def delete_object(key: str) -> None:
    """Idempotent: deleting a missing key is not an error in S3."""
    s3_client().delete_object(Bucket=get_settings().s3_bucket, Key=key)
