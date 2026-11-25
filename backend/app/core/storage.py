"""
Local File Storage Service - SMART LEARNING PRO
Handles secure upload validation (extension allowlist, magic bytes verification, max size)
and safe local disk persistence with path traversal prevention.
"""

import os
import re
import uuid
from pathlib import Path
from typing import Optional, Set, Tuple

from fastapi import HTTPException, UploadFile, status

from app.config import settings

MAX_UPLOAD_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB

ALLOWED_ASSIGNMENT_EXTENSIONS: Set[str] = {
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".csv",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

# Magic byte prefixes for binary format validation (prevents disguised executables)
_MAGIC_SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
    ".docx": (b"PK\x03\x04", b"PK\x05\x06"),
    ".xlsx": (b"PK\x03\x04", b"PK\x05\x06"),
    ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
}


def get_storage_root() -> Path:
    """Return resolved root directory for local file storage."""
    root = Path(settings.LOCAL_STORAGE_PATH).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_display_filename(filename: Optional[str]) -> str:
    """Sanitize original filename for display and Content-Disposition safety."""
    if not filename:
        return "tep_dinh_kem"
    base = os.path.basename(filename).strip()
    cleaned = re.sub(r"[^\w\-. \u00C0-\u1EF9]", "_", base)
    return cleaned[:200] or "tep_dinh_kem"


def validate_upload_bytes(
    filename: Optional[str],
    content: bytes,
    allowed_extensions: Set[str] = ALLOWED_ASSIGNMENT_EXTENSIONS,
    max_size_bytes: int = MAX_UPLOAD_FILE_SIZE_BYTES,
) -> Tuple[str, str]:
    """
    Validate file extension, size limit, and magic bytes.
    Returns (safe_display_name, normalized_extension).
    """
    safe_name = sanitize_display_filename(filename)
    ext = Path(safe_name).suffix.lower()

    if not ext or ext not in allowed_extensions:
        allowed_str = ", ".join(sorted(allowed_extensions))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng tệp '{ext or '(không có)'}' không được hỗ trợ. Cho phép: {allowed_str}.",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp tải lên bị rỗng.",
        )

    if len(content) > max_size_bytes:
        max_mb = round(max_size_bytes / (1024 * 1024), 1)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Dung lượng tệp vượt quá giới hạn cho phép ({max_mb} MB).",
        )

    # Check magic bytes for known binary formats
    expected_sigs = _MAGIC_SIGNATURES.get(ext)
    if expected_sigs is not None:
        if not any(content.startswith(sig) for sig in expected_sigs):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nội dung tệp không khớp với định dạng '{ext}'. Vui lòng kiểm tra lại tệp gốc.",
            )

    # For plain-text formats, verify not containing NUL bytes (binary executable masquerading as text)
    if ext in {".csv", ".txt", ".json"} and b"\x00" in content[:4096]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tệp văn bản '{ext}' chứa dữ liệu nhị phân không hợp lệ.",
        )

    return safe_name, ext


async def save_upload_file(
    upload: UploadFile,
    subdir: str,
    allowed_extensions: Set[str] = ALLOWED_ASSIGNMENT_EXTENSIONS,
    max_size_bytes: int = MAX_UPLOAD_FILE_SIZE_BYTES,
) -> Tuple[str, str, int, Optional[str]]:
    """
    Read, validate, and persist an UploadFile safely under LOCAL_STORAGE_PATH/subdir.
    Returns (storage_key, safe_display_name, size_bytes, content_type).
    """
    content = await upload.read()
    safe_name, ext = validate_upload_bytes(
        filename=upload.filename,
        content=content,
        allowed_extensions=allowed_extensions,
        max_size_bytes=max_size_bytes,
    )

    clean_subdir = re.sub(r"[^a-zA-Z0-9_\-/]", "", subdir).strip("/")
    root = get_storage_root()
    target_dir = (root / clean_subdir).resolve()
    target_dir.relative_to(root)  # Path traversal guard
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}{ext}"
    target_path = (target_dir / stored_filename).resolve()
    target_path.relative_to(root)

    target_path.write_bytes(content)

    storage_key = f"{clean_subdir}/{stored_filename}" if clean_subdir else stored_filename
    return storage_key, safe_name, len(content), upload.content_type


def resolve_storage_path(storage_key: str) -> Path:
    """
    Resolve a storage key safely inside LOCAL_STORAGE_PATH.
    Raises HTTPException 404 if missing or invalid traversal.
    """
    root = get_storage_root()
    try:
        candidate = (root / storage_key).resolve()
        candidate.relative_to(root)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tệp đính kèm không tồn tại hoặc đường dẫn không hợp lệ.",
        )

    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tệp đính kèm không tồn tại trên hệ thống lưu trữ.",
        )

    return candidate
