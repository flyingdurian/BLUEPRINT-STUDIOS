"""Mux a silent previs movie with the aligned narration mix and caption cues."""
from __future__ import annotations

import json
from pathlib import Path

from .audio_assembler import AudioAssemblyError, align_narration, load_manifest, resolve_job, shot_rows
from .ffmpeg_bin import find_tool, run_tool

PREVIEW_NAME = "pilot-preview.mp4"
FINAL_NAME = "pilot-final.mp4"
CAPTION_STYLE = (
    "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00101820&,"
    "BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=64"
)
PUBLIC_MEDIA = {
    PREVIEW_NAME: "video/mp4",
    FINAL_NAME: "video/mp4",
    "captions.vtt": "text/vtt",
    "narration_mix.wav": "audio/wav",
}


def _clock(milliseconds: int) -> tuple[int, int, int, int]:
    hours, milliseconds = divmod(max(milliseconds, 0), 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return hours, minutes, seconds, milliseconds


def _vtt_time(milliseconds: int) -> str:
    hours, minutes, seconds, millis = _clock(milliseconds)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _srt_time(milliseconds: int) -> str:
    hours, minutes, seconds, millis = _clock(milliseconds)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def caption_cues(manifest: dict) -> list[tuple[int, int, str]]:
    fps = int(manifest["fps"])
    shots = manifest["shots"]
    cues: list[tuple[int, int, str]] = []
    for index, shot in enumerate(shots):
        text = str(shot.get("narration") or "").strip()
        if not text:
            continue
        start = int(round(int(shot["startFrame"]) * 1000 / fps))
        end = int(round(int(shot["endFrameExclusive"]) * 1000 / fps))
        next_start = None
        if index + 1 < len(shots):
            next_start = int(round(int(shots[index + 1]["startFrame"]) * 1000 / fps))
        if next_start is not None and end >= next_start:
            end = next_start - 1
        if end <= start:
            end = start + 1
        cues.append((start, end, text))
    return cues


def write_captions(job: Path, manifest: dict) -> tuple[Path, Path]:
    cues = caption_cues(manifest)
    vtt = ["WEBVTT", ""]
    srt: list[str] = []
    for index, (start, end, text) in enumerate(cues, start=1):
        safe = _escape(text)
        vtt.extend([str(index), f"{_vtt_time(start)} --> {_vtt_time(end)}", safe, ""])
        srt.extend([str(index), f"{_srt_time(start)} --> {_srt_time(end)}", safe, ""])
    vtt_path = job / "captions.vtt"
    srt_path = job / "captions.srt"
    vtt_path.write_text("\n".join(vtt).rstrip() + "\n", encoding="utf-8")
    srt_path.write_text("\n".join(srt).rstrip() + "\n", encoding="utf-8")
    return vtt_path, srt_path


def _encode(job: Path, duration: float, *, burn: bool, output_name: str) -> None:
    silent = job / "pilot-previs.ogv"
    mix = job / "narration_mix.wav"
    if not silent.is_file():
        raise AudioAssemblyError("Silent previs movie pilot-previs.ogv is missing")
    if not mix.is_file():
        raise AudioAssemblyError("Aligned narration mix is missing")
    temporary = job / f".{output_name}.part.mp4"
    command = [
        "-y", "-hide_banner", "-loglevel", "error",
        "-i", silent.name, "-i", mix.name,
    ]
    if burn:
        command.extend(["-vf", f"subtitles=captions.srt:force_style='{CAPTION_STYLE}'"])
    command.extend([
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart", "-t", f"{duration:.3f}",
        temporary.name,
    ])
    try:
        run_tool(find_tool("ffmpeg"), command, cwd=job, timeout=600)
        temporary.replace(job / output_name)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def assemble_distribution(job_id: str, *, burn_captions: bool = True) -> dict:
    """Mix narration, write cues, and encode the H.264 preview and burned delivery file."""
    alignment = align_narration(job_id)
    job = resolve_job(job_id)
    manifest = load_manifest(job)
    write_captions(job, manifest)
    duration = float(alignment["durationSeconds"])
    _encode(job, duration, burn=False, output_name=PREVIEW_NAME)
    final_name = None
    if burn_captions:
        _encode(job, duration, burn=True, output_name=FINAL_NAME)
        final_name = FINAL_NAME
    receipt = {
        "schemaVersion": "blueprint.render-assembly.v1",
        "jobId": job_id,
        "projectId": manifest.get("projectId"),
        "quality": manifest.get("quality"),
        "productionLocked": bool(manifest.get("productionLocked")),
        "burnedCaptions": burn_captions,
        "preview": PREVIEW_NAME,
        "final": final_name,
        "audio": "narration_mix.wav",
        "captions": "captions.vtt",
        "durationSeconds": duration,
    }
    (job / "assembly.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def describe_job(job_id: str) -> dict:
    job = resolve_job(job_id)
    manifest = load_manifest(job)
    rows = shot_rows(job, manifest, probe=False)
    present = sum(1 for row in rows if row["wavPresent"])
    mix_ready = (job / "narration_mix.wav").is_file() and (job / "audio_alignment.json").is_file()
    if present == 0:
        audio_status = "missing"
    elif present < len(rows):
        audio_status = "partial"
    elif mix_ready:
        audio_status = "aligned"
    else:
        audio_status = "ready"
    receipt = {}
    receipt_path = job / "assembly.json"
    if receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            receipt = {}
    fps = int(manifest["fps"])
    stored = []
    if (job / "audio_alignment.json").is_file():
        try:
            stored = json.loads((job / "audio_alignment.json").read_text(encoding="utf-8")).get("shots") or []
        except json.JSONDecodeError:
            stored = []
    stored_by_code = {row.get("code"): row for row in stored if isinstance(row, dict)}
    shots = []
    for row in rows:
        previous = stored_by_code.get(row["code"]) or {}
        shots.append({
            "code": row["code"],
            "shot_id": row["shotId"],
            "start_frame": row["startFrame"],
            "duration_frames": row["durationFrames"],
            "start_seconds": row["startSeconds"],
            "narration": row["narration"],
            "wav_present": row["wavPresent"],
            "source_seconds": previous.get("sourceSeconds"),
        })
    return {
        "job_id": job_id,
        "project_id": manifest.get("projectId"),
        "revision": int(manifest.get("revision") or 0),
        "quality": str(manifest.get("quality") or "previs"),
        "production_locked": bool(manifest.get("productionLocked")),
        "frame_count": int(manifest["totalFrames"]),
        "shot_count": len(rows),
        "duration_seconds": int(manifest["totalFrames"]) / fps,
        "audio_status": audio_status,
        "tracks_present": present,
        "tracks_expected": len(rows),
        "mix_ready": mix_ready,
        "captions_ready": (job / "captions.vtt").is_file(),
        "silent_video_ready": (job / "pilot-previs.ogv").is_file(),
        "preview_ready": (job / PREVIEW_NAME).is_file(),
        "final_ready": (job / FINAL_NAME).is_file(),
        "burned_captions": bool(receipt.get("burnedCaptions")) and (job / FINAL_NAME).is_file(),
        "shots": shots,
    }


def media_file(job_id: str, filename: str) -> tuple[Path, str]:
    media_type = PUBLIC_MEDIA.get(filename)
    if media_type is None:
        raise AudioAssemblyError("Render media was not found", 404)
    job = resolve_job(job_id)
    path = (job / filename).resolve()
    if job.resolve() not in path.parents or not path.is_file():
        raise AudioAssemblyError("Render media was not found", 404)
    return path, media_type
