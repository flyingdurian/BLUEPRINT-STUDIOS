#!/usr/bin/env python3
"""Schema, cue, and Godot-source validation for M4E-C + M4E-D.

Checks the JSON contracts, the markdown channel and lighting names, and the
production Godot face and lighting files. Does not import a real .glb, render
frames, or record owner art acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "docs" / "examples"
GODOT = ROOT / "godot_render"
DOCS = ROOT / "docs"
NAMES = [
    "BrowInnerUp", "BrowOuterUp_L", "BrowOuterUp_R", "BrowDown_L", "BrowDown_R",
    "EyeWide_L", "EyeWide_R", "EyeSquint_L", "EyeSquint_R", "LidClose_L", "LidClose_R",
    "CheekRaise_L", "CheekRaise_R", "Smile_L", "Smile_R", "Frown_L", "Frown_R",
    "LipPress", "MouthOpen", "JawDrop", "MouthTight", "MouthCornerDown",
]
EXPRESSIONS = ["relieved", "polite", "suspicious", "confused", "confident", "frozen", "deadpan", "exhausted"]


def read(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def sample_weight(start: int, end: int, local: int, start_weight: float, end_weight: float) -> float:
    """Same smoothstep the Godot controller writes: e = u^2 * (3 - 2u)."""
    span = end - start
    if span <= 0:
        raise ValueError("cue end must be after start")
    u = max(0.0, min(1.0, (local - start) / span))
    eased = u * u * (3.0 - 2.0 * u)
    weight = (1.0 - eased) * start_weight + eased * end_weight
    return max(0.0, min(1.0, weight))


def _lock_v1_weights(face: dict, v1_file: Path, errors: list[str]) -> None:
    if not v1_file.is_file():
        return
    v1 = json.loads(v1_file.read_text(encoding="utf-8"))
    for pose, data in v1["presets"].items():
        for name, value in data["weights"].items():
            if face["presets"][pose]["weights"].get(name) != value:
                errors.append(f"Changed v1 baseline {pose}.{name}")


def _validate_sampling(face: dict, cues: dict, errors: list[str]) -> None:
    presets = face["presets"]
    checks = {
        ("SH_009", 0): "polite",
        ("SH_009", 24): "frozen",
        ("SH_005", 0): "confused",
        ("SH_005", 18): "suspicious",
        ("SH_014", 0): "exhausted",
        ("SH_014", 30): "deadpan",
    }
    by_code = {record["code"]: record for record in cues.get("examples", [])}
    for (code, local), pose in checks.items():
        record = by_code.get(code)
        if record is None:
            errors.append(f"Missing sample cue {code}")
            continue
        cue = next((item for item in record["faceCues"] if item["startLocalFrame"] <= local < item["endLocalFrameExclusive"]), None)
        if cue is None or (cue["from"] != pose and cue["to"] != pose):
            errors.append(f"{code} frame {local} is not the {pose} pose")
            continue
        for name in NAMES:
            expected = sample_weight(cue["startLocalFrame"], cue["endLocalFrameExclusive"], local, presets[cue["from"]]["weights"][name], presets[cue["to"]]["weights"][name])
            if expected != presets[pose]["weights"][name]:
                errors.append(f"{code} frame {local} {name} does not land on {pose}")
    record = by_code.get("SH_009")
    if record:
        cue = record["faceCues"][0]
        polite = presets["polite"]["weights"]["Smile_L"]
        frozen = presets["frozen"]["weights"]["Smile_L"]
        expected = sample_weight(0, 24, 12, polite, frozen)
        if abs(expected - ((polite + frozen) / 2.0)) > 1e-9:
            errors.append(f"SH_009 midpoint Smile_L is not the smoothstep midpoint ({expected})")


def _validate_godot(errors: list[str]) -> None:
    controller_path = GODOT / "scripts" / "FaceMorphController.gd"
    lighting_script_path = GODOT / "scripts" / "ApartmentLightingController.gd"
    lighting_scene_path = GODOT / "scenes" / "sets" / "ApartmentLighting.tscn"
    morph_doc = DOCS / "BS-M4E-C-FACIAL-MORPH-CONTRACT.md"
    light_doc = DOCS / "BS-M4E-D-APARTMENT-LIGHTING-CONTRACT.md"
    for path in (controller_path, lighting_script_path, lighting_scene_path, morph_doc, light_doc):
        if not path.is_file():
            errors.append(f"Missing {path.relative_to(ROOT)}")
    if not controller_path.is_file() or not lighting_script_path.is_file() or not lighting_scene_path.is_file():
        return
    controller = controller_path.read_text(encoding="utf-8")
    lighting_script = lighting_script_path.read_text(encoding="utf-8")
    scene = lighting_scene_path.read_text(encoding="utf-8")
    morph_text = morph_doc.read_text(encoding="utf-8") if morph_doc.is_file() else ""
    light_text = light_doc.read_text(encoding="utf-8") if light_doc.is_file() else ""
    if "u * u * (3.0 - 2.0 * u)" not in controller:
        errors.append("FaceMorphController is missing the smoothstep formula")
    for token in ("find_blend_shape_by_name", "blueprint.face_morphs.v2", "func evaluate("):
        if token not in controller:
            errors.append(f"FaceMorphController is missing {token}")
    if "create_tween" in controller or "create_tween" in lighting_script:
        errors.append("Production face or lighting script uses a tween")
    if "ProjectSettings.set_setting" in lighting_script:
        errors.append("Lighting controller mutates project settings")
    for token in (
        "TONE_MAPPER_FILMIC",
        "auto_exposure_enabled = false",
        "WindowKey",
        "FaceFill",
        "RimAccent",
        "SHADOW_PARALLEL_4_SPLITS",
        "apartment_day",
        "phone_insert",
        "host_desk",
        "func _deep_merge",
    ):
        if token not in lighting_script:
            errors.append(f"ApartmentLightingController is missing {token}")
    if scene.count('type="WorldEnvironment"') != 1:
        errors.append("ApartmentLighting.tscn must contain exactly one WorldEnvironment")
    for name, node_type in (
        ("WindowKey", "DirectionalLight3D"),
        ("FaceFill", "OmniLight3D"),
        ("RimAccent", "SpotLight3D"),
    ):
        if f'[node name="{name}" type="{node_type}" parent="LightingRig"]' not in scene:
            errors.append(f"ApartmentLighting.tscn is missing {name} {node_type}")
    for name in NAMES:
        if f"`{name}`" not in morph_text:
            errors.append(f"Facial markdown is missing {name}")
    for token in ("WindowKey", "FaceFill", "RimAccent", "TONE_MAPPER_FILMIC"):
        if token not in light_text:
            errors.append(f"Lighting markdown is missing {token}")


def validate(stage_plan: Path | None) -> list[str]:
    errors = []
    face = read("BS-M4E-C-FACE-PRESETS-v2.json")
    lights = read("BS-M4E-D-LIGHTING-PROFILES-v2.json")
    cues = read("BS-M4E-CD-SHOT-BINDINGS-v1.json")
    if face.get("schemaVersion") != "blueprint.face_morphs.v2": errors.append("Facial schema mismatch")
    names = [c.get("name") for c in face.get("channels", [])]
    if names != NAMES: errors.append("Exact canonical 22-channel name and order mismatch")
    if set(face.get("presets", {})) != set(EXPRESSIONS): errors.append("Missing or extra expression presets")
    if face.get("expectedChannelCount") != 22: errors.append("Expected channel count != 22")
    for pose, data in face.get("presets", {}).items():
        weights = data.get("weights", {})
        if set(weights) != set(NAMES): errors.append(f"{pose}: missing/extra keys")
        for name, value in weights.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                errors.append(f"{pose}.{name}: invalid weight {value}")
    neutral = face.get("neutral", {}).get("weights", {})
    if set(neutral) != set(NAMES) or any(neutral.get(n) != 0 for n in NAMES): errors.append("Neutral not all zero")
    # Lock original M4E v1 sparse nonzero coefficients. The repo copy is authoritative here.
    repo_v1 = EXAMPLES / "BS-M4E-FACIAL-RIG.json"
    if not repo_v1.is_file():
        errors.append("Repo v1 facial baseline is missing")
    _lock_v1_weights(face, repo_v1, errors)
    _lock_v1_weights(face, Path("/mnt/data/blueprint_bs_m4e_design/docs/examples/BS-M4E-FACIAL-RIG.json"), errors)
    _validate_sampling(face, cues, errors)
    _validate_godot(errors)
    if lights.get("schemaVersion") != "blueprint.apartment_lighting.v2": errors.append("Lighting schema mismatch")
    render = lights.get("render", {})
    for key, target in [("width",1080),("height",1920),("fps",30),("masterFrames",2490)]:
        if render.get(key) != target: errors.append(f"render.{key} expected {target}")
    if render.get("method") != "Forward+" or render.get("usePhysicalLightUnits") is not False: errors.append("Renderer/physical light units mismatch")
    env = lights.get("globalEnvironment",{}).get("environment",{})
    for key, target in [("tonemap_mode","TONE_MAPPER_FILMIC"),("tonemap_exposure",1.0),("ssil_enabled",False),("glow_enabled",False)]:
        if env.get(key) != target: errors.append(f"Environment {key} mismatch")
    if lights.get("globalEnvironment",{}).get("cameraAttributes",{}).get("auto_exposure_enabled") is not False:
        errors.append("Auto exposure must be disabled")
    profiles = lights.get("profiles",{})
    if set(profiles) != {"apartment_day","phone_insert","host_desk"}: errors.append("Lighting profiles mismatch")
    b = profiles.get("apartment_day",{})
    if b.get("key",{}).get("nodeType") != "DirectionalLight3D": errors.append("Missing DirectionalLight3D key")
    if b.get("fill",{}).get("nodeType") != "OmniLight3D": errors.append("Missing OmniLight3D fill")
    if b.get("rim",{}).get("nodeType") != "SpotLight3D": errors.append("Missing SpotLight3D rim")
    for n, expected in [("key",True),("fill",False),("rim",False)]:
        if b.get(n,{}).get("shadow_enabled") is not expected:
            errors.append(f"{n}: shadow policy mismatch")
    if cues.get("fps") != 30 or cues.get("totalFrames") != 2490: errors.append("Cue timing config mismatch")
    if stage_plan:
        plan = json.loads(stage_plan.read_text(encoding="utf-8"))
        if (plan.get("fps"),plan.get("totalFrames"),len(plan.get("shots",[]))) != (30,2490,14):
            errors.append("Stage plan is not the 14-shot 2490-frame pilot")
        indexed = {shot["shotId"]:shot for shot in plan.get("shots",[])}
        for record in cues.get("examples",[]):
            base = indexed.get(record.get("shotId"))
            if not base: errors.append("Unknown shot " + str(record.get("shotId"))); continue
            for field in ("code","startFrame","durationFrames"):
                if record.get(field) != base.get(field): errors.append(f"Cue differs from approved stage plan: {record['shotId']}.{field}")
    for rec in cues.get("examples", []):
        p=0
        for cue in rec.get("faceCues", []):
            start=cue.get("startLocalFrame",-1);end=cue.get("endLocalFrameExclusive",-1)
            if start != p or end <= start or end > rec.get("durationFrames",0): errors.append(f"{rec['code']}: gap/overlap/invalid cue")
            if cue.get("from") not in EXPRESSIONS or cue.get("to") not in EXPRESSIONS: errors.append(f"{rec['code']}: unknown facial preset")
            p=end
        if p != rec.get("durationFrames"): errors.append(f"{rec['code']}: incomplete cue coverage")
        if rec.get("lightingProfile") not in profiles: errors.append(f"{rec['code']}: unknown lighting profile")
    return errors


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--stage-plan', type=Path, help='authoritative BS-M4-PILOT-STAGE-PLAN.json')
    args=ap.parse_args()
    errors=validate(args.stage_plan)
    if errors:
        print('BS-M4E-C/D: CONTRACT FAIL')
        for error in errors: print('ERROR:', error)
        return 1
    print('BS-M4E-C/D: CONTRACT PASS; 22 channels x 8 presets, fixed 1080x1920/30fps profiles, sample shot cues')
    print('STRUCTURE: FaceMorphController and ApartmentLighting match the JSON and markdown contracts')
    print('PRODUCTION_GATE: BLOCKED; named face harness is not sculpted art and look-dev is provisional')
    print('NOTICE: no contact sheet, imported GLB, Forward+ proof render, or owner signoff.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
