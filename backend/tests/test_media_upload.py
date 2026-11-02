from __future__ import annotations

import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.db import init_database
from app.main import create_app
from app.services.media_store import StagedUpload, blob_file, media_root, stage_upload


PNG = b"\x89PNG\r\n\x1a\nblueprint-media"


class ChunkedUpload:
    def __init__(self, payload: bytes, content_type: str = "image/png"):
        self.payload = payload
        self.content_type = content_type
        self.offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self.payload[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


def upload(client: TestClient, project_id: str, asset_id: str, payload: bytes = PNG, **extra):
    files = {"file": ("frame.png", payload, extra.pop("content_type", "image/png"))}
    return client.post(f"/api/projects/{project_id}/assets/{asset_id}/versions/upload", files=files, **extra)


def test_chunked_hash_does_not_require_the_whole_file(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_MEDIA_ROOT", str(tmp_path / "media"))
    staged = pytest.importorskip("asyncio").run(stage_upload(ChunkedUpload(b"abcdefghij" * 5), chunk_size=8))
    try:
        assert staged.byte_size == 50
        assert staged.sha256 == hashlib.sha256(b"abcdefghij" * 5).hexdigest()
        assert staged.path.is_file()
    finally:
        staged.path.unlink(missing_ok=True)


def test_migration_keeps_existing_versions_and_pins(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_MEDIA_ROOT", str(tmp_path / "media"))
    db_file = tmp_path / "legacy.sqlite3"
    engine = create_engine("sqlite:///" + db_file.as_posix())
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE projects (
                id VARCHAR(80) PRIMARY KEY, name VARCHAR(200) NOT NULL, fps INTEGER NOT NULL,
                revision INTEGER NOT NULL, next_shot_number INTEGER NOT NULL, created_at DATETIME
            )
        """))
        connection.execute(text("""
            CREATE TABLE assets (
                id VARCHAR(100) PRIMARY KEY, project_id VARCHAR(80) NOT NULL, name VARCHAR(200) NOT NULL,
                category VARCHAR(30) NOT NULL, status VARCHAR(40) NOT NULL, current_version INTEGER NOT NULL,
                color VARCHAR(32) NOT NULL, shorthand VARCHAR(30) NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE shots (
                id VARCHAR(100) PRIMARY KEY, project_id VARCHAR(80) NOT NULL, code VARCHAR(50) NOT NULL,
                sort_index INTEGER NOT NULL, start_frame INTEGER NOT NULL, duration_frames INTEGER NOT NULL,
                visual TEXT NOT NULL, narration TEXT NOT NULL, notes TEXT NOT NULL, art_key VARCHAR(120) NOT NULL,
                mood VARCHAR(120) NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE asset_versions (
                asset_id VARCHAR(100) NOT NULL, version INTEGER NOT NULL, sha256 VARCHAR(64),
                relative_path TEXT, description TEXT NOT NULL, source VARCHAR(32) NOT NULL, created_at DATETIME,
                PRIMARY KEY (asset_id, version)
            )
        """))
        connection.execute(text("""
            CREATE TABLE shot_asset_links (
                shot_id VARCHAR(100) NOT NULL, asset_id VARCHAR(100) NOT NULL, pinned_version INTEGER NOT NULL,
                PRIMARY KEY (shot_id, asset_id)
            )
        """))
        connection.execute(text("INSERT INTO projects VALUES ('p', 'Pilot', 30, 4, 15, NULL)"))
        connection.execute(text("INSERT INTO shots VALUES ('shot-001', 'p', 'SH_001', 0, 0, 120, 'v', 'n', 'notes', 'phone', 'relief')"))
        connection.execute(text("INSERT INTO assets VALUES ('ast-phone', 'p', 'Smartphone', 'prop', 'Tested & Ready', 2, '#6c9fbf', 'PRP')"))
        connection.execute(text("INSERT INTO asset_versions VALUES ('ast-phone', 1, NULL, 'legacy/phone.png', 'imported', 'bs-m1-import', NULL)"))
        connection.execute(text("INSERT INTO asset_versions VALUES ('ast-phone', 2, NULL, NULL, 'marker', 'bs-m1-import', NULL)"))
        connection.execute(text("INSERT INTO shot_asset_links VALUES ('shot-001', 'ast-phone', 1)"))
    init_database(engine)
    with engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(asset_versions)"))}
        assert "blob_sha256" in columns
        versions = connection.execute(text(
            "SELECT version, relative_path, blob_sha256, source FROM asset_versions ORDER BY version"
        )).all()
        assert versions == [(1, "legacy/phone.png", None, "bs-m1-import"), (2, None, None, "bs-m1-import")]
        assert connection.execute(text("SELECT pinned_version FROM shot_asset_links")).scalar() == 1
        assert connection.execute(text("SELECT revision, next_shot_number FROM projects")).one() == (4, 15)
        assert connection.execute(text("SELECT version FROM schema_migrations")).scalar() == "m3a-media-blobs"
        assert connection.execute(text("SELECT name FROM sqlite_master WHERE name = 'media_blobs'")).scalar() == "media_blobs"
    init_database(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM asset_versions")).scalar() == 2


def test_upload_hashes_stores_and_leaves_pins_unchanged(client, pilot):
    api, _ = client
    project_id = api.post("/api/projects", json={"name": "Organizer", "fps": 30}).json()["id"]
    assert api.post(f"/api/projects/{project_id}/bootstrap", json=pilot).status_code == 201
    first = upload(api, project_id, "ast-phone", data={"expectedRevision": "1", "description": "Retake"})
    assert first.status_code == 201, first.text
    body = first.json()
    digest = hashlib.sha256(PNG).hexdigest()
    assert body["sha256"] == digest
    assert body["version"] == 3
    assert body["source"] == "upload"
    assert body["revision"] == 2
    assert body["relativePath"] == f"{digest[:2]}/{digest[2:4]}/{digest}"
    stored = blob_file(digest).read_bytes()
    assert stored == PNG
    assert blob_file(digest).parent == media_root() / digest[:2] / digest[2:4]
    snapshot = api.get(f"/api/projects/{project_id}/snapshot").json()
    assert snapshot["assets"]["ast-phone"]["currentVersion"] == 3
    assert snapshot["assets"]["ast-phone"]["status"] == "Tested & Ready"
    assert snapshot["links"][0]["pinnedVersion"] == 1
    second = upload(api, project_id, "ast-phone", data={"expectedRevision": "2"})
    assert second.status_code == 201, second.text
    assert second.json()["version"] == 4
    assert second.json()["sha256"] == digest
    assert list(media_root().rglob(digest)) == [blob_file(digest)]
    history = api.get(f"/api/projects/{project_id}/assets/ast-phone/versions").json()
    assert [item["version"] for item in history] == [1, 2, 3, 4]
    assert history[0]["source"] == "bs-m1-import"


def test_idempotent_replay_does_not_publish_another_version(client, pilot):
    api, _ = client
    project_id = api.post("/api/projects", json={"name": "Organizer", "fps": 30}).json()["id"]
    api.post(f"/api/projects/{project_id}/bootstrap", json=pilot)
    headers = {"Idempotency-Key": "upload-001"}
    created = upload(api, project_id, "ast-phone", data={"expectedRevision": "1"}, headers=headers)
    assert created.status_code == 201, created.text
    replay = upload(api, project_id, "ast-phone", data={"expectedRevision": "99"}, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["version"] == created.json()["version"]
    assert replay.json()["revision"] == created.json()["revision"]
    conflict = upload(api, project_id, "ast-phone", payload=PNG + b"x", data={"expectedRevision": "2"}, headers=headers)
    assert conflict.status_code == 409
    assert api.get(f"/api/projects/{project_id}/snapshot").json()["revision"] == 2


def test_upload_rejects_stale_revision_oversize_type_and_empty(client, pilot, monkeypatch):
    api, _ = client
    project_id = api.post("/api/projects", json={"name": "Organizer", "fps": 30}).json()["id"]
    api.post(f"/api/projects/{project_id}/bootstrap", json=pilot)
    stale = upload(api, project_id, "ast-phone", data={"expectedRevision": "0"})
    assert stale.status_code == 409
    assert api.get(f"/api/projects/{project_id}/assets/ast-phone/versions").json()[-1]["version"] == 2
    empty = upload(api, project_id, "ast-phone", payload=b"", data={"expectedRevision": "1"})
    assert empty.status_code == 422
    rejected = upload(api, project_id, "ast-phone", content_type="text/html", data={"expectedRevision": "1"})
    assert rejected.status_code == 415
    monkeypatch.setenv("BLUEPRINT_MAX_UPLOAD_BYTES", "8")
    too_big = upload(api, project_id, "ast-phone", data={"expectedRevision": "1"})
    assert too_big.status_code == 413
    assert api.get(f"/api/projects/{project_id}/snapshot").json()["revision"] == 1


def test_existing_digest_path_is_not_overwritten(client, pilot):
    api, _ = client
    project_id = api.post("/api/projects", json={"name": "Organizer", "fps": 30}).json()["id"]
    api.post(f"/api/projects/{project_id}/bootstrap", json=pilot)
    digest = hashlib.sha256(PNG).hexdigest()
    target = blob_file(digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"not-the-real-bytes")
    response = upload(api, project_id, "ast-phone", data={"expectedRevision": "1"})
    assert response.status_code == 409
    assert target.read_bytes() == b"not-the-real-bytes"
    assert api.get(f"/api/projects/{project_id}/assets/ast-phone/versions").json()[-1]["version"] == 2


def test_crash_before_commit_publishes_nothing_and_retry_reuses_blob(client, pilot, monkeypatch):
    api, _ = client
    project_id = api.post("/api/projects", json={"name": "Organizer", "fps": 30}).json()["id"]
    api.post(f"/api/projects/{project_id}/bootstrap", json=pilot)
    import app.api.uploads as uploads

    def explode(*_args, **_kwargs):
        raise RuntimeError("crash before commit")

    original = uploads.register_upload
    monkeypatch.setattr(uploads, "register_upload", explode)
    with pytest.raises(RuntimeError, match="crash before commit"):
        upload(api, project_id, "ast-phone", data={"expectedRevision": "1"})
    digest = hashlib.sha256(PNG).hexdigest()
    assert blob_file(digest).read_bytes() == PNG
    assert api.get(f"/api/projects/{project_id}/assets/ast-phone/versions").json()[-1]["version"] == 2
    monkeypatch.setattr(uploads, "register_upload", original)
    retried = upload(api, project_id, "ast-phone", data={"expectedRevision": "1"})
    assert retried.status_code == 201, retried.text
    assert retried.json()["sha256"] == digest
    assert list(media_root().rglob(digest)) == [blob_file(digest)]


def test_schema_migration_is_visible_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_MEDIA_ROOT", str(tmp_path / "media"))
    url = "sqlite:///" + (tmp_path / "fresh.sqlite3").as_posix()
    with TestClient(create_app(url)) as api:
        assert api.get("/api/health").status_code == 200
    with sqlite3.connect(tmp_path / "fresh.sqlite3") as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"media_blobs", "upload_receipts", "schema_migrations"} <= tables
        version_columns = {row[1] for row in conn.execute("PRAGMA table_info(asset_versions)")}
        assert "blob_sha256" in version_columns


def test_place_blob_reuses_matching_file(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_MEDIA_ROOT", str(tmp_path / "media"))
    staged = pytest.importorskip("asyncio").run(stage_upload(ChunkedUpload(PNG), chunk_size=4))
    from app.services.media_store import place_blob

    first = place_blob(staged)
    again = pytest.importorskip("asyncio").run(stage_upload(ChunkedUpload(PNG), chunk_size=4))
    second = place_blob(StagedUpload(again.path, again.sha256, again.byte_size, again.media_type))
    assert first == second
    assert blob_file(again.sha256).read_bytes() == PNG
