"""Assemble narration, captions, and an H.264 MP4 for a frozen render job."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import CamelModel
from ..services.audio_assembler import AudioAssemblyError, active_job_id
from ..services.ffmpeg_assembly import assemble_distribution, describe_job, media_file
from ..services.ffmpeg_bin import MediaToolError
from ..services.graph import require_project

router = APIRouter(prefix="/api/projects/{project_id}/renders", tags=["renders"])


class AssembleRequest(CamelModel):
    burn_captions: bool = True


class RenderShotStatus(CamelModel):
    code: str
    shot_id: str | None = None
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(ge=1)
    start_seconds: float = Field(ge=0)
    narration: str
    wav_present: bool
    source_seconds: float | None = None


class RenderJobStatus(CamelModel):
    job_id: str
    project_id: str
    revision: int = Field(ge=0)
    quality: str
    production_locked: bool
    frame_count: int = Field(ge=1)
    shot_count: int = Field(ge=1)
    duration_seconds: float = Field(gt=0)
    audio_status: Literal["missing", "partial", "ready", "aligned"]
    tracks_present: int = Field(ge=0)
    tracks_expected: int = Field(ge=1)
    mix_ready: bool
    captions_ready: bool
    silent_video_ready: bool
    preview_ready: bool
    final_ready: bool
    burned_captions: bool
    shots: list[RenderShotStatus]
    preview_url: str | None = None
    download_url: str | None = None
    captions_url: str | None = None


def _raise_tool(exc: MediaToolError) -> None:
    raise HTTPException(exc.status_code, str(exc)) from exc


def _status(project_id: str, job_id: str) -> RenderJobStatus:
    try:
        payload = describe_job(job_id)
    except MediaToolError as exc:
        _raise_tool(exc)
    if payload["project_id"] != project_id:
        raise HTTPException(404, "Render job not found")
    base = f"/api/projects/{project_id}/renders/{job_id}/media"
    payload["preview_url"] = f"{base}/pilot-preview.mp4" if payload["preview_ready"] else None
    payload["download_url"] = f"{base}/pilot-final.mp4" if payload["final_ready"] else None
    payload["captions_url"] = f"{base}/captions.vtt" if payload["captions_ready"] else None
    return RenderJobStatus.model_validate(payload)


@router.get("/active", response_model=RenderJobStatus)
def active_render(project_id: str, db: Session = Depends(get_session)) -> RenderJobStatus:
    require_project(db, project_id)
    try:
        job_id = active_job_id(project_id)
    except AudioAssemblyError as exc:
        _raise_tool(exc)
    return _status(project_id, job_id)


@router.get("/{job_id}", response_model=RenderJobStatus)
def render_status(project_id: str, job_id: str, db: Session = Depends(get_session)) -> RenderJobStatus:
    require_project(db, project_id)
    return _status(project_id, job_id)


@router.post("/{job_id}/assemble", response_model=RenderJobStatus, status_code=201)
def assemble_render(project_id: str, job_id: str, payload: AssembleRequest, db: Session = Depends(get_session)) -> RenderJobStatus:
    require_project(db, project_id)
    try:
        manifest_project = describe_job(job_id)["project_id"]
    except MediaToolError as exc:
        _raise_tool(exc)
    if manifest_project != project_id:
        raise HTTPException(404, "Render job not found")
    try:
        assemble_distribution(job_id, burn_captions=payload.burn_captions)
    except MediaToolError as exc:
        _raise_tool(exc)
    return _status(project_id, job_id)


@router.get("/{job_id}/media/{filename}")
def render_media(project_id: str, job_id: str, filename: str, db: Session = Depends(get_session)) -> FileResponse:
    require_project(db, project_id)
    try:
        if describe_job(job_id)["project_id"] != project_id:
            raise HTTPException(404, "Render job not found")
        path, media_type = media_file(job_id, filename)
    except MediaToolError as exc:
        _raise_tool(exc)
    disposition = "attachment" if filename == "pilot-final.mp4" else "inline"
    return FileResponse(path, media_type=media_type, filename=filename, content_disposition_type=disposition)
