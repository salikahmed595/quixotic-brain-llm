"""Upload validation — PRD §13.1 (V1 formats) and §51 (file validation, upload size limits)."""
from __future__ import annotations

import json
import os

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md", "markdown", "json", "csv"}   # §13.1


class InvalidUpload(ValueError):
    pass


def extension_of(filename: str) -> str:
    return os.path.splitext(filename)[1].lower().lstrip(".")


def validate_upload(filename: str, data: bytes, max_bytes: int) -> str:
    """Return the normalized extension or raise InvalidUpload."""
    ext = extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidUpload(f"unsupported file type .{ext or '?'}; V1 accepts PDF, DOCX, TXT, Markdown, JSON, CSV")
    if not data:
        raise InvalidUpload("file is empty")
    if len(data) > max_bytes:
        raise InvalidUpload(f"file exceeds the {max_bytes}-byte upload limit")
    if ext == "pdf" and not data.startswith(b"%PDF"):
        raise InvalidUpload("file content is not a PDF")
    if ext == "docx" and not data.startswith(b"PK"):
        raise InvalidUpload("file content is not a DOCX")
    if ext == "json":
        try:
            json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise InvalidUpload("file content is not valid JSON")
    return "md" if ext == "markdown" else ext


def safe_filename(filename: str) -> str:
    return os.path.basename(filename).replace("\\", "_").replace("/", "_") or "file"
