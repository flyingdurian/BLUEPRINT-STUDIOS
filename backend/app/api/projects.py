from __future__ import annotations

from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m, schemas as s
from ..db import get_session
from ..services import graph

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=s.ProjectOut, status_code=201)
def create_project(payload: s.ProjectCreate, db: Session = Depends(get_session)) -> s.ProjectOut:
    id_ = payload.id or str(uuid4())
    if db.get(m.Project, id_) is not None:
        raise HTTPException(409, "Project ID already exists")
    project = m.Project(id=id_, name=payload.name, fps=payload.fps, revision=0, next_shot_number=1)
    db.add(project)
    db.commit()
    return graph.project_payload(project)


@router.get("", response_model=list[s.ProjectOut])
def list_projects(db: Session = Depends(get_session)) -> list[s.ProjectOut]:
    return [graph.project_payload(p) for p in db.scalars(select(m.Project).order_by(m.Project.created_at)).all()]


@router.get("/{project_id}/snapshot", response_model=s.SnapshotOut)
def get_snapshot(project_id: str, db: Session = Depends(get_session)) -> s.SnapshotOut:
    return graph.snapshot(db, graph.require_project(db, project_id))


@router.post("/{project_id}/bootstrap", response_model=s.SnapshotOut, status_code=201)
def import_bs_m1(project_id: str, payload: s.BootstrapData, db: Session = Depends(get_session)) -> s.SnapshotOut:
    project = graph.require_project(db, project_id)
    graph.bootstrap(db, project, payload)
    db.commit()
    return graph.snapshot(db, project)
