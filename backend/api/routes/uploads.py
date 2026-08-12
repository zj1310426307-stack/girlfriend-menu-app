"""Administrator image upload route with the established validation limits."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.dependencies import verify_admin_token
from storage import save_image


router = APIRouter()

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


@router.post("/api/upload/image", dependencies=[Depends(verify_admin_token)])
async def upload_image(file: UploadFile = File(...)):
    """Validate and store one image without changing the existing upload contract."""
    extension = Path(file.filename or "").suffix.lower()
    if (
        extension not in ALLOWED_IMAGE_EXTENSIONS
        or file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 jpg、jpeg、png、webp 图片",
        )

    content = await file.read(MAX_IMAGE_SIZE + 1)
    await file.close()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="图片大小不能超过 5MB",
        )

    try:
        image_url = save_image(content, extension)
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
        )
    return {"image_url": image_url}
