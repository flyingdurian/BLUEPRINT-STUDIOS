from __future__ import annotations

import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.main import create_app


def create_project(client: TestClient, name="Organizer") -> str:
    response = client.post("/api/projects", json={"name": name, "fps": 30})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_sqlite_wal_foreign_keys_and_tables(client):
    _, db_file = client
    with sqlite3.connect(db_file) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert {x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} >= {
            "projects", "shots", "assets", "asset_versions", "shot_asset_links", "storyboards"
        }
    assert client[0].get("/api/health").json()["status"] == "ok"


def test_bs_m1_bootstrap_roundtrip(client, pilot):
    c, _ = client
    pid = create_project(c)
    res = c.post(f"/api/projects/{pid}/bootstrap", json=pilot)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["revision"] == 1
    for field in ("shots", "shotOrder", "assets", "links", "nextShotNumber"):
        assert data[field] == pilot[field]
    assert c.get(f"/api/projects/{pid}/snapshot").json()["shotOrder"] == ["shot-001", "shot-002"]
    assert c.post(f"/api/projects/{pid}/bootstrap", json=pilot).status_code == 409
    versions = c.get(f"/api/projects/{pid}/assets/ast-phone/versions").json()
    assert [x["version"] for x in versions] == [1, 2]
    assert all(x["source"] == "bs-m1-import" and x["sha256"] is None for x in versions)


def test_shot_update_and_stale_revision(client, pilot):
    c, _ = client
    pid = create_project(c)
    c.post(f"/api/projects/{pid}/bootstrap", json=pilot)
    url = f"/api/projects/{pid}/shots/shot-001"
    assert c.patch(url, json={"visual": "Revised", "expectedRevision": 0}).status_code == 409
    res = c.patch(url, json={"visual": "Revised", "expectedRevision": 1})
    assert res.status_code == 200, res.text
    assert res.json()["visual"] == "Revised"
    assert c.get(f"/api/projects/{pid}/snapshot").json()["revision"] == 2
    assert c.patch(url, json={"durationFrames": 0}).status_code == 422


def test_shot_graph_sync_and_conflict(client, pilot):
    c, _ = client
    pid = create_project(c)
    c.post(f"/api/projects/{pid}/bootstrap", json=pilot)
    swapped = {"expectedRevision": 1, "shots": pilot["shots"],
               "shotOrder": ["shot-001", "shot-002"], "nextShotNumber": 4}
    swapped["shots"] = dict(pilot["shots"])
    swapped["shots"]["shot-002"] = {**pilot["shots"]["shot-002"], "narration": "Revised narration."}
    response = c.put(f"/api/projects/{pid}/shots/sync", json=swapped)
    assert response.status_code == 200, response.text
    assert response.json()["shots"]["shot-002"]["narration"] == "Revised narration."
    assert c.put(f"/api/projects/{pid}/shots/sync", json=swapped).status_code == 409
    invalid = {**swapped, "expectedRevision": 2, "shotOrder": ["shot-001"]}
    assert c.put(f"/api/projects/{pid}/shots/sync", json=invalid).status_code == 422
    assert c.get(f"/api/projects/{pid}/snapshot").json()["revision"] == 2


def test_asset_versions_preserve_pinned_links(client, pilot):
    c, _ = client
    pid = create_project(c)
    c.post(f"/api/projects/{pid}/bootstrap", json=pilot)
    version_url = f"/api/projects/{pid}/assets/ast-phone/versions"
    res = c.post(version_url, json={"expectedRevision": 1,
              "sha256": "a" * 64, "relativePath": "assets/phone/v3.png", "description": "Retopology"})
    assert res.status_code == 201, res.text
    assert res.json()["version"] == 3
    snapshot = c.get(f"/api/projects/{pid}/snapshot").json()
    assert snapshot["assets"]["ast-phone"]["currentVersion"] == 3
    assert snapshot["links"][0]["pinnedVersion"] == 1  # no silent update
    url = f"/api/projects/{pid}/shots/shot-001/assets/ast-phone"
    assert c.put(url, json={"pinnedVersion": 50}).status_code == 422
    assert c.put(url, json={"pinnedVersion": 3, "expectedRevision": 2}).json()["pinnedVersion"] == 3
    assert c.get(f"/api/projects/{pid}/snapshot").json()["links"][0]["pinnedVersion"] == 3
    assert c.post(version_url, json={"relativePath": "../../secret.png"}).status_code == 422
    assert len(c.get(version_url).json()) == 3


