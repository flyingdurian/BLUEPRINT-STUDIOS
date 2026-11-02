from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.services.media_store import blob_file, relative_blob_path
from app.services.render_manifest import (
    ManifestCompileError, compile_render_manifest, default_plan_path,
)

PROJECT_ID = "blueprint-pilot-01"
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
ASSETS = {
    "ast-lead": ("Lead Character", "rig", "Tested & Ready", 1, "#c4a18a", "RIG"),
    "ast-aunt": ("Aunt Call Avatar", "rig", "Rigging", 2, "#c596bb", "AVT"),
    "ast-apartment": ("Apartment Nook", "environment", "Tested & Ready", 3, "#80979d", "ENV"),
    "ast-phone": ("Smartphone", "prop", "Tested & Ready", 2, "#6c9fbf", "PRP"),
    "ast-mug": ("Ceramic Tea Mug", "prop", "3D Modeling", 1, "#cda973", "PRP"),
    "ast-drawer": ("Side-table Drawer", "prop", "Concept", 1, "#a68e77", "PRP"),
    "ast-chat": ("Chat UI Kit", "graphic", "Tested & Ready", 2, "#82aea2", "GFX"),
    "ast-restaurant": ("Host Stand Cutaway", "environment", "Concept", 1, "#b98d9e", "ENV"),
    "ast-badge": ("Coordinator Badge", "graphic", "Concept", 1, "#dcaa70", "GFX"),
    "ast-vo": ("Narrator VO Scratch", "audio", "Concept", 1, "#aa9db9", "VO"),
}


def pilot_graph() -> dict:
    plan = json.loads(default_plan_path().read_text(encoding="utf-8"))
    shots = {}
    order = []
    links = []
    for planned in plan["shots"]:
        shot_id = planned["shotId"]
        order.append(shot_id)
        shots[shot_id] = {
            "id": shot_id, "code": planned["code"], "startFrame": planned["startFrame"],
            "durationFrames": planned["durationFrames"], "visual": planned.get("overlayCue") or "",
            "narration": planned["narration"], "notes": planned["code"], "artKey": planned["setKey"],
            "mood": planned["setKey"],
        }
        for asset_id in planned["linkedAssetIds"]:
            links.append({"shotId": shot_id, "assetId": asset_id, "pinnedVersion": ASSETS[asset_id][3]})
    assets = {
        asset_id: {
            "id": asset_id, "name": spec[0], "category": spec[1], "status": spec[2],
            "currentVersion": spec[3], "color": spec[4], "shorthand": spec[5],
        }
        for asset_id, spec in ASSETS.items()
    }
    return {"shots": shots, "shotOrder": order, "assets": assets, "links": links, "nextShotNumber": 15}


def seed(api) -> dict:
    created = api.post("/api/projects", json={"id": PROJECT_ID, "name": "Pilot 1", "fps": 30})
    assert created.status_code == 201, created.text
    imported = api.post(f"/api/projects/{PROJECT_ID}/bootstrap", json=pilot_graph())
    assert imported.status_code == 201, imported.text
    return imported.json()


def session_for(db_file: Path) -> Session:
    engine = create_engine("sqlite:///" + Path(db_file).as_posix())
    return Session(engine)


def write_blob(digest: str, payload: bytes) -> None:
    target = blob_file(digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def attach_phone(db_file: Path, digest: str, payload: bytes, *, version_path: str | None = None) -> None:
    write_blob(digest, payload)
    relative = relative_blob_path(digest)
    with sqlite3.connect(db_file) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO media_blobs (sha256, byte_size, media_type, relative_path) VALUES (?, ?, 'image/png', ?)",
            (digest, len(payload), relative),
        )
        connection.execute(
            "UPDATE asset_versions SET sha256=?, blob_sha256=?, relative_path=? WHERE asset_id='ast-phone' AND version=2",
            (digest, digest, version_path if version_path is not None else relative),
        )
        connection.commit()


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    monkeypatch.setenv("BLUEPRINT_RENDER_JOBS_ROOT", str(root))
    return root


def test_previs_proxy_freezes_fourteen_shot_manifest(client, jobs):
    api, _ = client
    seed(api)
    denied = api.post(f"/api/projects/{PROJECT_ID}/render-manifests", json={"quality": "previs", "allowProxy": False})
    assert denied.status_code == 422, denied.text
    created = api.post(f"/api/projects/{PROJECT_ID}/render-manifests", json={"quality": "previs", "allowProxy": True})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["frameCount"] == 2490
    assert body["shotCount"] == 14
    assert body["unresolvedCount"] > 0
    assert body["standIn"] is True
    manifest_path = jobs / body["jobId"] / "render_manifest.json"
    encoded = manifest_path.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == (jobs / body["jobId"] / "render_manifest.sha256").read_text(encoding="utf-8").strip()
    manifest = json.loads(encoded)
    assert [shot["code"] for shot in manifest["shots"]][0] == "SH_001"
    assert manifest["shots"][-1]["endFrameExclusive"] == 2490
    assert manifest["shots"][0]["performance"]["execute"] is False
    assets = [asset for shot in manifest["shots"] for asset in shot["assets"]]
    assert assets
    assert all(asset["sha256"] is None and asset["resolution"] == "UNRESOLVED_PROXY" and asset["verified"] is False for asset in assets)
    stand_in = jobs / body["jobId"] / manifest["standIn"]["relativePath"]
    assert hashlib.sha256(stand_in.read_bytes()).hexdigest() == manifest["standIn"]["sha256"]
    assert not (jobs / body["jobId"] / "pilot-previs.ogv").exists()


