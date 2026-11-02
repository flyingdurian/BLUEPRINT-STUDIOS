"""Short database commit for a file that has already been hashed and stored."""
from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models as m
from ..services import graph

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")


def validate_idempotency_key(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if _IDEMPOTENCY_KEY.fullmatch(value) is None:
        raise HTTPException(422, "Idempotency-Key must be 1-80 characters of letters, numbers, or . _ : -")
    return value


def register_upload(db: Session, project: m.Project, asset_id: str, *, digest: str, byte_size: int,
                    media_type: str, relative_path: str, description: str, expected_revision: int | None,
                    idempotency_key: str | None) -> tuple[m.AssetVersion, m.MediaBlob, bool]:
    """Publish one immutable version. Returns the version, blob, and whether this was a replay."""
    db.refresh(project)
    graph.require_asset(db, project.id, asset_id)
    if idempotency_key:
        receipt = db.get(m.UploadReceipt, (project.id, idempotency_key))
        if receipt is not None:
            if receipt.asset_id != asset_id or receipt.sha256 != digest or receipt.byte_size != byte_size:
                raise HTTPException(409, "Idempotency key was already used for different content")
            existing = db.get(m.AssetVersion, (asset_id, receipt.version))
            blob = db.get(m.MediaBlob, receipt.sha256)
            if existing is None or blob is None:
                raise HTTPException(409, "Upload receipt does not match a stored version")
            return existing, blob, True
    graph.check_revision(project, expected_revision)
    blob = db.get(m.MediaBlob, digest)
    if blob is None:
        blob = m.MediaBlob(sha256=digest, byte_size=byte_size, media_type=media_type, relative_path=relative_path)
        db.add(blob)
        db.flush()
    version = graph.publish_asset_version(
        db, project, asset_id, sha256=digest, relative_path=relative_path, description=description,
        source="upload", blob_sha256=digest,
    )
    if idempotency_key:
        db.add(m.UploadReceipt(project_id=project.id, idempotency_key=idempotency_key, asset_id=asset_id,
                               sha256=digest, byte_size=byte_size, version=version.version))
    graph.touch(project)
    return version, blob, False
