from __future__ import annotations

from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
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
    asset_id = payload.id or str(uuid4())
    if db.get(m.Asset, asset_id):
        raise HTTPException(409, "Asset ID already exists")
    asset = m.Asset(id=asset_id, project_id=project_id, name=payload.name, category=payload.category,
                    status=payload.status, current_version=1, color=payload.color, shorthand=payload.shorthand)
    db.add(asset)
    db.flush()
    db.add(m.AssetVersion(asset_id=asset_id, version=1, source="created", description="Initial asset version"))
    graph.touch(project)
    db.commit()
    return graph.asset_payload(asset)


@router.patch("/assets/{asset_id}", response_model=s.AssetPayload)
def update_asset(project_id: str, asset_id: str, payload: s.AssetPatch,
                 db: Session = Depends(get_session)) -> s.AssetPayload:
    project = graph.require_project(db, project_id)
    graph.check_revision(project, payload.expected_revision)
    asset = graph.require_asset(db, project_id, asset_id)
    for name, value in payload.model_dump(exclude_unset=True, exclude={"expected_revision"}).items():
        if value is not None:
            setattr(asset, name, value)
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
    asset = graph.require_asset(db, project_id, asset_id)
    new_version = asset.current_version + 1
    row = m.AssetVersion(asset_id=asset_id, version=new_version, sha256=payload.sha256,
                         relative_path=payload.relative_path, description=payload.description, source="manual")
    db.add(row)
    asset.current_version = new_version
    graph.touch(project)
    db.commit()
    return version_payload(row)


@router.put("/shots/{shot_id}/assets/{asset_id}", response_model=s.AssetLinkPayload)
def upsert_link(project_id: str, shot_id: str, asset_id: str, payload: s.LinkUpsert,
                db: Session = Depends(get_session)) -> s.AssetLinkPayload:
    project = graph.require_project(db, project_id)
    graph.check_revision(project, payload.expected_revision)
    graph.require_shot(db, project_id, shot_id)
    asset = graph.require_asset(db, project_id, asset_id)
    version = payload.pinned_version if payload.pinned_version is not None else asset.current_version
    if db.get(m.AssetVersion, (asset_id, version)) is None:
        raise HTTPException(422, "Pinned asset version does not exist")
    link = db.get(m.ShotAssetLink, (shot_id, asset_id))
    if link is None:
        link = m.ShotAssetLink(shot_id=shot_id, asset_id=asset_id, pinned_version=version)
        db.add(link)
    else:
        link.pinned_version = version
    graph.touch(project)
    db.commit()
    return s.AssetLinkPayload(shot_id=shot_id, asset_id=asset_id, pinned_version=version)


@router.delete("/shots/{shot_id}/assets/{asset_id}", status_code=204)
def unlink_asset(project_id: str, shot_id: str, asset_id: str,
                 db: Session = Depends(get_session)) -> None:
    project = graph.require_project(db, project_id)
    graph.require_shot(db, project_id, shot_id)
    graph.require_asset(db, project_id, asset_id)
    link = db.get(m.ShotAssetLink, (shot_id, asset_id))
    if link is None:
        raise HTTPException(404, "Shot-asset link not found")
    db.delete(link)
    graph.touch(project)
    db.commit()
