"""Transactional graph management and BS-M1 serialization boundary."""
from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s


def require_project(db: Session, project_id: str) -> m.Project:
    project = db.get(m.Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def check_revision(project: m.Project, expected: int | None) -> None:
    if expected is not None and expected != project.revision:
        raise HTTPException(409, detail={"message": "Stale project revision", "expected": expected, "actual": project.revision})


def touch(project: m.Project) -> None:
    project.revision += 1


def require_shot(db: Session, project_id: str, shot_id: str) -> m.Shot:
    shot = db.get(m.Shot, shot_id)
    if shot is None or shot.project_id != project_id:
        raise HTTPException(404, "Shot not found in project")
    return shot


def require_asset(db: Session, project_id: str, asset_id: str) -> m.Asset:
    asset = db.get(m.Asset, asset_id)
    if asset is None or asset.project_id != project_id:
        raise HTTPException(404, "Asset not found in project")
    return asset


def assert_shot_graph(shots: dict[str, s.ShotPayload], order: list[str]) -> None:
    if set(shots) != set(order) or len(order) != len(set(order)):
        raise HTTPException(422, "shotOrder must list every shot key exactly once")
    codes: set[str] = set()
    prev_end = 0
    for index, key in enumerate(order):
        shot = shots[key]
        if key != shot.id:
            raise HTTPException(422, f"Shot key {key!r} must equal its stable id")
        if shot.code in codes:
            raise HTTPException(422, f"Duplicate shot code: {shot.code}")
        codes.add(shot.code)
        if index > 0 and shot.start_frame < prev_end:
            raise HTTPException(422, f"Shot {shot.code} overlaps preceding shot")
        prev_end = shot.start_frame + shot.duration_frames


def validate_next_shot_number(shots: dict[str, s.ShotPayload], next_number: int) -> None:
    # BS-M1 uses stable human-readable SH_001 labels and a monotonically
    # increasing creation counter. Never permit a future duplicate label.
    numbered = [int(match.group(1)) for row in shots.values()
                if (match := re.fullmatch(r"SH_(\d+)", row.code))]
    if numbered and next_number <= max(numbered):
        raise HTTPException(422, "nextShotNumber must exceed all numbered SH_ labels")


def shot_payload(row: m.Shot) -> s.ShotPayload:
    return s.ShotPayload(
        id=row.id, code=row.code, start_frame=row.start_frame,
        duration_frames=row.duration_frames, visual=row.visual,
        narration=row.narration, notes=row.notes, art_key=row.art_key, mood=row.mood,
    )


def asset_payload(row: m.Asset) -> s.AssetPayload:
    return s.AssetPayload(
        id=row.id, name=row.name, category=row.category, status=row.status,
        current_version=row.current_version, color=row.color, shorthand=row.shorthand,
    )


def project_payload(row: m.Project) -> s.ProjectOut:
    return s.ProjectOut(id=row.id, name=row.name, fps=row.fps,
                        revision=row.revision, next_shot_number=row.next_shot_number)


def snapshot(db: Session, project: m.Project) -> s.SnapshotOut:
    shots = db.scalars(select(m.Shot).where(m.Shot.project_id == project.id).order_by(m.Shot.sort_index)).all()
    assets = db.scalars(select(m.Asset).where(m.Asset.project_id == project.id).order_by(m.Asset.id)).all()
    shot_ids = [shot.id for shot in shots]
    asset_ids = {asset.id for asset in assets}
    links = db.scalars(select(m.ShotAssetLink).join(m.Shot).where(m.Shot.project_id == project.id)).all()
    return s.SnapshotOut(
        project=project_payload(project), revision=project.revision,
        shots={row.id: shot_payload(row) for row in shots},
        shot_order=shot_ids,
        assets={row.id: asset_payload(row) for row in assets},
        links=[s.AssetLinkPayload(shot_id=l.shot_id, asset_id=l.asset_id,
                                  pinned_version=l.pinned_version) for l in links if l.asset_id in asset_ids],
        next_shot_number=project.next_shot_number,
    )


def apply_shot_sync(db: Session, project: m.Project, payload: s.ShotSync) -> None:
    check_revision(project, payload.expected_revision)
    assert_shot_graph(payload.shots, payload.shot_order)
    validate_next_shot_number(payload.shots, payload.next_shot_number)
    existing = {row.id: row for row in db.scalars(select(m.Shot).where(m.Shot.project_id == project.id)).all()}
    wanted = set(payload.shots)
    for id_, old in existing.items():
        if id_ not in wanted:
            db.delete(old)  # Existing dependent links/storyboards cascade in SQLite.
    for index, id_ in enumerate(payload.shot_order):
        input_row = payload.shots[id_]
        current = existing.get(id_)
        if current is None:
            current = m.Shot(id=id_, project_id=project.id)
            db.add(current)
        elif current.code != input_row.code:
            raise HTTPException(409, "Stable shot code cannot change; create a new shot instead")
        current.code = input_row.code
        current.sort_index = index
        current.start_frame = input_row.start_frame
        current.duration_frames = input_row.duration_frames
        current.visual = input_row.visual
        current.narration = input_row.narration
        current.notes = input_row.notes
        current.art_key = input_row.art_key
        current.mood = input_row.mood
    if payload.next_shot_number < project.next_shot_number:
        raise HTTPException(409, "nextShotNumber cannot move backwards")
    project.next_shot_number = payload.next_shot_number
    touch(project)


def bootstrap(db: Session, project: m.Project, data: s.BootstrapData) -> None:
    if db.scalar(select(m.Shot.id).where(m.Shot.project_id == project.id).limit(1)) or db.scalar(select(m.Asset.id).where(m.Asset.project_id == project.id).limit(1)):
        raise HTTPException(409, "Project already contains production data; bootstrap is first-import only")
    assert_shot_graph(data.shots, data.shot_order)
    validate_next_shot_number(data.shots, data.next_shot_number)
    for key, asset in data.assets.items():
        if key != asset.id:
            raise HTTPException(422, "Asset record key must equal its stable id")
    if len({(x.shot_id, x.asset_id) for x in data.links}) != len(data.links):
        raise HTTPException(422, "Duplicate shot-asset link")
    for link in data.links:
        if link.shot_id not in data.shots or link.asset_id not in data.assets:
            raise HTTPException(422, "Link references missing shot or asset")
        if link.pinned_version > data.assets[link.asset_id].current_version:
            raise HTTPException(422, "Link references version not present on asset")
    db.add_all([
        m.Shot(id=row.id, project_id=project.id, code=row.code, sort_index=index,
               start_frame=row.start_frame, duration_frames=row.duration_frames,
               visual=row.visual, narration=row.narration, notes=row.notes,
               art_key=row.art_key, mood=row.mood)
        for index, key in enumerate(data.shot_order) for row in [data.shots[key]]
    ])
    db.add_all([
        m.Asset(id=row.id, project_id=project.id, name=row.name, category=row.category,
                status=row.status, current_version=row.current_version,
                color=row.color, shorthand=row.shorthand)
        for row in data.assets.values()
    ])
    db.flush()
    # BS-M1 only tracked a counter, not real files. Mark historical versions as
    # placeholders; do not invent SHA-256 hashes or file provenance.
    for row in data.assets.values():
        for n in range(1, row.current_version + 1):
            db.add(m.AssetVersion(asset_id=row.id, version=n,
                                  description="BS-M1 imported version marker (no verified file)",
                                  source="bs-m1-import"))
    db.flush()
    db.add_all([m.ShotAssetLink(shot_id=link.shot_id, asset_id=link.asset_id,
                                pinned_version=link.pinned_version) for link in data.links])
    project.next_shot_number = data.next_shot_number
    touch(project)
