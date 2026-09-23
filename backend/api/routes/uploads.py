"""Administrator image upload route with the established validation limits."""

import base64
import binascii
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from api.dependencies import verify_admin_token
from database import get_db
import models
import schemas
from storage import save_image_variants


router = APIRouter()

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def _store_validated_image(filename: str, content_type: str, content: bytes) -> dict[str, str]:
    """Apply the same type, size, content and storage rules to every upload transport."""
    extension = Path(filename).suffix.lower()
    if (
        extension not in ALLOWED_IMAGE_EXTENSIONS
        or content_type not in ALLOWED_IMAGE_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 jpg、jpeg、png、webp 图片",
        )
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="图片大小不能超过 5MB",
        )

    try:
        return save_image_variants(content, extension)
    except ValueError as error:
        invalid_image = any(
            marker in str(error) for marker in ("有效图片", "扩展名", "图片内容")
        )
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
                if invalid_image
                else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(error),
        ) from error


@router.get("/api/images/{image_id}")
def uploaded_image(image_id: str, db: Session = Depends(get_db)):
    """Serve one immutable database-backed image without authentication."""
    if len(image_id) != 32 or not all(char in "0123456789abcdef" for char in image_id):
        raise HTTPException(status_code=404, detail="图片不存在")
    item = db.get(models.UploadedImage, image_id)
    if not item:
        raise HTTPException(status_code=404, detail="图片不存在")
    return Response(
        content=item.content,
        media_type=item.content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.post("/api/upload/image", dependencies=[Depends(verify_admin_token)])
async def upload_image(file: UploadFile = File(...)):
    """Validate and store one image without changing the existing upload contract."""
    content = await file.read(MAX_IMAGE_SIZE + 1)
    await file.close()
    return _store_validated_image(file.filename or "", file.content_type or "", content)


@router.post("/api/upload/image-base64", dependencies=[Depends(verify_admin_token)])
def upload_image_base64(payload: schemas.ImageUploadBase64):
    """Accept an image JSON envelope when Mini Program private access cannot use uploadFile."""
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片编码不正确",
        ) from error
    return _store_validated_image(payload.filename, payload.content_type, content)
