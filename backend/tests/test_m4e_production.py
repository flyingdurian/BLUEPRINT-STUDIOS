from __future__ import annotations

import importlib.util
import json
import wave
from pathlib import Path

from app.services.render_manifest import production_manifest_blockers

ROOT = Path(__file__).resolve().parents[2]


def _qc():
    path = ROOT / "tools" / "qc_production_render.py"
    spec = importlib.util.spec_from_file_location("qc_production_render", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_production_blockers_name_unresolved_rig_face_actions_and_light():
    plan = json.loads((ROOT / "docs" / "examples" / "BS-M4-PILOT-STAGE-PLAN.json").read_text(encoding="utf-8"))
    blockers = production_manifest_blockers(plan, resolved=[])
    text = "\n".join(blockers)
    assert "40-bone rig is an unapproved dummy" in text
    assert "22 facial blend shapes are not imported" in text
    assert "34 action mappings are unresolved registry names" in text
    assert "LOOKDEV_PROVISIONAL_NOT_APPROVED" in text
    assert "no verified protagonist GLB is pinned" in text
    assert "Forward+" in text


def test_qc_refuses_previs_and_does_not_write_final(tmp_path: Path):
    job = tmp_path / "job"
    job.mkdir()
    manifest = {
        "quality": "previs",
        "productionLocked": False,
        "fps": 30,
        "totalFrames": 2490,
        "shots": [],
    }
    (job / "render_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (job / "pilot-final.mp4").write_bytes(b"leave-me")
    before = {path.name: path.read_bytes() for path in job.iterdir()}
    report = _qc().inspect_candidate(job)
    after = {path.name: path.read_bytes() for path in job.iterdir()}
    assert report["encodeFinal"] is False
    assert any("pilot-final.mp4" in error for error in report["errors"])
    assert any("Unassigned material" in error for error in report["errors"])
    assert before == after


def test_qc_reports_short_narration_against_the_2490_frame_picture(tmp_path: Path):
    job = tmp_path / "production-job"
    job.mkdir()
    manifest = {
        "quality": "production",
        "productionLocked": True,
        "fps": 30,
        "totalFrames": 2490,
        "shots": [
            {"code": f"SH_{index:03d}", "startFrame": (index - 1) * 120, "endFrameExclusive": index * 120}
            for index in range(1, 15)
        ],
    }
    # The real pilot is not 14 equal 120-frame shots. This fixture only checks the audio gate.
    manifest["shots"][-1]["endFrameExclusive"] = 2490
    (job / "render_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    mix = job / "narration_mix.wav"
    with wave.open(str(mix), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        handle.writeframes(b"\x00\x00" * 480)
    report = _qc().inspect_candidate(job)
    assert report["encodeFinal"] is False
    assert any("Narration mix" in error for error in report["errors"])
    assert not (job / "pilot-final.mp4").exists()
