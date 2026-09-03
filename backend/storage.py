"""Validated image storage with local and S3-compatible providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
import logging
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from core.settings import Settings, load_settings


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
    def __init__(self, settings: Settings | None = None):
        """Build an S3 client from the configuration visible at construction time."""
        import boto3

        settings = settings or load_settings()
        required = {
            "S3_BUCKET": settings.s3_bucket,
            "S3_ACCESS_KEY_ID": settings.s3_access_key_id_value,
            "S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key_value,
            "S3_PUBLIC_BASE_URL": settings.s3_public_base_url,
        }
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
            endpoint_url=settings.s3_endpoint or None,
            region_name=settings.s3_region or None,
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


class DatabaseStorageProvider(StorageProvider):
    """Persist compressed images in PostgreSQL for small private deployments."""

    def save(self, content: bytes, extension: str, content_type: str) -> str:
        del extension
        from database import SessionLocal
        import models

        image_id = uuid4().hex
        with SessionLocal() as db:
            db.add(
                models.UploadedImage(
                    id=image_id,
                    content_type=content_type,
                    content=content,
                    size=len(content),
                )
            )
            db.commit()
        return f"/api/images/{image_id}"


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


def _webp_thumbnail(content: bytes, max_edge: int = 960) -> bytes:
    """Create a bounded WebP derivative while preserving the validated original."""
    try:
        with Image.open(BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            mode = "RGBA" if "A" in image.getbands() else "RGB"
            output = BytesIO()
            image.convert(mode).save(output, "WEBP", quality=82, method=6)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("文件不是有效图片") from error


def get_storage_provider() -> StorageProvider:
    """Select a provider from the runtime-observable upload configuration."""
    settings = load_settings()
    provider = settings.upload_provider_name
    if provider == "local":
        if settings.is_production:
            logger.error("production_storage_is_local uploaded files may be lost on ephemeral disks")
        return LocalStorageProvider()
    if provider in {"s3", "s3-compatible"}:
        return S3CompatibleStorageProvider(settings)
    if provider in {"database", "postgresql"}:
        return DatabaseStorageProvider()
    raise ValueError(f"不支持的图片存储类型：{provider}")


def storage_readiness() -> dict[str, object]:
    """Return configuration readiness without making a network request."""
    settings = load_settings()
    provider = settings.upload_provider_name
    if provider == "local":
        return {
            "provider": provider,
            "status": "release-blocked" if settings.is_production else "ready",
            "missing": [],
        }
    if provider in {"s3", "s3-compatible"}:
        values = {
            "S3_BUCKET": settings.s3_bucket,
            "S3_ACCESS_KEY_ID": settings.s3_access_key_id_value,
            "S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key_value,
            "S3_PUBLIC_BASE_URL": settings.s3_public_base_url,
        }
        missing = [name for name in S3_REQUIRED_ENV if not values[name]]
        public_base = settings.s3_public_base_url
        if public_base and not public_base.startswith("https://"):
            missing.append("S3_PUBLIC_BASE_URL(HTTPS)")
        return {
            "provider": "s3",
            "status": "ready" if not missing else "release-blocked",
            "missing": missing,
        }
    if provider in {"database", "postgresql"}:
        return {
            "provider": "database",
            "status": "ready",
            "missing": [],
        }
    return {"provider": provider, "status": "invalid", "missing": []}


def save_image(content: bytes, extension: str) -> str:
    """Preserve the original upload contract for compatibility callers."""
    normalized, actual_extension, content_type = _validated_image(content, extension)
    return get_storage_provider().save(normalized, actual_extension, content_type)


def save_image_variants(content: bytes, extension: str) -> dict[str, str]:
    """Store the compatible original plus a small WebP derivative for dish cards."""
    normalized, actual_extension, content_type = _validated_image(content, extension)
    thumbnail = _webp_thumbnail(normalized)
    provider = get_storage_provider()
    return {
        "image_url": provider.save(normalized, actual_extension, content_type),
        "thumbnail_url": provider.save(thumbnail, ".webp", CONTENT_TYPE[".webp"]),
    }
