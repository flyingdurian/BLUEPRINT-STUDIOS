#!/usr/bin/env python3
"""Offline schema and content-contract validation for M4E-C + M4E-D.

Does NOT validate a real .glb's morph import, GDScript compilation, lighting,
shadows, rendered frames, or owner art acceptance. Run Godot runtime gates too.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "docs" / "examples"
NAMES = [
    "BrowInnerUp", "BrowOuterUp_L", "BrowOuterUp_R", "BrowDown_L", "BrowDown_R",
    "EyeWide_L", "EyeWide_R", "EyeSquint_L", "EyeSquint_R", "LidClose_L", "LidClose_R",
    "CheekRaise_L", "CheekRaise_R", "Smile_L", "Smile_R", "Frown_L", "Frown_R",
    "LipPress", "MouthOpen", "JawDrop", "MouthTight", "MouthCornerDown",
]
EXPRESSIONS = ["relieved", "polite", "suspicious", "confused", "confident", "frozen", "deadpan", "exhausted"]


def read(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


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
    # Lock original M4E v1 values wherever a sparse nonzero coefficient was given.
    v1_file = Path("/mnt/data/blueprint_bs_m4e_design/docs/examples/BS-M4E-FACIAL-RIG.json")
    # v1 optional, because Cursor will execute this in a clean repository.
    if v1_file.is_file():
        v1 = json.loads(v1_file.read_text(encoding="utf-8"))
        for pose, data in v1["presets"].items():
            for name, value in data["weights"].items():
                if face["presets"][pose]["weights"].get(name) != value:
                    errors.append(f"Changed v1 baseline {pose}.{name}")
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
    print('NOTICE: no Godot runtime, imported rig, light render or art review tested.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
