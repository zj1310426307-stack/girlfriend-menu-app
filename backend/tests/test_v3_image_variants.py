"""V3 uploads keep original URLs while offering bounded WebP dish thumbnails."""

from io import BytesIO

from PIL import Image

import storage


class RecordingStorage(storage.StorageProvider):
    """Capture stored objects without touching local, database or S3 providers."""

    def __init__(self):
        self.objects: list[tuple[bytes, str, str]] = []

    def save(self, content: bytes, extension: str, content_type: str) -> str:
        """Record one object and return a stable test URL."""
        self.objects.append((content, extension, content_type))
        return f"https://images.example/{len(self.objects)}{extension}"


def test_image_variants_preserve_original_and_add_bounded_webp(monkeypatch) -> None:
    """Keep old clients on image_url while new dish cards consume thumbnail_url."""
    raw = BytesIO()
    Image.new("RGB", (1800, 1200), color=(143, 185, 150)).save(raw, "PNG")
    provider = RecordingStorage()
    monkeypatch.setattr(storage, "get_storage_provider", lambda: provider)

    result = storage.save_image_variants(raw.getvalue(), ".png")

    assert result == {
        "image_url": "https://images.example/1.png",
        "thumbnail_url": "https://images.example/2.webp",
    }
    assert provider.objects[0][1:] == (".png", "image/png")
    assert provider.objects[1][1:] == (".webp", "image/webp")
    with Image.open(BytesIO(provider.objects[1][0])) as thumbnail:
        assert thumbnail.format == "WEBP"
        assert max(thumbnail.size) <= 960
