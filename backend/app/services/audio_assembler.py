"""Align one narration WAV to each shot in a frozen render manifest and mix them."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from .ffmpeg_bin import MediaToolError, find_tool, run_tool
from .render_manifest import default_jobs_root

SCHEMA = "blueprint.render-manifest.v1"
ALIGNMENT_SCHEMA = "blueprint.audio-alignment.v1"
SHOT_CODE = re.compile(r"^SH_\d{3}$")
JOB_ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class AudioAssemblyError(MediaToolError):
    pass


def resolve_job(job_id: str) -> Path:
    if not JOB_ID.fullmatch(job_id or ""):
        raise AudioAssemblyError("Render job not found", 404)
    root = default_jobs_root().resolve()
    job = (root / job_id).resolve()
    if root != job and root not in job.parents:
        raise AudioAssemblyError("Render job not found", 404)
    if not job.is_dir() or not (job / "render_manifest.json").is_file():
        raise AudioAssemblyError("Render job not found", 404)
    return job


def active_job_id(project_id: str) -> str:
    root = default_jobs_root()
    if not root.is_dir():
        raise AudioAssemblyError("No render manifest for this project", 404)
    candidates: list[tuple[float, str]] = []
    for child in root.iterdir():
        if not child.is_dir() or not JOB_ID.fullmatch(child.name):
            continue
        manifest_path = child / "render_manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if payload.get("projectId") != project_id:
            continue
        candidates.append((manifest_path.stat().st_mtime, child.name))
    if not candidates:
        raise AudioAssemblyError("No render manifest for this project", 404)
    return max(candidates)[1]


def load_manifest(job: Path) -> dict:
    manifest_path = job / "render_manifest.json"
    sidecar_path = job / "render_manifest.sha256"
    if not sidecar_path.is_file():
        raise AudioAssemblyError("Render manifest sidecar is missing")
    raw = manifest_path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    expected = sidecar_path.read_text(encoding="utf-8").strip().lower()
    if actual != expected:
        raise AudioAssemblyError("Render manifest hash does not match its sidecar")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AudioAssemblyError("Render manifest is not valid JSON") from exc
    _validate_manifest(manifest)
    return manifest


def _validate_manifest(manifest: dict) -> None:
    if manifest.get("schemaVersion") != SCHEMA:
        raise AudioAssemblyError("Render manifest schema is not supported")
    fps = manifest.get("fps")
    total = manifest.get("totalFrames")
    shots = manifest.get("shots")
    if not isinstance(fps, int) or fps <= 0:
        raise AudioAssemblyError("Render manifest fps must be a positive integer")
    if not isinstance(total, int) or total <= 0:
        raise AudioAssemblyError("Render manifest totalFrames must be a positive integer")
    if not isinstance(shots, list) or not shots:
        raise AudioAssemblyError("Render manifest has no shots")
    cursor = 0
    seen: set[str] = set()
    for shot in shots:
        code = shot.get("code")
        if not isinstance(code, str) or not SHOT_CODE.fullmatch(code) or code in seen:
            raise AudioAssemblyError("Render manifest shot code is invalid")
        seen.add(code)
        start = shot.get("startFrame")
        duration = shot.get("durationFrames")
        end = shot.get("endFrameExclusive")
        if not all(isinstance(value, int) for value in (start, duration, end)):
            raise AudioAssemblyError(f"{code} timing is invalid")
        if start != cursor or duration <= 0 or end != start + duration:
            raise AudioAssemblyError(f"{code} does not continue the timeline")
        if not isinstance(shot.get("narration"), str):
            raise AudioAssemblyError(f"{code} narration is missing")
        cursor = end
    if cursor != total:
        raise AudioAssemblyError("Shot timings do not cover totalFrames")


def narration_wav(job: Path, code: str) -> Path:
    if not SHOT_CODE.fullmatch(code):
        raise AudioAssemblyError("Render manifest shot code is invalid")
    return job / "narration" / f"{code}.wav"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_wav(path: Path) -> None:
    header = path.read_bytes()[:12]
    if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise AudioAssemblyError(f"{path.name} is not a WAV narration track")


def probe_duration(path: Path) -> float:
    raw = run_tool(find_tool("ffprobe"), [
        "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path),
    ])
    try:
        duration = float(json.loads(raw)["format"]["duration"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise AudioAssemblyError(f"Could not read the duration of {path.name}") from exc
    if duration <= 0:
        raise AudioAssemblyError(f"{path.name} has no audio duration")
    return duration


def shot_rows(job: Path, manifest: dict, *, probe: bool) -> list[dict]:
    fps = int(manifest["fps"])
    rows: list[dict] = []
    for shot in manifest["shots"]:
        code = str(shot["code"])
        wav = narration_wav(job, code)
        present = wav.is_file()
        source_seconds = None
        digest = None
        if present and probe:
            _assert_wav(wav)
            source_seconds = probe_duration(wav)
            digest = _sha256(wav)
        elif present:
            _assert_wav(wav)
            digest = _sha256(wav)
        slot = int(shot["durationFrames"]) / fps
        rows.append({
            "code": code,
            "shotId": shot.get("shotId"),
            "startFrame": int(shot["startFrame"]),
            "durationFrames": int(shot["durationFrames"]),
            "startSeconds": int(shot["startFrame"]) / fps,
            "slotSeconds": slot,
            "narration": shot["narration"],
            "wavPresent": present,
            "sourceSeconds": source_seconds,
            "trimmed": bool(source_seconds is not None and source_seconds > slot + 0.02),
            "sha256": digest,
            "relativePath": f"narration/{code}.wav" if present else None,
        })
    return rows


def align_narration(job_id: str) -> dict:
    """Place each shot WAV at that shot's start frame and pad it to the shot length."""
    job = resolve_job(job_id)
    manifest = load_manifest(job)
    rows = shot_rows(job, manifest, probe=True)
    missing = [row["code"] for row in rows if not row["wavPresent"]]
    if missing:
        raise AudioAssemblyError(
            "Narration WAV tracks are missing: " + ", ".join(missing)
            + ". Expected narration/SH_###.wav inside the render job."
        )
    fps = int(manifest["fps"])
    filters: list[str] = []
    labels: list[str] = []
    command = [find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error"]
    for index, row in enumerate(rows):
        command.extend(["-i", str(narration_wav(job, row["code"]))])
        slot = float(row["slotSeconds"])
        label = f"a{index}"
        filters.append(
            f"[{index}]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"atrim=start=0:end={slot:.6f},asetpts=PTS-STARTPTS,apad=whole_dur={slot:.6f}[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(f"{''.join(labels)}concat=n={len(rows)}:v=0:a=1[aout]")
    destination = job / "narration_mix.wav"
    temporary = job / f".narration_mix.{uuid.uuid4().hex}.wav"
    command.extend([
        "-filter_complex", ";".join(filters), "-map", "[aout]", "-c:a", "pcm_s16le", str(temporary),
    ])
    try:
        run_tool(command[0], command[1:], timeout=600)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    expected = int(manifest["totalFrames"]) / fps
    mixed = probe_duration(destination)
    if abs(mixed - expected) > 0.05:
        destination.unlink(missing_ok=True)
        raise AudioAssemblyError(f"Narration mix duration {mixed:.3f}s does not match the manifest {expected:.3f}s")
    alignment = {
        "schemaVersion": ALIGNMENT_SCHEMA,
        "jobId": job_id,
        "projectId": manifest.get("projectId"),
        "fps": fps,
        "totalFrames": int(manifest["totalFrames"]),
        "durationSeconds": expected,
        "mixedDurationSeconds": mixed,
        "sampleRate": 48000,
        "channels": 2,
        "mix": "narration_mix.wav",
        "shots": rows,
    }
    encoded = json.dumps(alignment, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    (job / "audio_alignment.json").write_bytes(encoded)
    return alignment
