import os
from pathlib import Path
from uuid import uuid4


UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"


def ensure_upload_directory():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_image(content: bytes, extension: str) -> str:
    provider = os.getenv("UPLOAD_PROVIDER", "local").lower()
    if provider != "local":
        raise ValueError(f"暂未实现的图片存储类型：{provider}")

    ensure_upload_directory()
    filename = f"{uuid4().hex}{extension}"
    (UPLOAD_DIR / filename).write_bytes(content)
    return f"/uploads/{filename}"