def test_compile_does_not_change_pins_or_revision(client, jobs):
    api, _ = client
    before = seed(api)
    created = api.post(f"/api/projects/{PROJECT_ID}/render-manifests", json={"quality": "previs", "allowProxy": True})
    assert created.status_code == 201, created.text
    after = api.get(f"/api/projects/{PROJECT_ID}/snapshot").json()
    assert after["revision"] == before["revision"]
    assert after["links"] == before["links"]
    assert after["assets"]["ast-phone"]["currentVersion"] == before["assets"]["ast-phone"]["currentVersion"]


def test_verified_blob_is_staged_and_rehashed(client, jobs):
    api, db_file = client
    seed(api)
    digest = hashlib.sha256(PNG).hexdigest()
    attach_phone(db_file, digest, PNG)
    with session_for(db_file) as db:
        result = compile_render_manifest(db, PROJECT_ID, quality="previs", allow_proxy=True, jobs_root=jobs)
    manifest = json.loads(Path(result["manifest_path"]).read_bytes())
    phone = next(asset for shot in manifest["shots"] for asset in shot["assets"] if asset["assetId"] == "ast-phone")
    assert phone["verified"] is True
    assert phone["sha256"] == digest
    assert phone["pinnedVersion"] == 2
    staged = jobs / result["job_id"] / phone["relativePath"]
    assert hashlib.sha256(staged.read_bytes()).hexdigest() == digest
    others = [asset for shot in manifest["shots"] for asset in shot["assets"] if asset["assetId"] != "ast-phone"]
    assert all(asset["resolution"] == "UNRESOLVED_PROXY" and asset["sha256"] is None for asset in others)


def test_digest_mismatch_fails_closed(client, jobs):
    api, db_file = client
    seed(api)
    claimed = "ab" * 32
    attach_phone(db_file, claimed, PNG)
    with session_for(db_file) as db:
        with pytest.raises(ManifestCompileError, match="does not match its bytes"):
            compile_render_manifest(db, PROJECT_ID, quality="previs", allow_proxy=True, jobs_root=jobs)
    assert list(jobs.glob("*")) == []


def test_external_path_fails_even_with_proxy(client, jobs):
    api, db_file = client
    seed(api)
    with sqlite3.connect(db_file) as connection:
        connection.execute(
            "UPDATE asset_versions SET relative_path=? WHERE asset_id='ast-phone' AND version=2",
            ("C:/Windows/notepad.exe",),
        )
        connection.commit()
    with session_for(db_file) as db:
        with pytest.raises(ManifestCompileError, match="escapes the media library"):
            compile_render_manifest(db, PROJECT_ID, quality="previs", allow_proxy=True, jobs_root=jobs)


def test_plan_and_pin_mismatch_fails(client, jobs, tmp_path):
    api, db_file = client
    seed(api)
    plan = json.loads(default_plan_path().read_text(encoding="utf-8"))
    plan["shots"][0]["linkedAssetIds"] = ["ast-lead"]
    broken = tmp_path / "mismatch.json"
    broken.write_text(json.dumps(plan), encoding="utf-8")
    with session_for(db_file) as db:
        with pytest.raises(ManifestCompileError, match="pins do not match"):
            compile_render_manifest(db, PROJECT_ID, quality="previs", allow_proxy=True, plan_path=broken, jobs_root=jobs)


def test_production_quality_is_blocked(client, jobs):
    api, _ = client
    seed(api)
    response = api.post(f"/api/projects/{PROJECT_ID}/render-manifests", json={"quality": "production", "allowProxy": True})
    assert response.status_code == 422, response.text
    assert "DRAFT_UNMAPPED" in response.text
    assert "M4-D/E" in response.text
    assert list(jobs.glob("*")) == []


def test_overlapping_stage_plan_fails(client, jobs, tmp_path):
    api, db_file = client
    seed(api)
    plan = json.loads(default_plan_path().read_text(encoding="utf-8"))
    plan["shots"][1]["startFrame"] = 0
    overlap = tmp_path / "overlap.json"
    overlap.write_text(json.dumps(plan), encoding="utf-8")
    with session_for(db_file) as db:
        with pytest.raises(ManifestCompileError, match="overlap|gap|duration"):
            compile_render_manifest(db, PROJECT_ID, quality="previs", allow_proxy=True, plan_path=overlap, jobs_root=jobs)


def test_compile_endpoint_returns_job_without_rendering(client, jobs):
    api, _ = client
    seed(api)
    first = api.post(f"/api/projects/{PROJECT_ID}/render-manifests", json={"quality": "previs", "allowProxy": True})
    second = api.post(f"/api/projects/{PROJECT_ID}/render-manifests", json={"quality": "previs", "allowProxy": True})
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["jobId"] != second.json()["jobId"]
    assert len(list(jobs.iterdir())) == 2
    for body in (first.json(), second.json()):
        assert body["manifestSha256"]
        assert (jobs / body["jobId"] / "render_manifest.json").is_file()
        assert not (jobs / body["jobId"] / "pilot-previs.ogv").exists()
