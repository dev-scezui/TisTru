"""Detect allowed image types from magic bytes (ignore client Content-Type)."""

from __future__ import annotations

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"


def detect_image_mime(data: bytes) -> str | None:
    """Return image/jpeg, image/png, or image/webp when magic bytes match; else None."""
    if not data:
        return None
    if data.startswith(_JPEG):
        return "image/jpeg"
    if data.startswith(_PNG):
        return "image/png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None
