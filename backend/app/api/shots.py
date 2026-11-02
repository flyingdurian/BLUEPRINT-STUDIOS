from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas as s, models as m
from ..db import get_session
from ..services import graph

router = APIRouter(prefix="/api/projects/{project_id}/shots", tags=["shots"])


@router.put("/sync", response_model=s.SnapshotOut)
def sync_shots(project_id: str, payload: s.ShotSync,
               db: Session = Depends(get_session)) -> s.SnapshotOut:
    project = graph.require_project(db, project_id)
    graph.apply_shot_sync(db, project, payload)
    db.commit()
    return graph.snapshot(db, project)


@router.patch("/{shot_id}", response_model=s.ShotPayload)
def update_shot(project_id: str, shot_id: str, payload: s.ShotPatch,
                db: Session = Depends(get_session)) -> s.ShotPayload:
    project = graph.require_project(db, project_id)
    graph.check_revision(project, payload.expected_revision)
    shot = graph.require_shot(db, project_id, shot_id)
    for name, value in payload.model_dump(exclude_unset=True, exclude={"expected_revision"}).items():
        if value is not None:
            setattr(shot, name, value)
    # Guard against an individual timing edit overlapping another shot.
    siblings = db.scalars(select(m.Shot).where(m.Shot.project_id == project_id, m.Shot.id != shot_id)).all()
    for other in siblings:
        if shot.start_frame < other.start_frame + other.duration_frames and other.start_frame < shot.start_frame + shot.duration_frames:
            raise HTTPException(422, f"Timing overlaps {other.code}; use /shots/sync for a coordinated retime")
    graph.touch(project)
    db.commit()
    return graph.shot_payload(shot)
