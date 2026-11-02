"""Content-addressed media files. Bytes are hashed while they stream to disk."""
from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile

CHUNK_BYTES = 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 256 * 1024 * 1024

ALLOWED_MEDIA_TYPES = frozenset({
    "image/png", "image/jpeg", "image/webp", "image/gif",
    "video/mp4", "video/webm", "video/quicktime",
    "audio/wav", "audio/mpeg", "audio/ogg", "audio/flac", "audio/webm",
    "model/gltf+json", "model/gltf-binary",
})


@dataclass(frozen=True)
class StagedUpload:
    path: Path
    sha256: str
    byte_size: int
    media_type: str


def media_root() -> Path:
    override = os.getenv("BLUEPRINT_MEDIA_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "media"


def max_upload_bytes() -> int:
    raw = os.getenv("BLUEPRINT_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES
    return value if value > 0 else DEFAULT_MAX_UPLOAD_BYTES


def ensure_media_root() -> Path:
    root = media_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "_staging").mkdir(parents=True, exist_ok=True)
    return root


def media_type_of(upload: UploadFile) -> str:
    return (upload.content_type or "").split(";", 1)[0].strip().lower()


def relative_blob_path(digest: str) -> str:
    return f"{digest[:2]}/{digest[2:4]}/{digest}"


def blob_file(digest: str) -> Path:
    return media_root() / digest[:2] / digest[2:4] / digest


async def stage_upload(upload: UploadFile, *, chunk_size: int = CHUNK_BYTES) -> StagedUpload:
    """Hash and spool the upload. The digest path is not touched yet."""
    media_type = media_type_of(upload)
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(415, "Unsupported media type")
    root = ensure_media_root()
    descriptor, name = tempfile.mkstemp(dir=root / "_staging")
    path = Path(name)
    hasher = hashlib.sha256()
    size = 0
    limit = max_upload_bytes()
    try:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise HTTPException(413, "Upload exceeds the byte limit")
            hasher.update(chunk)
            os.write(descriptor, chunk)
        if size == 0:
            raise HTTPException(422, "Upload is empty")
    except Exception:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        raise
    os.close(descriptor)
    return StagedUpload(path=path, sha256=hasher.hexdigest(), byte_size=size, media_type=media_type)


def stream_matches(path: Path, digest: str, size: int) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_BYTES)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest() == digest


def place_blob(staged: StagedUpload) -> str:
    """Move a staged file into its digest path. An existing matching file is reused."""
    relative = relative_blob_path(staged.sha256)
    dest = blob_file(staged.sha256)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dest.exists():
            if not stream_matches(dest, staged.sha256, staged.byte_size):
                raise HTTPException(409, "Existing media blob does not match its digest and was not overwritten")
            return relative
        created = _link_or_exclusive_copy(staged.path, dest)
        if not stream_matches(dest, staged.sha256, staged.byte_size):
            if created:
                dest.unlink(missing_ok=True)
            raise HTTPException(409, "Stored media blob failed digest verification")
        return relative
    finally:
        staged.path.unlink(missing_ok=True)


def _link_or_exclusive_copy(source: Path, dest: Path) -> bool:
    """Return True only when this call created dest. Never replace an existing file."""
    try:
        os.link(source, dest)
        return True
    except FileExistsError:
        return False
    except OSError:
        pass
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(dest, flags)
    except FileExistsError:
        return False
    try:
        with os.fdopen(descriptor, "wb") as target, source.open("rb") as handle:
            while True:
                chunk = handle.read(CHUNK_BYTES)
                if not chunk:
                    break
                target.write(chunk)
        return True
    except Exception:
        dest.unlink(missing_ok=True)
        raise
