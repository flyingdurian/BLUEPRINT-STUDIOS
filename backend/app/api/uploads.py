from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from ..db import get_session
from ..services import graph, media_store
from ..services.ingestion import register_upload, validate_idempotency_key

router = APIRouter(prefix="/api/projects/{project_id}/assets/{asset_id}/versions", tags=["media"])


def _payload(version: m.AssetVersion, blob: m.MediaBlob, revision: int) -> s.VersionUploadOut:
    return s.VersionUploadOut(
        asset_id=version.asset_id, version=version.version, sha256=blob.sha256,
        relative_path=blob.relative_path, description=version.description, source=version.source,
        byte_size=blob.byte_size, media_type=blob.media_type, revision=revision,
    )


@router.post("/upload", response_model=s.VersionUploadOut, status_code=201)
async def upload_asset_version(
    project_id: str, asset_id: str, response: Response,
    file: Annotated[UploadFile, File()],
    description: Annotated[str, Form()] = "",
    expected_revision: Annotated[int | None, Form(alias="expectedRevision")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_session),
) -> s.VersionUploadOut:
    if len(description) > 4000:
        raise HTTPException(422, "Description is too long")
    key = validate_idempotency_key(idempotency_key)
    project = graph.require_project(db, project_id)
    graph.require_asset(db, project_id, asset_id)
    # Release the read before the byte stream so SQLite is not held open for the file.
    db.commit()
    staged = await media_store.stage_upload(file)
    try:
        relative = media_store.place_blob(staged)
    finally:
        await file.close()
    version, blob, replayed = register_upload(
        db, project, asset_id, digest=staged.sha256, byte_size=staged.byte_size, media_type=staged.media_type,
        relative_path=relative, description=description, expected_revision=expected_revision, idempotency_key=key,
    )
    if not replayed:
        db.commit()
    response.status_code = 200 if replayed else 201
    return _payload(version, blob, project.revision)
