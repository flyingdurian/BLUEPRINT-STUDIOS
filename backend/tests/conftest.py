from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_MEDIA_ROOT", str(tmp_path / "media"))
    db_file = tmp_path / "director.sqlite3"
    application = create_app("sqlite:///" + db_file.as_posix())
    with TestClient(application) as test_client:
        yield test_client, db_file


@pytest.fixture
def pilot():
    shots = {
        "shot-001": {
            "id": "shot-001", "code": "SH_001", "startFrame": 0,
            "durationFrames": 120, "visual": "@Smartphone muted", "narration": "You mute the chat.",
            "notes": "Opening", "artKey": "phone", "mood": "relief",
        },
        "shot-002": {
            "id": "shot-002", "code": "SH_002", "startFrame": 120,
            "durationFrames": 150, "visual": "Sip of tea", "narration": "You sip tea.",
            "notes": "False peace", "artKey": "mug", "mood": "calm",
        },
    }
    assets = {
        "ast-phone": {
            "id": "ast-phone", "name": "Smartphone", "category": "prop", "status": "Tested & Ready",
            "currentVersion": 2, "color": "#6c9fbf", "shorthand": "PRP",
        },
        "ast-mug": {
            "id": "ast-mug", "name": "Ceramic Tea Mug", "category": "prop", "status": "Concept",
            "currentVersion": 1, "color": "#cda973", "shorthand": "PRP",
        },
    }
    return {"shots": shots, "shotOrder": list(shots), "assets": assets,
            "links": [{"shotId": "shot-001", "assetId": "ast-phone", "pinnedVersion": 1}],
            "nextShotNumber": 3}
