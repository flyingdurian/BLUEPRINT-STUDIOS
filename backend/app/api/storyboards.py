from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import schemas as s
from ..db import get_session
from ..services import graph

router = APIRouter(prefix="/api/projects/{project_id}/storyboards", tags=["storyboards"])


@router.get("", response_model=list[s.StoryboardOut])
def list_storyboards(project_id: str, db: Session = Depends(get_session)) -> list[s.StoryboardOut]:
    graph.require_project(db, project_id)
    return [graph.storyboard_payload(row) for row in graph.storyboard_rows(db, project_id)]


@router.post("", response_model=s.StoryboardOut, status_code=201)
def create_storyboard(project_id: str, payload: s.StoryboardCreate,
                      db: Session = Depends(get_session)) -> s.StoryboardOut:
    project = graph.require_project(db, project_id)
    row = graph.create_storyboard(db, project, payload)
    graph.touch(project)
    db.commit()
    return graph.storyboard_payload(row)


@router.put("/{storyboard_id}", response_model=s.StoryboardOut)
def update_storyboard(project_id: str, storyboard_id: str, payload: s.StoryboardUpdate,
                      db: Session = Depends(get_session)) -> s.StoryboardOut:
    project = graph.require_project(db, project_id)
    graph.check_revision(project, payload.expected_revision)
    row = graph.replace_storyboard(db, project, storyboard_id, payload)
    graph.touch(project)
    db.commit()
    return graph.storyboard_payload(row)


@router.delete("/{storyboard_id}", status_code=204)
def delete_storyboard(project_id: str, storyboard_id: str,
                      expected_revision: int | None = Query(default=None, alias="expectedRevision", ge=0),
                      db: Session = Depends(get_session)) -> None:
    project = graph.require_project(db, project_id)
    graph.check_revision(project, expected_revision)
    graph.remove_storyboard(db, project, storyboard_id)
    graph.touch(project)
    db.commit()
