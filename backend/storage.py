"""Validated image storage with local and S3-compatible providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
import logging
import os
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError


logger = logging.getLogger(__name__)
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
FORMAT_EXTENSION = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
CONTENT_TYPE = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
S3_REQUIRED_ENV = (
    "S3_BUCKET",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "S3_PUBLIC_BASE_URL",
)


def ensure_upload_directory():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class StorageProvider(ABC):
    @abstractmethod
    def save(self, content: bytes, extension: str, content_type: str) -> str:
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    def save(self, content: bytes, extension: str, content_type: str) -> str:
        ensure_upload_directory()
        filename = f"{uuid4().hex}{extension}"
        (UPLOAD_DIR / filename).write_bytes(content)
        return f"/uploads/{filename}"


class S3CompatibleStorageProvider(StorageProvider):
    def __init__(self):
        import boto3

        required = {name: os.getenv(name) for name in S3_REQUIRED_ENV}
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"对象存储缺少配置：{', '.join(missing)}")
        public_base = required["S3_PUBLIC_BASE_URL"].rstrip("/")
        if not public_base.startswith("https://"):
            raise ValueError("S3_PUBLIC_BASE_URL 必须是 HTTPS 地址")
        self.bucket = required["S3_BUCKET"]
        self.public_base = public_base
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT") or None,
            region_name=os.getenv("S3_REGION") or None,
            aws_access_key_id=required["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=required["S3_SECRET_ACCESS_KEY"],
        )

    def save(self, content: bytes, extension: str, content_type: str) -> str:
        key = f"dishes/{uuid4().hex}{extension}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        return f"{self.public_base}/{key}"


def _validated_image(content: bytes, requested_extension: str) -> tuple[bytes, str, str]:
    try:
        with Image.open(BytesIO(content)) as candidate:
            candidate.verify()
        with Image.open(BytesIO(content)) as source:
            image_format = (source.format or "").upper()
            extension = FORMAT_EXTENSION.get(image_format)
            if not extension:
                raise ValueError("图片内容不是受支持的 JPEG、PNG 或 WebP")
            normalized_request = ".jpg" if requested_extension.lower() == ".jpeg" else requested_extension.lower()
            if extension != normalized_request:
                raise ValueError("图片内容与文件扩展名不一致")
            image = ImageOps.exif_transpose(source)
            output = BytesIO()
            if image_format == "JPEG":
                image.convert("RGB").save(output, "JPEG", quality=88, optimize=True)
            elif image_format == "PNG":
                mode = "RGBA" if "A" in image.getbands() else "RGB"
                image.convert(mode).save(output, "PNG", optimize=True)
            else:
                mode = "RGBA" if "A" in image.getbands() else "RGB"
                image.convert(mode).save(output, "WEBP", quality=88, method=6)
            return output.getvalue(), extension, CONTENT_TYPE[extension]
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("文件不是有效图片") from error


def get_storage_provider() -> StorageProvider:
    provider = os.getenv("UPLOAD_PROVIDER", "local").strip().lower()
    if provider == "local":
        if os.getenv("APP_ENV", "development").lower() == "production":
            logger.error("production_storage_is_local uploaded files may be lost on ephemeral disks")
        return LocalStorageProvider()
    if provider in {"s3", "s3-compatible"}:
        return S3CompatibleStorageProvider()
    raise ValueError(f"不支持的图片存储类型：{provider}")


def storage_readiness() -> dict[str, object]:
    """Return configuration readiness without making a network request."""
    provider = os.getenv("UPLOAD_PROVIDER", "local").strip().lower()
    if provider == "local":
        production = os.getenv("APP_ENV", "development").lower() == "production"
        return {
            "provider": provider,
            "status": "release-blocked" if production else "ready",
            "missing": [],
        }
    if provider in {"s3", "s3-compatible"}:
        missing = [name for name in S3_REQUIRED_ENV if not os.getenv(name)]
        public_base = os.getenv("S3_PUBLIC_BASE_URL", "")
        if public_base and not public_base.startswith("https://"):
            missing.append("S3_PUBLIC_BASE_URL(HTTPS)")
        return {
            "provider": "s3",
            "status": "ready" if not missing else "release-blocked",
            "missing": missing,
        }
    return {"provider": provider, "status": "invalid", "missing": []}


def save_image(content: bytes, extension: str) -> str:
    normalized, actual_extension, content_type = _validated_image(content, extension)
    return get_storage_provider().save(normalized, actual_extension, content_type)
