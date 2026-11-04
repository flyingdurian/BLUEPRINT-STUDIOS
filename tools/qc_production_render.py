#!/usr/bin/env python3
"""Inspect a production render candidate before any pilot-final.mp4 is written.

This gate does not encode video. M4-D assembly stays the only mux path, and it
must not be asked to write pilot-final.mp4 while this report has errors.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GODOT = ROOT / "godot_render"
EXPECTED_SECONDS = 2490 / 30
FRAME_TOLERANCE = 1 / 30


def inspect_candidate(job: Path | None = None, project: Path | None = None) -> dict[str, object]:
    errors: list[str] = []
    project_root = project or GODOT
    errors.extend(_material_errors(project_root))
    if job is None:
        errors.append("No production render candidate was provided")
    else:
        errors.extend(_job_errors(job))
    return {"ok": not errors, "encodeFinal": False if errors else True, "errors": errors}


def _job_errors(job: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = job / "render_manifest.json"
    if not manifest_path.is_file():
        return ["Render manifest is missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("quality") != "production" or manifest.get("productionLocked") is not True:
        errors.append("Previs or unlocked manifest cannot generate pilot-final.mp4")
    if int(manifest.get("fps", 0)) != 30 or int(manifest.get("totalFrames", 0)) != 2490:
        errors.append("Manifest timing is not 2490 frames at 30 fps")
    shots = manifest.get("shots", [])
    if isinstance(shots, list):
        cursor = 0
        for shot in shots:
            start = int(shot.get("startFrame", -1))
            end = int(shot.get("endFrameExclusive", -1))
            if start != cursor or end <= start:
                errors.append(f"{shot.get('code', 'shot')} breaks the half-open timeline")
                break
            cursor = end
        if shots and cursor != 2490:
            errors.append("Shot timeline does not end at frame 2490")
    if (job / "pilot-previs.ogv").is_file():
        errors.append("Silent previs movie cannot satisfy the production frame gate")
    elif not (job / "pilot-master.ogv").is_file():
        errors.append("Production master frames are missing")
    mix = job / "narration_mix.wav"
    if not mix.is_file():
        errors.append("Narration mix is missing, so audio sync cannot be accepted")
    else:
        duration = _wav_seconds(mix)
        if abs(duration - EXPECTED_SECONDS) > FRAME_TOLERANCE:
            errors.append(f"Narration mix is {duration:.3f}s and the picture is {EXPECTED_SECONDS:.3f}s")
    captions = job / "captions.vtt"
    if not captions.is_file():
        errors.append("Captions are missing")
    else:
        errors.extend(_caption_errors(captions.read_text(encoding="utf-8")))
    return errors


def _material_errors(project: Path) -> list[str]:
    errors: list[str] = []
    scene = project / "actors" / "lead" / "ActorLead.tscn"
    if not scene.is_file():
        return ["Actor scene is missing"]
    text = scene.read_text(encoding="utf-8")
    for name in _unassigned_material_nodes(text):
        errors.append(f"Unassigned material on {name}")
    if "albedo_texture" in text and "albedo_texture = " not in text:
        errors.append("A material slot has an unassigned texture")
    return errors


def _unassigned_material_nodes(scene_text: str) -> list[str]:
    pattern = re.compile(r'\[node name="([^"]+)" type="MeshInstance3D"[^\]]*\](.*?)(?=\n\[|\Z)', re.S)
    missing: list[str] = []
    for match in pattern.finditer(scene_text):
        body = match.group(2)
        if "material" not in body and "surface_material_override" not in body:
            missing.append(match.group(1))
    return missing


def _caption_errors(text: str) -> list[str]:
    cues = re.findall(r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})", text)
    if len(cues) != 14:
        return [f"Captions have {len(cues)} cues; the pilot has 14 shots"]
    previous = -1
    for start, end in cues:
        start_ms = _clock_ms(start)
        end_ms = _clock_ms(end)
        if start_ms <= previous or end_ms <= start_ms:
            return ["Caption cues overlap or run backwards"]
        previous = end_ms
    return []


def _clock_ms(value: str) -> int:
    hours, minutes, seconds = value.split(":")
    whole, millis = seconds.split(".")
    return ((int(hours) * 60 + int(minutes)) * 60 + int(whole)) * 1000 + int(millis)


def _wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        if rate <= 0:
            return -1.0
        return handle.getnframes() / float(rate)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path, help="Render job directory to inspect")
    args = parser.parse_args()
    report = inspect_candidate(args.job)
    if report["ok"]:
        print("QC PASS")
        print("pilot-final.mp4 was not written by this gate")
        return 0
    print("QC FAIL")
    for error in report["errors"]:
        print("ERROR:", error)
    print("pilot-final.mp4 was not written")
    return 1


if __name__ == "__main__":
    sys.exit(main())
