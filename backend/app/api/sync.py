from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas as s
from ..db import get_session
from ..services import graph

router = APIRouter(prefix="/api/projects", tags=["sync"])


@router.post("/{project_id}/sync-batch", response_model=s.SyncBatchOut)
def sync_batch(project_id: str, payload: s.SyncBatch,
               db: Session = Depends(get_session)) -> s.SyncBatchOut:
    project = graph.require_project(db, project_id)
    graph.apply_batch(db, project, payload)
    db.commit()
    return s.SyncBatchOut(
        snapshot=graph.snapshot(db, project),
        storyboards=[graph.storyboard_payload(row) for row in graph.storyboard_rows(db, project_id)],
    )
