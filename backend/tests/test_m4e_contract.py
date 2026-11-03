from __future__ import annotations

import json
from pathlib import Path

from app.services.production_stage_validation import (
    production_blockers,
    validate_design,
    validate_godot_structure,
    validate_scene_text,
)

ROOT = Path(__file__).resolve().parents[2]


def test_design_and_godot_harness_match_and_art_stays_blocked():
    plan = json.loads((ROOT / "docs" / "examples" / "BS-M4-PILOT-STAGE-PLAN.json").read_text(encoding="utf-8"))
    examples = ROOT / "docs" / "examples"
    rig = json.loads((examples / "BS-M4E-RIG-CONTRACT.json").read_text(encoding="utf-8"))
    assert validate_design(plan, examples) == []
    assert validate_godot_structure(ROOT / "godot_render", rig) == []
    blockers = production_blockers(ROOT / "godot_render")
    assert any("GLB" in blocker for blocker in blockers)
    assert any("action" in blocker.lower() for blocker in blockers)


def test_wrong_socket_bone_fails_closed():
    rig = {"requiredBones": ["Root", "Hand_R", "Hand_L"]}
    scene = """
[node name="CharacterRoot" type="Node3D"]
[node name="Skeleton3D" type="Skeleton3D" parent="CharacterRoot"]
bones/0/name = "Root"
bones/0/scale = Vector3(1, 1, 1)
bones/1/name = "Hand_R"
bones/1/scale = Vector3(1, 1, 1)
bones/2/name = "Hand_L"
bones/2/scale = Vector3(1, 1, 1)
[node name="phone_grip_r" type="BoneAttachment3D" parent="CharacterRoot/Skeleton3D"]
bone_name = "Hand_L"
[node name="AnimationPlayer" type="AnimationPlayer"]
[node name="BodyMesh" type="MeshInstance3D"]
[node name="FaceMesh" type="MeshInstance3D"]
"""
    errors = validate_scene_text(scene, rig)
    assert any("phone_grip_r must be a BoneAttachment3D bound to Hand_R" in error for error in errors)
