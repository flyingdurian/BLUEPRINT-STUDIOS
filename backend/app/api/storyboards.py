from __future__ import annotations

from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m, schemas as s
from ..db import get_session
from ..services import graph

router = APIRouter(prefix="/api/projects/{project_id}/storyboards", tags=["storyboards"])


def output(row: m.Storyboard) -> s.StoryboardOut:
    return s.StoryboardOut(id=row.id, project_id=row.project_id, shot_id=row.shot_id,
                           crop_mode=row.crop_mode, media_path=row.media_path,
                           asset_id=row.asset_id, asset_version=row.asset_version,
                           sort_index=row.sort_index, notes=row.notes)


@router.get("", response_model=list[s.StoryboardOut])
def list_storyboards(project_id: str, db: Session = Depends(get_session)) -> list[s.StoryboardOut]:
    graph.require_project(db, project_id)
    rows = db.scalars(select(m.Storyboard).where(m.Storyboard.project_id == project_id).order_by(m.Storyboard.sort_index)).all()
    return [output(x) for x in rows]


@router.post("", response_model=s.StoryboardOut, status_code=201)
def create_storyboard(project_id: str, payload: s.StoryboardCreate,
                      db: Session = Depends(get_session)) -> s.StoryboardOut:
    project = graph.require_project(db, project_id)
    graph.require_shot(db, project_id, payload.shot_id)
    if (payload.asset_id is None) != (payload.asset_version is None):
        raise HTTPException(422, "assetId and assetVersion must both be specified or both omitted")
    if payload.asset_id:
        graph.require_asset(db, project_id, payload.asset_id)
        if db.get(m.AssetVersion, (payload.asset_id, payload.asset_version)) is None:
            raise HTTPException(422, "Storyboard asset version does not exist")
    id_ = payload.id or str(uuid4())
    if db.get(m.Storyboard, id_):
        raise HTTPException(409, "Storyboard ID exists")
    row = m.Storyboard(id=id_, project_id=project_id, shot_id=payload.shot_id,
                       crop_mode=payload.crop_mode, media_path=payload.media_path,
                       asset_id=payload.asset_id, asset_version=payload.asset_version,
                       sort_index=payload.sort_index, notes=payload.notes)
    db.add(row)
    graph.touch(project)
    db.commit()
    return output(row)
