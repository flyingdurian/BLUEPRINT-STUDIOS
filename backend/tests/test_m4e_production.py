from __future__ import annotations

import importlib.util
import json
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


def test_manifest_hash_mismatch_blocks_without_writing_final(tmp_path: Path):
    job = tmp_path / "job"
    job.mkdir()
    body = {"schemaVersion": "blueprint.render-manifest.v1", "quality": "previs", "shots": []}
    raw = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    (job / "render_manifest.json").write_bytes(raw)
    (job / "render_manifest.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    (job / "pilot-final.mp4").write_bytes(b"leave-me")
    qc = _qc()
    args = qc.argparse.Namespace(
        job_dir=job,
        stage_plan=ROOT / "docs" / "examples" / "BS-M4-PILOT-STAGE-PLAN.json",
        rig_contract=ROOT / "docs" / "examples" / "BS-M4E-RIG-CONTRACT.json",
        face_contract=ROOT / "docs" / "examples" / "BS-M4E-FACIAL-RIG.json",
        actions_contract=ROOT / "docs" / "examples" / "BS-M4E-ACTION-BINDINGS.json",
        lighting_contract=ROOT / "docs" / "examples" / "BS-M4E-D-LIGHTING-PROFILES-v2.json",
    )
    payload, code = qc.run_qc(args)
    assert code == 2
    assert any(item["code"] == "MANIFEST_HASH" and item["expected"] != item["actual"] for item in payload["findings"])
    assert payload["approvedForFinalPromotion"] is False
    assert (job / "pilot-final.mp4").read_bytes() == b"leave-me"


def test_contract_digest_codes_report_expected_and_actual():
    qc = _qc()
    report = qc.Report()
    qc.validate_contract_hashes(
        {
            "skeletonContractSha256": "a" * 64,
            "faceContractSha256": "b" * 64,
            "actionRegistrySha256": "c" * 64,
            "lightingContractSha256": "d" * 64,
        },
        {
            "rig": ROOT / "docs" / "examples" / "BS-M4E-RIG-CONTRACT.json",
            "face": ROOT / "docs" / "examples" / "BS-M4E-FACIAL-RIG.json",
            "actions": ROOT / "docs" / "examples" / "BS-M4E-ACTION-BINDINGS.json",
            "lighting": ROOT / "docs" / "examples" / "BS-M4E-D-LIGHTING-PROFILES-v2.json",
        },
        report,
    )
    codes = {item["code"] for item in report.findings}
    assert {"SKELETON_CONTRACT_SHA", "FACE_CONTRACT_SHA", "ACTION_REGISTRY_SHA", "LIGHTING_CONTRACT_SHA"} <= codes
    assert all("expected" in item and "actual" in item for item in report.findings)
