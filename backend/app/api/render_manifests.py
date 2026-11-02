"""Freeze a render job. This route does not start Godot or a render queue."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import CamelModel
from ..services.render_manifest import ManifestCompileError, compile_render_manifest

router = APIRouter(prefix="/api/projects/{project_id}/render-manifests", tags=["renders"])


class RenderManifestRequest(CamelModel):
    quality: Literal["previs", "production"] = "previs"
    allow_proxy: bool = False


class RenderManifestOut(CamelModel):
    job_id: str
    project_id: str
    revision: int = Field(ge=0)
    manifest_relative_path: str
    manifest_sha256: str
    frame_count: int = Field(ge=1)
    shot_count: int = Field(ge=1)
    unresolved_count: int = Field(ge=0)
    stand_in: bool
    quality: Literal["previs", "production"]


@router.post("", response_model=RenderManifestOut, status_code=201)
def compile_manifest(project_id: str, payload: RenderManifestRequest, db: Session = Depends(get_session)) -> RenderManifestOut:
    try:
        result = compile_render_manifest(db, project_id, quality=payload.quality, allow_proxy=payload.allow_proxy)
    except ManifestCompileError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return RenderManifestOut(
        job_id=str(result["job_id"]), project_id=str(result["project_id"]), revision=int(result["revision"]),
        manifest_relative_path=str(result["manifest_relative_path"]), manifest_sha256=str(result["manifest_sha256"]),
        frame_count=int(result["frame_count"]), shot_count=int(result["shot_count"]),
        unresolved_count=int(result["unresolved_count"]), stand_in=bool(result["stand_in"]), quality=payload.quality,
    )
