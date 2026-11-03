#!/usr/bin/env python3
"""Validate M4-E design contracts and the Godot rig harness. This does not approve art."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.production_stage_validation import (  # noqa: E402
    production_blockers,
    validate_design,
    validate_godot_structure,
    _read_json,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--examples", type=Path, default=ROOT / "docs" / "examples")
    parser.add_argument("--godot", type=Path, default=ROOT / "godot_render")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    rig = _read_json(args.examples / "BS-M4E-RIG-CONTRACT.json")
    errors = validate_design(plan, args.examples)
    errors.extend(validate_godot_structure(args.godot, rig))
    blockers = production_blockers(args.godot)
    print(
        "M4-E design validation: "
        f"bones={len(rig['requiredBones'])} shots={len(plan['shots'])} frames={plan['totalFrames']}"
    )
    for error in errors:
        print("ERROR:", error)
    for blocker in blockers:
        print("BLOCKER:", blocker)
    if errors:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS (design contracts and Godot dummy structure; no art approval)")
    print("PRODUCTION_GATE: BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
