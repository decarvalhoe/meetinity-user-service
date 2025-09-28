"""Utilities for managing file uploads."""

from __future__ import annotations

import os
import time
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB


class UploadError(ValueError):
    """Raised when an uploaded file is invalid."""


def save_user_photo(
    file_storage: FileStorage,
    *,
    user_id: int,
    upload_folder: str,
    url_prefix: str = "/uploads",
) -> str:
    """Persist a user photo to disk and return its public URL."""

    filename = (file_storage.filename or "").strip()
    if not filename:
        raise UploadError("missing filename")

    sanitized = secure_filename(filename)
    if not sanitized:
        raise UploadError("invalid filename")

    ext = sanitized.rsplit(".", 1)[-1].lower() if "." in sanitized else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadError("unsupported file type")

    stream = file_storage.stream
    if hasattr(stream, "seek") and hasattr(stream, "tell"):
        current = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(current)
        if size > MAX_FILE_SIZE:
            raise UploadError("file too large")

    upload_path = Path(upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)

    unique_name = f"user-{user_id}-{int(time.time())}.{ext}"
    destination = upload_path / unique_name
    file_storage.save(destination)

    prefix = url_prefix.rstrip("/")
    if prefix:
        return f"{prefix}/{unique_name}"
    return f"/{unique_name}"