def test_assets_and_storyboard_project_scoping(client, pilot):
    c, _ = client
    p1 = create_project(c)
    p2 = create_project(c, "Other")
    c.post(f"/api/projects/{p1}/bootstrap", json=pilot)
    assert c.patch(f"/api/projects/{p2}/assets/ast-phone", json={"status": "Rigging"}).status_code == 404
    assert c.put(f"/api/projects/{p2}/shots/shot-001/assets/ast-phone", json={}).status_code == 404
    asset = c.post(f"/api/projects/{p1}/assets", json={"name": "Lamp", "category": "prop"})
    assert asset.status_code == 201, asset.text
    assert c.patch(f"/api/projects/{p1}/assets/{asset.json()['id']}", json={"status": "Rigging"}).json()["status"] == "Rigging"
    url = f"/api/projects/{p1}/storyboards"
    r = c.post(url, json={"shotId": "shot-001", "cropMode": "9:16", "notes": "Opening still"})
    assert r.status_code == 201, r.text
    assert c.get(url).json()[0]["notes"] == "Opening still"
    assert c.post(url, json={"shotId": "shot-001", "assetId": "ast-phone", "assetVersion": 100}).status_code == 422


def test_bootstrap_rolls_back_atomically_on_bad_link(client, pilot):
    c, _ = client
    pid = create_project(c)
    bad = {**pilot, "links": [{"shotId": "shot-001", "assetId": "ast-phone", "pinnedVersion": 999}]}
    assert c.post(f"/api/projects/{pid}/bootstrap", json=bad).status_code == 422
    state = c.get(f"/api/projects/{pid}/snapshot").json()
    assert state["shots"] == {}
    assert state["assets"] == {}
    assert state["revision"] == 0


def test_persistence_after_app_restarts(tmp_path, pilot):
    url = "sqlite:///" + str(tmp_path / "restart.sqlite3")
    with TestClient(create_app(url)) as c:
        pid = create_project(c)
        assert c.post(f"/api/projects/{pid}/bootstrap", json=pilot).status_code == 201
    with TestClient(create_app(url)) as c:
        snapshot = c.get(f"/api/projects/{pid}/snapshot")
        assert snapshot.status_code == 200
        assert len(snapshot.json()["shots"]) == 2


def test_reject_bad_next_shot_number_and_overlapping_patch(client, pilot):
    c, _ = client
    pid = create_project(c)
    invalid = {**pilot, "nextShotNumber": 2}
    assert c.post(f"/api/projects/{pid}/bootstrap", json=invalid).status_code == 422
    assert c.post(f"/api/projects/{pid}/bootstrap", json=pilot).status_code == 201
    assert c.patch(f"/api/projects/{pid}/shots/shot-001", json={"durationFrames": 200}).status_code == 422
    snap = c.get(f"/api/projects/{pid}/snapshot").json()
    assert snap["shots"]["shot-001"]["durationFrames"] == 120
    assert snap["revision"] == 1


def test_deleting_shot_via_sync_cascades_link(client, pilot):
    c, _ = client
    pid = create_project(c)
    assert c.post(f"/api/projects/{pid}/bootstrap", json=pilot).status_code == 201
    subset = {"expectedRevision": 1, "shots": {"shot-002": pilot["shots"]["shot-002"]},
              "shotOrder": ["shot-002"], "nextShotNumber": 3}
    response = c.put(f"/api/projects/{pid}/shots/sync", json=subset)
    assert response.status_code == 200, response.text
    assert response.json()["links"] == []


def test_storyboard_path_sanitization(client, pilot):
    c, _ = client
    pid = create_project(c)
    assert c.post(f"/api/projects/{pid}/bootstrap", json=pilot).status_code == 201
    url = f"/api/projects/{pid}/storyboards"
    assert c.post(url, json={"shotId": "shot-001", "mediaPath": "../outside.png"}).status_code == 422
    assert c.post(url, json={"shotId": "shot-001", "mediaPath": "frames/storyboard.png"}).status_code == 201


