#!/usr/bin/env python3
"""BS-M4E-E reference QC baseline, Python 3.11+.

Fail-closed structural and A/V checks. Requires actual Godot evidence. It cannot
prove artistic quality solely from an MP4. No file is promoted or overwritten.

Usage: python tools/qc_production_render.py --job-dir PATH --stage-plan PATH \
    --rig-contract PATH --face-contract PATH --actions-contract PATH

Exit: 0 = TECHNICAL_PASS; 2 = QC failed/incomplete; 3 = invalid arguments/tools.
Owner approval is a separate downstream gate before 'pilot-final.mp4' promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

_MEDIA_SUFFIX = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    "model/gltf-binary": ".glb", "audio/wav": ".wav", "audio/mpeg": ".mp3",
    "video/mp4": ".mp4", "audio/ogg": ".ogg",
}
_LOG_PATTERNS = (
    ("GODOT_SCRIPT_ERROR", re.compile(r"SCRIPT ERROR|Parse Error")),
    ("GODOT_IMPORT", re.compile(r"import(?:er)?.{0,40}(?:fail|error)", re.IGNORECASE)),
    ("GODOT_TEXTURE", re.compile(r"(?:texture|image).{0,40}(?:fail|error|not found)", re.IGNORECASE)),
    ("GODOT_SHADER", re.compile(r"shader.{0,40}(?:error|fail)", re.IGNORECASE)),
)
_CONTRACT_HASHES = (
    ("skeletonContractSha256", "rig", "SKELETON_CONTRACT_SHA"),
    ("faceContractSha256", "face", "FACE_CONTRACT_SHA"),
    ("actionRegistrySha256", "actions", "ACTION_REGISTRY_SHA"),
    ("lightingContractSha256", "lighting", "LIGHTING_CONTRACT_SHA"),
)

FPS = 30
FRAMES = 2490
WIDTH = 1080
HEIGHT = 1920
VTT_TIME = re.compile(r"(?P<h>\d\d):(?P<m>\d\d):(?P<s>\d\d)\.(?P<ms>\d{3})")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def ffprobe(video: Path, frames: bool = False) -> dict[str, Any]:
    cmd = ["ffprobe", "-v", "error", "-of", "json"]
    if frames:
        cmd.extend(["-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp_time"])
    else:
        cmd.extend(["-count_frames", "-show_streams", "-show_format"])
    result = subprocess.run(cmd + [str(video)], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-500:]}")
    return json.loads(result.stdout)


class Report:
    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []
        self.metrics: dict[str, Any] = {}

    def check(self, ok: bool, code: str, message: str, *, evidence: Any = None,
              expected: Any = None, actual: Any = None, shot_id: str | None = None,
              frame: int | None = None) -> bool:
        if not ok:
            finding: dict[str, Any] = {"severity": "BLOCKER", "code": code, "message": message, "evidence": evidence}
            if expected is not None:
                finding["expected"] = expected
            if actual is not None:
                finding["actual"] = actual
            if shot_id is not None:
                finding["shotId"] = shot_id
            if frame is not None:
                finding["frame"] = frame
            self.findings.append(finding)
        return bool(ok)

    def warn(self, code: str, message: str, evidence: Any = None) -> None:
        self.findings.append({"severity": "WARNING", "code": code, "message": message, "evidence": evidence})


def validate_timeline(manifest: dict[str, Any], stage: dict[str, Any], report: Report) -> set[str]:
    report.check(manifest.get("schemaVersion") == "blueprint.render-manifest.v2", "SCHEMA", "Production manifest must be v2")
    report.check(manifest.get("quality") == "production" and manifest.get("productionLocked") is True,
                 "NOT_LOCKED", "Manifest not locked for production")
    report.check(manifest.get("proxy") is False and manifest.get("standIn") is None,
                 "PROXY", "Production cannot reference previs stand-ins")
    report.check(manifest.get("stagePlanStatus") == "APPROVED", "STAGE_APPROVAL", "Stage-plan approval missing")
    report.check((manifest.get("fps"), manifest.get("width"), manifest.get("height"), manifest.get("totalFrames"))
                 == (FPS, WIDTH, HEIGHT, FRAMES), "FORMAT", "Unexpected frame rate/resolution/runtime")
    shots = manifest.get("shots", [])
    original = stage.get("shots", [])
    report.check(len(shots) == len(original) == 14, "SHOT_COUNT", "Expected exactly 14 shots")
    report.check([shot.get("code") for shot in shots if isinstance(shot, dict)] == [f"SH_{n:03d}" for n in range(1, 15)],
                 "SHOT_CODES", "Shot codes must be SH_001 through SH_014 in order")
    end = 0
    all_actions: set[str] = set()
    original_actions: set[str] = set()
    for i, shot in enumerate(shots):
        if not isinstance(shot, dict):
            report.check(False, "SHOT_RECORD", f"Shot {i} is not an object")
            continue
        start, duration, stop = (shot.get("startFrame"), shot.get("durationFrames"), shot.get("endFrameExclusive"))
        if not all(isinstance(v, int) for v in (start, duration, stop)) or (start, duration, stop) != (end, duration, end + duration) or duration <= 0:
            report.check(False, "SHOT_TIMING", f"Invalid timing for shot {i}")
        else:
            end = stop
        if i >= len(original):
            continue
        planned = original[i]
        for key in ("shotId", "code", "startFrame", "durationFrames", "endFrameExclusive", "setKey"):
            report.check(shot.get(key) == planned.get(key), "STAGE_DRIFT", f"Shot {i+1} {key} changed")
        report.check(shot.get("cameraPreset", shot.get("camera", {}).get("preset")) == planned["camera"]["preset"],
                     "CAMERA_DRIFT", f"Camera preset mismatch {shot.get('code')}")
        cues = shot.get("actionCues", [])
        expected = planned["performance"]["actionIds"]
        original_actions.update(expected)
        actual = [c.get("actionId") for c in cues] if isinstance(cues, list) else []
        report.check(actual == expected, "ACTION_CUES", f"Missing/reordered action cues {shot.get('code')}")
        for cue in cues if isinstance(cues, list) else []:
            a, b = cue.get("startLocalFrame"), cue.get("endLocalFrameExclusive")
            report.check(isinstance(a, int) and isinstance(b, int) and 0 <= a < b <= duration,
                         "ACTION_TIME", f"Bad action interval {shot.get('code')}:{cue.get('actionId')}")
        all_actions.update(actual)
        report.check(shot.get("stageApproval") == "APPROVED", "SHOT_APPROVAL", f"Missing approval for {shot.get('code')}")
        for asset in shot.get("assets", []):
            ok = asset.get("verified") is True and asset.get("resolution") == "VERIFIED_BLOB" \
                 and bool(re.fullmatch(r"[a-f0-9]{64}", str(asset.get("sha256", ""))))
            report.check(ok, "ASSET_UNVERIFIED", f"Unverified pinned asset {asset.get('assetId')} in {shot.get('code')}")
    report.check(end == FRAMES, "TOTAL_DURATION", "Shot intervals do not cover 2490 frames", evidence=end)
    report.check(len(original_actions) == 34 and all_actions == original_actions,
                 "ACTION_COVERAGE", "All 34 stage-plan action IDs must have cues")
    return original_actions


def validate_staged_assets(job: Path, manifest: dict[str, Any], report: Report) -> None:
    """Rehash every unique staged version; path must stay inside the job."""
    examined: set[str] = set()
    for shot in manifest.get("shots", []):
        for asset in shot.get("assets", []):
            relative = asset.get("relativePath")
            digest = asset.get("sha256")
            if not isinstance(relative, str) or not isinstance(digest, str):
                report.check(False, "ASSET_PATH", f"Staged path/digest absent for {asset.get('assetId')}")
                continue
            if relative in examined:
                continue
            examined.add(relative)
            target = (job / relative).resolve()
            if job.resolve() not in target.parents or not target.is_file():
                report.check(False, "ASSET_PATH", f"Asset path escapes job or file missing: {relative}")
                continue
            actual_digest = sha256_file(target)
            report.check(actual_digest == digest, "STAGED_HASH", f"Physical bytes changed: {relative}",
                         expected=digest, actual=actual_digest)
            media_type = asset.get("mediaType")
            if isinstance(media_type, str):
                suffix = _MEDIA_SUFFIX.get(media_type)
                report.check(suffix is not None and target.suffix.lower() == suffix, "ASSET_MIME",
                             f"Staged suffix does not match {media_type} for {asset.get('assetId')}",
                             expected=suffix, actual=target.suffix.lower())
    report.metrics["stagedMediaFilesChecked"] = len(examined)


def validate_engine(engine: dict[str, Any], digest: str, rig: dict[str, Any],
                    face: dict[str, Any], actions: set[str], report: Report,
                    manifest: dict[str, Any] | None = None) -> None:
    report.check(engine.get("manifestSha256") == digest, "ENGINE_MANIFEST", "Engine report is for different manifest")
    required_bones = rig.get("requiredBones", [])
    required_shapes = [x["name"] for x in face.get("channels", [])]
    report.check(len(required_bones) == 40 and len(set(required_bones)) == 40,
                 "RIG_CONTRACT", "Canonical 40 bones contract invalid")
    report.check(len(required_shapes) == 22 and len(set(required_shapes)) == 22,
                 "FACE_CONTRACT", "Canonical 22 morph names contract invalid")
    bone_names = list(engine.get("boneNames", []))
    report.check(engine.get("schemaVersion") == "blueprint.engine-preflight.v1",
                 "ENGINE_SCHEMA", "Engine preflight schema is not blueprint.engine-preflight.v1",
                 expected="blueprint.engine-preflight.v1", actual=engine.get("schemaVersion"))
    report.check(set(bone_names) == set(required_bones) and len(bone_names) == 40,
                 "BONES", "Godot rig is not the exact 40-name skeleton",
                 expected=40, actual=len(bone_names))
    report.check(set(required_shapes).issubset(set(engine.get("blendShapeNames", []))),
                 "MORPHS", "Godot FaceMesh missing named morphs")
    report.check(set(actions).issubset(set(engine.get("executableActionIds", []))),
                 "ACTIONS_NOT_EXECUTABLE", "Godot has unresolved production actions")
    report.check(engine.get("rigStatus") == "OWNER_APPROVED", "RIG_IDENTITY", "Rig identity not approved")
    report.check(str(engine.get("engineVersion", "")).startswith("4.7.2"), "ENGINE_VERSION", "Godot 4.7.2 required")
    if manifest:
        expected_cameras = {shot.get("cameraPreset", shot.get("camera", {}).get("preset")) for shot in manifest.get("shots", [])}
        report.check(expected_cameras.issubset(set(engine.get("cameraPresets", []))), "CAMERAS", "Missing camera presets")
        pinned_rig = manifest.get("production", {}).get("rigSha256")
        report.check(engine.get("rigSha256") == pinned_rig, "RIG_HASH", "Engine imported a different rig version",
                     expected=pinned_rig, actual=engine.get("rigSha256"))
        report.check(engine.get("approvedSourceDigest") == pinned_rig, "APPROVED_SOURCE",
                     "Engine approvedSourceDigest does not match the pinned rig",
                     expected=pinned_rig, actual=engine.get("approvedSourceDigest"))
    report.check(engine.get("skeletonBindingsOk") is True, "SKIN_BINDING", "Skinned meshes not bound")
    report.check(engine.get("socketsCalibrated") is True, "SOCKETS", "Prop sockets not calibrated")
    report.check(int(engine.get("surfacesValidated", 0)) > 0, "SURFACES", "No effective materials inspected")
    report.check(int(engine.get("texturesValidated", 0)) > 0, "TEXTURES", "No textures inspected")
    for field in ("materialErrors", "missingTextures", "socketErrors", "importErrors", "sceneWarnings"):
        report.check(engine.get(field) == [], field.upper(), f"Godot reported {field}", evidence=engine.get(field))


def validate_contract_hashes(production: dict[str, Any], contracts: dict[str, Path | None], report: Report) -> None:
    """Hash the source contracts named by the sealed production block."""
    for field, key, code in _CONTRACT_HASHES:
        expected = production.get(field)
        path = contracts.get(key)
        if not isinstance(expected, str) or re.fullmatch(r"[a-f0-9]{64}", expected) is None:
            report.check(False, code, f"Missing {field}", expected=expected, actual=None)
            continue
        if path is None or not path.is_file():
            report.check(False, code, f"No contract file supplied for {field}", expected=expected, actual=None)
            continue
        actual = sha256_file(path)
        report.check(actual == expected, code, f"{field} does not match {path.name}", expected=expected, actual=actual)


def validate_godot_log(job: Path, report: Report) -> None:
    log = job / "godot.log"
    if not log.is_file():
        report.check(False, "GODOT_LOG_MISSING", "Godot log is missing")
        return
    text = log.read_text(encoding="utf-8", errors="replace")
    for code, pattern in _LOG_PATTERNS:
        match = pattern.search(text)
        report.check(match is None, code, "Godot log contains a production error",
                     evidence=None if match is None else match.group(0))


def validate_frame_index(path: Path, report: Report) -> None:
    if not path.is_file():
        report.check(False, "FRAME_INDEX_MISSING", "render_frame_index.json is missing")
        return
    payload = read_json(path)
    rows = payload.get("frames") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        report.check(False, "FRAME_INDEX_COUNT", "Frame index is not a list", actual=type(rows).__name__)
        return
    report.check(len(rows) == FRAMES, "FRAME_INDEX_COUNT", "Frame index does not cover 2490 frames",
                 expected=FRAMES, actual=len(rows))
    for index, row in enumerate(rows[:FRAMES]):
        if not isinstance(row, dict):
            report.check(False, "FRAME_INDEX_PTS", f"Frame index row {index} is not an object", frame=index)
            break
        try:
            actual = float(row.get("pts", row.get("best_effort_timestamp_time")))
        except (TypeError, ValueError):
            report.check(False, "FRAME_INDEX_PTS", f"Frame index timestamp missing at {index}", frame=index)
            break
        expected = index / FPS
        if abs(actual - expected) > 0.0015:
            report.check(False, "FRAME_INDEX_PTS", f"Frame index timestamp drifted at {index}",
                         expected=expected, actual=actual, frame=index)
            break


def validate_trace(trace: Path, manifest: dict[str, Any], report: Report) -> None:
    shots = manifest.get("shots", [])
    if not trace.is_file():
        report.check(False, "TRACE_MISSING", "Godot render_trace.jsonl missing")
        return
    frame = 0
    shot_index = 0
    expected_events: set[tuple[int, str]] = set()
    seen_events: set[tuple[int, str]] = set()
    for shot in shots:
        for cue in shot.get("actionCues", []):
            expected_events.add((shot["startFrame"] + cue["startLocalFrame"], cue["actionId"]))
    try:
        with trace.open("r", encoding="utf-8") as f:
            for raw in f:
                row = json.loads(raw)
                if shot_index >= len(shots):
                    report.check(False, "TRACE_OVERFLOW", "Extra frame trace rows")
                    break
                while shot_index < len(shots) - 1 and frame >= shots[shot_index]["endFrameExclusive"]:
                    shot_index += 1
                shot = shots[shot_index]
                report.check(row.get("frame") == frame, "TRACE_FRAME", f"Trace index mismatch at {frame}")
                report.check(row.get("shotId") == shot["shotId"], "TRACE_SHOT", f"Wrong active shot at {frame}")
                report.check(row.get("cameraPreset") == shot.get("cameraPreset", shot.get("camera", {}).get("preset")),
                             "TRACE_CAMERA", f"Wrong camera at {frame}")
                report.check(row.get("faceChannelCount") == 22, "TRACE_FACE", f"Incomplete facial evaluation at {frame}")
                for error_field in ("socketErrors", "materialErrors", "missingTextures"):
                    report.check(row.get(error_field) == [], "TRACE_" + error_field.upper(),
                                 f"Frame {frame}: {error_field}", evidence=row.get(error_field))
                for action in row.get("startedActions", []):
                    seen_events.add((frame, str(action)))
                frame += 1
    except (OSError, ValueError, TypeError) as exc:
        report.check(False, "TRACE_PARSE", f"Cannot decode frame trace: {exc}")
    report.check(frame == FRAMES, "TRACE_COUNT", "Expected 2490 ordered frame trace rows", evidence=frame)
    report.check(seen_events == expected_events, "TRACE_ACTION_EVENTS", "Action start events not at authored frames",
                 evidence={"missing": sorted(expected_events - seen_events), "unexpected": sorted(seen_events - expected_events)})
    report.metrics["evaluatedFrames"] = frame


def validate_video(candidate: Path, report: Report) -> None:
    if not candidate.is_file():
        report.check(False, "VIDEO_MISSING", "Candidate MP4 missing")
        return
    meta = ffprobe(candidate)
    video = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in meta.get("streams", []) if s.get("codec_type") == "audio"), {})
    report.check(video.get("codec_name") == "h264", "VIDEO_CODEC", "Expected H.264 video")
    report.check(video.get("pix_fmt") == "yuv420p", "PIX_FMT", "Expected yuv420p")
    report.check((video.get("width"), video.get("height")) == (WIDTH, HEIGHT), "VIDEO_SIZE", "Wrong output size")
    try:
        rate = Fraction(str(video.get("avg_frame_rate", "0/1")))
    except (ZeroDivisionError, ValueError):
        rate = Fraction(0)
    report.check(rate == 30, "FPS", "Video is not exact CFR 30")
    try:
        frames = int(video.get("nb_read_frames", "-1"))
    except (ValueError, TypeError):
        frames = -1
    report.check(frames == FRAMES, "DECODED_FRAMES", "Wrong decoded frame count", evidence=frames)
    report.check(audio.get("codec_name") == "aac", "AUDIO_CODEC", "Expected AAC mix")
    report.check(int(audio.get("sample_rate", 0)) == 48000, "AUDIO_RATE", "Audio not 48 kHz")
    report.check(video.get("color_primaries") in ("bt709",), "COLOR", "Missing Rec.709 primaries metadata")
    report.check(video.get("color_transfer") in ("bt709",), "TRANSFER", "Missing Rec.709 transfer metadata")
    report.check(video.get("color_space") in ("bt709",), "MATRIX", "Missing Rec.709 matrix metadata")
    for name, stream, tolerance in (("video", video, .035), ("audio", audio, .15)):
        try:
            duration = float(stream.get("duration", -1))
        except (ValueError, TypeError):
            duration = -1
        report.check(abs(duration - 83.0) <= tolerance, "DURATION_" + name.upper(),
                     f"Wrong {name} duration", evidence=duration)
    ts = ffprobe(candidate, frames=True).get("frames", [])
    report.check(len(ts) == FRAMES, "PTS_FRAMECOUNT", "Frame timestamp count not 2490", evidence=len(ts))
    last = None
    for idx, row in enumerate(ts):
        try:
            actual = float(row["best_effort_timestamp_time"])
        except (ValueError, KeyError, TypeError):
            report.check(False, "PTS_MISSING", f"Timestamp unavailable for frame {idx}")
            break
        expected = idx / FPS
        if abs(actual - expected) > .0015 or (last is not None and actual <= last):
            report.check(False, "PTS_DRIFT", f"Invalid presentation timestamp at frame {idx}",
                         evidence={"actual": actual, "expected": expected})
            break
        last = actual
    report.metrics["decodedFrames"] = frames
    report.metrics["videoSha256"] = sha256_file(candidate)


def parse_vtt(path: Path) -> list[tuple[int, int, str]]:
    content = path.read_text(encoding="utf-8-sig")
    if not content.startswith("WEBVTT"):
        raise ValueError("Not WEBVTT")
    cues: list[tuple[int, int, str]] = []
    for block in re.split(r"\r?\n\s*\r?\n", content):
        if "-->" not in block:
            continue
        lines = block.splitlines()
        index = next((i for i, line in enumerate(lines) if "-->" in line), -1)
        if index < 0:
            continue
        a, b = lines[index].split("-->", 1)
        start, end = parse_vtt_time(a.strip()), parse_vtt_time(b.strip().split()[0])
        text = html.unescape(" ".join(lines[index + 1:])).strip()
        cues.append((start, end, text))
    return cues


def parse_vtt_time(text: str) -> int:
    m = VTT_TIME.fullmatch(text)
    if not m:
        raise ValueError(f"Invalid caption clock {text!r}")
    return ((int(m['h']) * 3600 + int(m['m']) * 60 + int(m['s'])) * 1000 + int(m['ms']))


def validate_audio_captions(job: Path, manifest: dict[str, Any], report: Report, manifest_sha: str | None = None) -> None:
    alignment_file = job / "audio_alignment.json"
    captions_file = job / "captions.vtt"
    mix_file = job / "narration_mix.wav"
    for f in (alignment_file, captions_file, mix_file):
        if not f.is_file():
            report.check(False, "M4D_MISSING", f"Missing M4-D artifact {f.name}")
            return
    alignment = read_json(alignment_file)
    report.check(alignment.get("schemaVersion") == "blueprint.audio-alignment.v1", "AUDIO_SCHEMA", "Wrong M4-D alignment schema")
    if manifest_sha is not None:
        report.check(alignment.get("manifestSha256") == manifest_sha, "AUDIO_MANIFEST_HASH",
                     "Audio alignment is not tied to this manifest digest",
                     expected=manifest_sha, actual=alignment.get("manifestSha256"))
    report.check(alignment.get("totalFrames") == FRAMES and alignment.get("fps") == FPS, "AUDIO_TIMING", "M4-D timing mismatch")
    report.check(alignment.get("sampleRate") == 48000, "AUDIO_SAMPLE_RATE", "Narration mix sample rate mismatch")
    rows = alignment.get("shots", [])
    shots = manifest.get("shots", [])
    report.check(len(rows) == len(shots) == 14, "AUDIO_SHOTS", "Expected 14 narration alignment records")
    for i, row in enumerate(rows):
        if i >= len(shots):
            break
        planned = shots[i]
        report.check(row.get("code") == planned.get("code") and row.get("startFrame") == planned.get("startFrame"),
                     "AUDIO_SHOT_DRIFT", f"Narration cue drift on shot {i+1}")
        report.check(row.get("wavPresent") is True, "VOICE_MISSING", f"Narration WAV missing for {planned.get('code')}")
        voice_digest = row.get("sha256")
        relative = row.get("relativePath") or f"narration/{planned.get('code')}.wav"
        if isinstance(voice_digest, str) and re.fullmatch(r"[a-f0-9]{64}", voice_digest):
            voice = (job / relative).resolve()
            if job.resolve() not in voice.parents or not voice.is_file():
                report.check(False, "VOICE_HASH", f"Narration WAV missing for hash check {planned.get('code')}",
                             expected=voice_digest, actual=None, shot_id=planned.get("shotId"))
            else:
                actual_voice = sha256_file(voice)
                report.check(actual_voice == voice_digest, "VOICE_HASH",
                             f"Narration WAV bytes changed for {planned.get('code')}",
                             expected=voice_digest, actual=actual_voice, shot_id=planned.get("shotId"))
        elif row.get("wavPresent") is True:
            report.check(False, "VOICE_HASH", f"Narration WAV for {planned.get('code')} has no digest",
                         shot_id=planned.get("shotId"))
    try:
        cues = parse_vtt(captions_file)
    except ValueError as exc:
        report.check(False, "VTT_PARSE", str(exc))
        return
    report.check(len(cues) == len(shots) == 14, "CAPTION_COUNT", "Expected 14 caption cues")
    for i, (start, end, words) in enumerate(cues):
        if i >= len(shots):
            break
        shot = shots[i]
        a = int(shot["startFrame"] * 1000 / FPS)
        b = int(shot["endFrameExclusive"] * 1000 / FPS)
        report.check(abs(start - a) <= 20 and 0 < end - start <= b - a,
                     "CAPTION_TIMING", f"Caption timing differs on {shot['code']}")
        expected_text = str(shot.get("narration", "")).strip()
        report.check(" ".join(words.split()) == " ".join(expected_text.split()),
                     "CAPTION_WORDS", f"Caption content differs on {shot['code']}")
        if i + 1 < len(cues):
            report.check(end <= cues[i+1][0], "CAPTION_OVERLAP", f"Caption overlap after {shot['code']}")


def pcm_decode(path: Path) -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("numpy is required for audio correlation: pip install numpy") from exc
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "2000", "-f", "s16le", "pipe:1"]
    p = subprocess.run(cmd, capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"FFmpeg PCM decode failed for {path.name}: {p.stderr[-300:]!r}")
    return np.frombuffer(p.stdout, dtype="<i2").astype(np.float32)


def validate_audio_waveform(job: Path, candidate: Path, manifest: dict[str, Any], report: Report) -> None:
    """Content-based A/V offset proof: compare M4-D mixed WAV to decoded AAC.

    This detects systematic shifts, not semantic narration transcription.
    Deliberate silent sections must be handled by approved shot-level exceptions.
    """
    import numpy as np
    source = pcm_decode(job / "narration_mix.wav")
    encoded = pcm_decode(candidate)
    peak = float(np.max(np.abs(encoded))) if len(encoded) else 0.0
    report.check(peak <= 32760.0, "AUDIO_CLIPPING", "Decoded narration is clipped", evidence=peak, actual=peak)
    offsets: list[float] = []
    for shot in manifest.get("shots", []):
        start = int(shot["startFrame"] / FPS * 2000)
        length = int(shot["durationFrames"] / FPS * 2000)
        # Test a 1-second window from inside each authored shot, not silence-prone boundary.
        a = start + max(0, (length - 2000) // 2)
        n = min(2000, length)
        if a+n >= min(len(source),len(encoded)):
            report.check(False, "AUDIO_PCM_SHORT", f"PCM too short for {shot['code']}")
            continue
        window = source[a:a+n]
        if float(np.std(window)) < 30.0:
            report.check(False, "AUDIO_PCM_SILENT", f"No usable speech evidence for {shot['code']}")
            continue
        pad = 350 # +/-175 ms; detect shifts beyond allowed one-frame limit
        lo = max(0, a-pad)
        hi = min(len(encoded), a+n+pad)
        choices = encoded[lo:hi]
        if len(choices) < n:
            report.check(False, "AUDIO_PCM_SHORT", f"Audio window truncated {shot['code']}")
            continue
        window = window - float(window.mean())
        windows = np.lib.stride_tricks.sliding_window_view(choices, n)
        numerators = windows @ window
        denom = (np.linalg.norm(windows, axis=1) * np.linalg.norm(window)) + 1e-9
        correlations = numerators / denom
        best_index = int(np.argmax(correlations))
        best = float(correlations[best_index])
        shift = (lo + best_index - a) / 2000.0
        offsets.append(shift)
        report.check(best >= .75, "AUDIO_PCM_CONFIDENCE", f"Low decoded audio match {shot['code']}", evidence=best)
        report.check(abs(shift) <= 1/FPS, "AUDIO_OFFSET", f"Narration displaced by >1 frame {shot['code']}", evidence=shift)
    report.check(len(offsets) == 14, "AUDIO_PCM_COVERAGE", "Could not correlate all 14 narration shots")
    report.metrics["audioOffsetsSeconds"] = offsets


def run_qc(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    job = args.job_dir.resolve()
    report = Report()
    manifest_path = job / "render_manifest.json"
    digest_path = job / "render_manifest.sha256"
    if not manifest_path.is_file() or not digest_path.is_file():
        raise RuntimeError("Missing sealed manifest and sidecar")
    digest = sha256_file(manifest_path)
    sidecar = digest_path.read_text().strip().lower()
    report.check(sidecar == digest, "MANIFEST_HASH", "Manifest SHA-256 sidecar mismatch", expected=digest, actual=sidecar)
    manifest, stage, rig, face = map(read_json, (manifest_path, args.stage_plan, args.rig_contract, args.face_contract))
    canonical = (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    canonical_digest = hashlib.sha256(canonical).hexdigest()
    report.check(manifest_path.read_bytes() == canonical, "MANIFEST_CANONICAL",
                 "Sealed manifest bytes are not canonical JSON", expected=canonical_digest, actual=digest)
    stage_digest = sha256_file(args.stage_plan)
    report.check(manifest.get("stagePlanSha256") == stage_digest, "STAGE_SHA", "Stage plan digest mismatch",
                 expected=stage_digest, actual=manifest.get("stagePlanSha256"))
    actions = validate_timeline(manifest, stage, report)
    production = manifest.get("production", {})
    report.check(isinstance(production, dict) and len(production.get("requiredMorphNames", [])) == 22,
                 "PRODUCTION_REGISTRY", "Missing complete 22-channel production binding")
    if isinstance(production, dict):
        report.check(set(production.get("requiredActionIds", [])) == actions,
                     "PRODUCTION_ACTIONS", "Production manifest has incomplete action registry")
        report.check(set(production.get("requiredMorphNames", [])) == {r["name"] for r in face.get("channels", [])},
                     "PRODUCTION_MORPHS", "Production manifest has wrong morph identities")
        report.check(set(production.get("requiredBoneNames", [])) == set(rig.get("requiredBones", [])),
                     "PRODUCTION_BONES", "Production manifest has wrong skeleton identities")
        report.check(bool(re.fullmatch(r"[a-f0-9]{64}", str(production.get("rigSha256", "")))),
                     "PRODUCTION_RIG_SHA", "Missing pinned rig digest")
        report.check(bool(re.fullmatch(r"[a-f0-9]{64}", str(production.get("ownerApprovalReceiptSha256", "")))),
                     "OWNER_STAGE_RECEIPT", "Missing stage/rig approval receipt digest")
        validate_contract_hashes(production, {
            "rig": args.rig_contract,
            "face": args.face_contract,
            "actions": args.actions_contract,
            "lighting": getattr(args, "lighting_contract", None),
        }, report)
        approval_file = job / "owner_stage_approval.json"
        report.check(approval_file.is_file() and sha256_file(approval_file) == production.get("ownerApprovalReceiptSha256"),
                     "OWNER_STAGE_RECEIPT_FILE", "Stage approval receipt missing or modified")
        cap_file = job / "engine_capabilities.json"
        cap_digest = sha256_file(cap_file) if cap_file.is_file() else None
        report.check(cap_file.is_file() and cap_digest == production.get("engineCapabilitiesSha256"),
                     "ENGINE_CAPABILITIES", "Pre-manifest Godot capabilities receipt missing or modified",
                     expected=production.get("engineCapabilitiesSha256"), actual=cap_digest)
        if cap_file.is_file():
            capabilities = read_json(cap_file)
            report.check("manifestSha256" not in capabilities, "CAPABILITIES_CYCLE",
                         "engine_capabilities.json must not contain the manifest digest")
    validate_staged_assets(job, manifest, report)
    registry = read_json(args.actions_contract).get("actionRegistry", {})
    report.check(set(registry) == actions and len(actions) == 34, "REGISTRY", "Action registry does not match stage plan")
    engine_file = job / "engine_preflight.json"
    if engine_file.is_file():
        validate_engine(read_json(engine_file), digest, rig, face, actions, report, manifest)
    else:
        report.check(False, "ENGINE_REPORT", "Godot engine preflight evidence missing")
    validate_godot_log(job, report)
    validate_frame_index(job / "render_frame_index.json", report)
    validate_trace(job / "render_trace.jsonl", manifest, report)
    candidate = job / "pilot-candidate.mp4"
    validate_video(candidate, report)
    validate_audio_captions(job, manifest, report, digest)
    if candidate.is_file() and (job / "narration_mix.wav").is_file():
        try:
            validate_audio_waveform(job, candidate, manifest, report)
        except (RuntimeError, ValueError, ImportError) as exc:
            report.check(False, "AUDIO_PCM", str(exc))
    blockers = [f for f in report.findings if f["severity"] == "BLOCKER"]
    status = "FAIL" if blockers else "TECHNICAL_PASS_OWNER_APPROVAL_PENDING"
    payload = {"schemaVersion": "blueprint.production-qc.v1", "status": status,
               "manifestSha256": digest, "findings": report.findings,
               "metrics": report.metrics,
               "humanReviewRequired": True,
               "automatedVisualComparisonImplemented": False,
               "approvedForFinalPromotion": False}
    return payload, (2 if blockers else 0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job-dir", type=Path, required=True)
    p.add_argument("--stage-plan", type=Path, required=True)
    p.add_argument("--rig-contract", type=Path, required=True)
    p.add_argument("--face-contract", type=Path, required=True)
    p.add_argument("--actions-contract", type=Path, required=True)
    p.add_argument("--lighting-contract", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args(argv)
    out = args.report or args.job_dir / "qc_report.json"
    try:
        result, code = run_qc(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        result = {"schemaVersion": "blueprint.production-qc.v1", "status": "FAIL",
                  "findings": [{"severity": "BLOCKER", "code": "QC_FATAL", "message": str(exc)}],
                  "approvedForFinalPromotion": False}
        code = 3
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"QC: {result['status']} | {len(result.get('findings', []))} findings | {out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
