from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m, schemas as s
from ..db import get_session
from ..services import graph

router = APIRouter(prefix="/api/projects/{project_id}", tags=["assets and links"])


def version_payload(row: m.AssetVersion) -> s.VersionOut:
    return s.VersionOut(asset_id=row.asset_id, version=row.version, sha256=row.sha256,
                        relative_path=row.relative_path, description=row.description, source=row.source)


@router.get("/assets", response_model=list[s.AssetPayload])
def list_assets(project_id: str, db: Session = Depends(get_session)) -> list[s.AssetPayload]:
    graph.require_project(db, project_id)
    return [graph.asset_payload(x) for x in db.scalars(select(m.Asset).where(m.Asset.project_id == project_id).order_by(m.Asset.name)).all()]


@router.post("/assets", response_model=s.AssetPayload, status_code=201)
def create_asset(project_id: str, payload: s.AssetCreate,
                 db: Session = Depends(get_session)) -> s.AssetPayload:
    project = graph.require_project(db, project_id)
    asset = graph.insert_asset(db, project, payload)
    graph.touch(project)
    db.commit()
    return graph.asset_payload(asset)


@router.patch("/assets/{asset_id}", response_model=s.AssetPayload)
def update_asset(project_id: str, asset_id: str, payload: s.AssetPatch,
                 db: Session = Depends(get_session)) -> s.AssetPayload:
    project = graph.require_project(db, project_id)
    graph.check_revision(project, payload.expected_revision)
    asset = graph.patch_asset(db, project, asset_id, payload.model_dump(exclude_unset=True, exclude={"expected_revision"}))
    graph.touch(project)
    db.commit()
    return graph.asset_payload(asset)


@router.get("/assets/{asset_id}/versions", response_model=list[s.VersionOut])
def list_versions(project_id: str, asset_id: str,
                  db: Session = Depends(get_session)) -> list[s.VersionOut]:
    graph.require_asset(db, project_id, asset_id)
    rows = db.scalars(select(m.AssetVersion).where(m.AssetVersion.asset_id == asset_id).order_by(m.AssetVersion.version)).all()
    return [version_payload(x) for x in rows]


@router.post("/assets/{asset_id}/versions", response_model=s.VersionOut, status_code=201)
def create_version(project_id: str, asset_id: str, payload: s.VersionCreate,
                   db: Session = Depends(get_session)) -> s.VersionOut:
    project = graph.require_project(db, project_id)
    graph.check_revision(project, payload.expected_revision)
    row = graph.publish_asset_version(db, project, asset_id, sha256=payload.sha256,
                                      relative_path=payload.relative_path, description=payload.description)
    graph.touch(project)
    db.commit()
    return version_payload(row)


@router.put("/shots/{shot_id}/assets/{asset_id}", response_model=s.AssetLinkPayload)
def upsert_link(project_id: str, shot_id: str, asset_id: str, payload: s.LinkUpsert,
                db: Session = Depends(get_session)) -> s.AssetLinkPayload:
    project = graph.require_project(db, project_id)
    graph.check_revision(project, payload.expected_revision)
    result = graph.upsert_link(db, project, shot_id, asset_id, payload.pinned_version)
    graph.touch(project)
    db.commit()
    return result


@router.delete("/shots/{shot_id}/assets/{asset_id}", status_code=204)
def unlink_asset(project_id: str, shot_id: str, asset_id: str,
                 db: Session = Depends(get_session)) -> None:
    project = graph.require_project(db, project_id)
    graph.remove_link(db, project, shot_id, asset_id)
    graph.touch(project)
    db.commit()