def test_storyboard_put_delete_and_revision(client, pilot):
    c, _ = client
    pid = create_project(c)
    other = create_project(c, "Other")
    assert c.post(f"/api/projects/{pid}/bootstrap", json=pilot).status_code == 201
    url = f"/api/projects/{pid}/storyboards"
    created = c.post(url, json={"id": "board-1", "shotId": "shot-001", "notes": "Opening still"})
    assert created.status_code == 201, created.text
    assert c.get(f"/api/projects/{pid}/snapshot").json()["revision"] == 2
    stale = c.put(f"{url}/board-1", json={"shotId": "shot-001", "notes": "Nope", "expectedRevision": 1})
    assert stale.status_code == 409
    assert c.get(url).json()[0]["notes"] == "Opening still"
    updated = c.put(f"{url}/board-1", json={
        "shotId": "shot-002", "cropMode": "16:9", "notes": "Revised", "sortIndex": 2,
        "mediaPath": "frames/board.png", "expectedRevision": 2,
    })
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["shotId"] == "shot-002"
    assert body["notes"] == "Revised"
    assert body["mediaPath"] == "frames/board.png"
    assert c.put(f"/api/projects/{other}/storyboards/board-1", json={"shotId": "shot-001", "notes": "x"}).status_code == 404
    assert c.get(f"/api/projects/{pid}/snapshot").json()["revision"] == 3
    assert c.delete(f"{url}/board-1?expectedRevision=2").status_code == 409
    assert c.delete(f"{url}/board-1?expectedRevision=3").status_code == 204
    assert c.get(url).json() == []
    assert c.delete(f"{url}/board-1").status_code == 404


def test_sync_batch_is_atomic_and_single_revision(client, pilot):
    c, _ = client
    pid = create_project(c)
    assert c.post(f"/api/projects/{pid}/bootstrap", json=pilot).status_code == 201
    shots = {**pilot["shots"], "shot-002": {**pilot["shots"]["shot-002"], "narration": "Batch narration."}}
    ok = c.post(f"/api/projects/{pid}/sync-batch", json={
        "expectedRevision": 1,
        "mutations": [
            {"op": "update_asset", "assetId": "ast-mug", "status": "Rigging"},
            {"op": "sync_shots", "shots": shots, "shotOrder": pilot["shotOrder"], "nextShotNumber": pilot["nextShotNumber"]},
            {"op": "create_storyboard", "storyboard": {"id": "board-9", "shotId": "shot-001", "notes": "Batch still"}},
        ],
    })
    assert ok.status_code == 200, ok.text
    payload = ok.json()
    assert payload["snapshot"]["revision"] == 2
    assert payload["snapshot"]["shots"]["shot-002"]["narration"] == "Batch narration."
    assert payload["snapshot"]["assets"]["ast-mug"]["status"] == "Rigging"
    assert payload["storyboards"][0]["id"] == "board-9"
    assert payload["storyboards"][0]["notes"] == "Batch still"
    bad_shots = {**shots, "shot-001": {**shots["shot-001"], "narration": "Should roll back"}}
    bad = c.post(f"/api/projects/{pid}/sync-batch", json={
        "expectedRevision": 2,
        "mutations": [
            {"op": "sync_shots", "shots": bad_shots, "shotOrder": pilot["shotOrder"], "nextShotNumber": pilot["nextShotNumber"]},
            {"op": "create_storyboard", "storyboard": {"shotId": "shot-001", "assetId": "ast-phone", "assetVersion": 999}},
        ],
    })
    assert bad.status_code == 422, bad.text
    snap = c.get(f"/api/projects/{pid}/snapshot").json()
    assert snap["revision"] == 2
    assert snap["shots"]["shot-001"]["narration"] == pilot["shots"]["shot-001"]["narration"]
    assert snap["shots"]["shot-002"]["narration"] == "Batch narration."
    assert c.get(f"/api/projects/{pid}/storyboards").json()[0]["notes"] == "Batch still"
    stale = c.post(f"/api/projects/{pid}/sync-batch", json={
        "expectedRevision": 1,
        "mutations": [{"op": "delete_storyboard", "storyboardId": "board-9"}],
    })
    assert stale.status_code == 409
    assert c.get(f"/api/projects/{pid}/storyboards").json()[0]["id"] == "board-9"
    assert c.post(f"/api/projects/{pid}/sync-batch", json={"expectedRevision": 2, "mutations": []}).status_code == 422
