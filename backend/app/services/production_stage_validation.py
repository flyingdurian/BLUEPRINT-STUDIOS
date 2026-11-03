"""Check M4-E design contracts and the Godot rig harness. This does not approve art."""
from __future__ import annotations

import json
import re
from pathlib import Path

EXPRESSIONS = [
    "relieved", "polite", "suspicious", "confused",
    "confident", "frozen", "deadpan", "exhausted",
]
SOCKET_BONES = {
    "phone_grip_r": "Hand_R",
    "phone_grip_l": "Hand_L",
    "mug_grip_r": "Hand_R",
}
REQUIRED_SCENE_NODES = ("CharacterRoot", "Skeleton3D", "AnimationPlayer", "BodyMesh", "FaceMesh")
REQUIRED_SCRIPTS = (
    "scripts/RigValidator.gd",
    "scripts/PropSocketResolver.gd",
    "actors/lead/LeadPropBinding.gd",
    "actors/lead/ActorLead.tscn",
    "tests/test_rig_and_props.gd",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_design(plan: dict, examples: Path) -> list[str]:
    errors: list[str] = []
    rig = _read_json(examples / "BS-M4E-RIG-CONTRACT.json")
    face = _read_json(examples / "BS-M4E-FACIAL-RIG.json")
    anim = _read_json(examples / "BS-M4E-ACTION-BINDINGS.json")
    lights = _read_json(examples / "BS-M4E-LIGHTING-PRESETS.json")
    if len(rig["requiredBones"]) != 40 or len(set(rig["requiredBones"])) != 40:
        errors.append("Expected 40 distinct canonical bones")
    channels = [row["name"] for row in face["channels"]]
    if len(channels) != 22 or len(set(channels)) != 22:
        errors.append("Expected 22 distinct facial channels")
    if set(face["presets"]) != set(EXPRESSIONS):
        errors.append("All eight named facial presets required")
    for name, preset in face["presets"].items():
        for channel, value in preset["weights"].items():
            if channel not in channels or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                errors.append(f"Invalid morph {name}:{channel}:{value}")
    if len(plan["shots"]) != 14 or plan["totalFrames"] != 2490 or plan["fps"] != 30:
        errors.append("Stage plan must be 14 shots/2490 frames/30fps")
    expected = {action for shot in plan["shots"] for action in shot["performance"]["actionIds"]}
    defined = set(anim["actionRegistry"])
    if expected != defined:
        errors.append(f"Action registry difference: missing {expected - defined}, extra {defined - expected}")
    if len(expected) != 34:
        errors.append(f"Expected 34 unique action IDs, found {len(expected)}")
    if len(anim["shots"]) != len(plan["shots"]):
        errors.append("Shot count mismatch")
    for planned, staged in zip(plan["shots"], anim["shots"]):
        for key in ("shotId", "code", "startFrame", "durationFrames"):
            if planned[key] != staged[key]:
                errors.append(f"Wrong {key} in {planned['code']}")
        if staged["cameraPreset"] != planned["camera"]["preset"]:
            errors.append(f"Camera changed: {planned['code']}")
        if staged["setKey"] != planned["setKey"]:
            errors.append(f"Set changed: {planned['code']}")
        if len(staged["actionCues"]) != len(planned["performance"]["actionIds"]):
            errors.append(f"Action cue count mismatch: {planned['code']}")
        for original, cue in zip(planned["performance"]["actionIds"], staged["actionCues"]):
            if original != cue["actionId"]:
                errors.append(f"Action reorder: {planned['code']}")
            if not 0 <= cue["startLocalFrame"] < cue["endLocalFrameExclusive"] <= planned["durationFrames"]:
                errors.append(f"Bad local frame cue: {planned['code']}/{original}")
        if staged["initialFacePose"] not in face["presets"]:
            errors.append(f"Unknown facial preset: {planned['code']}")
        if staged["lightingPreset"] not in lights["presets"]:
            errors.append(f"Unknown light preset: {planned['code']}")
    return errors


def validate_godot_structure(project: Path, rig: dict) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_SCRIPTS:
        if not (project / relative).is_file():
            errors.append(f"Godot project is missing {relative}")
    validator = project / "scripts" / "RigValidator.gd"
    scene_path = project / "actors" / "lead" / "ActorLead.tscn"
    resolver = project / "scripts" / "PropSocketResolver.gd"
    if validator.is_file():
        declared = _declared_bones(validator.read_text(encoding="utf-8"))
        if declared != rig["requiredBones"]:
            errors.append("RigValidator.gd bone list does not match the rig contract")
    if resolver.is_file():
        text = resolver.read_text(encoding="utf-8")
        for token in ("phone_grip_r_to_table", "phone_grip_r_to_drawer", "mug_grip_r_or_two_handed_gag"):
            if token not in text:
                errors.append(f"PropSocketResolver.gd does not handle {token}")
    if scene_path.is_file():
        errors.extend(validate_scene_text(scene_path.read_text(encoding="utf-8"), rig))
    return errors


def validate_scene_text(scene_text: str, rig: dict) -> list[str]:
    errors: list[str] = []
    bones = re.findall(r'bones/\d+/name = "([^"]+)"', scene_text)
    required = rig["requiredBones"]
    if len(bones) != len(set(bones)):
        errors.append("Actor scene repeats a bone name")
    missing = [name for name in required if name not in bones]
    if missing:
        errors.append("Actor scene is missing canonical bones: " + ", ".join(missing))
    for scale in re.findall(r"bones/\d+/scale = Vector3\(([^)]+)\)", scene_text):
        parts = [float(part.strip()) for part in scale.split(",")]
        if len(parts) != 3 or any(part <= 0 for part in parts) or len(set(parts)) != 1:
            errors.append(f"Actor scene bone scale is not uniform and positive: {scale}")
    nodes = _scene_nodes(scene_text)
    names = {node["name"] for node in nodes}
    for name in (*REQUIRED_SCENE_NODES, *SOCKET_BONES, "Grip_R", "Grip_L"):
        if name not in names:
            errors.append(f"Actor scene is missing node {name}")
    by_name = {node["name"]: node for node in nodes}
    for socket, bone in SOCKET_BONES.items():
        node = by_name.get(socket)
        if node and (node["type"] != "BoneAttachment3D" or node["properties"].get("bone_name") != bone):
            errors.append(f"{socket} must be a BoneAttachment3D bound to {bone}")
    for grip, bone in (("Grip_R", "Hand_R"), ("Grip_L", "Hand_L")):
        node = by_name.get(grip)
        if node and (node["type"] != "BoneAttachment3D" or node["properties"].get("bone_name") != bone):
            errors.append(f"{grip} must be a BoneAttachment3D bound to {bone}")
    if not any(node["name"] == "PhoneSocket" and node["parent"].endswith("Grip_R") for node in nodes):
        errors.append("Grip_R/PhoneSocket is missing")
    if not any(node["name"] == "MugSocket" and node["parent"].endswith("Grip_R") for node in nodes):
        errors.append("Grip_R/MugSocket is missing")
    if not any(node["name"] == "PhoneSocket" and node["parent"].endswith("Grip_L") for node in nodes):
        errors.append("Grip_L/PhoneSocket is missing")
    for anchor in ("table_phone_rest", "drawer_phone_rest", "mug_rest", "cutaway_cloned_phones"):
        if anchor not in names:
            errors.append(f"Stage anchor is missing: {anchor}")
    if ".glb" in scene_text or "OWNER_APPROVED" in scene_text:
        errors.append("Actor scene claims approved art. The current harness must stay an unapproved dummy.")
    return errors


def production_blockers(project: Path) -> list[str]:
    scene = project / "actors" / "lead" / "ActorLead.tscn"
    blockers = [
        "No owner-approved protagonist GLB is instanced in the Godot project.",
        "The 34 action IDs are registry names, not authored AnimationPlayer clips.",
        "FaceMesh does not yet carry the 22 sculpted blend shapes.",
    ]
    if scene.is_file() and "TEST_DUMMY_NOT_APPROVED_ART" not in scene.read_text(encoding="utf-8"):
        blockers.append("Actor scene is missing the unapproved-dummy marker")
    return blockers


def _declared_bones(script_text: str) -> list[str]:
    match = re.search(r"const REQUIRED_BONES: PackedStringArray = \[(.*?)\]", script_text, re.S)
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def _scene_nodes(scene_text: str) -> list[dict]:
    pattern = re.compile(r'\[node name="([^"]+)" type="([^"]+)"(?: parent="([^"]*)")?\]')
    matches = list(pattern.finditer(scene_text))
    nodes = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(scene_text)
        properties = {}
        for line in scene_text[match.end():end].splitlines():
            if " = " not in line or line.startswith("["):
                continue
            key, value = line.split(" = ", 1)
            properties[key.strip()] = value.strip().strip('"')
        nodes.append({
            "name": match.group(1),
            "type": match.group(2),
            "parent": match.group(3) or "",
            "properties": properties,
        })
    return nodes
