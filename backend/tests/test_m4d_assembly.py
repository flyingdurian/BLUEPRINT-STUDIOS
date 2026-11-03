from __future__ import annotations

import hashlib
import json
import math
import struct
import uuid
import wave
from pathlib import Path

from app.services.audio_assembler import AudioAssemblyError, align_narration
from app.services.ffmpeg_assembly import caption_cues, write_captions
from app.services.ffmpeg_bin import find_tool, run_tool

PROJECT_ID = "blueprint-pilot-01"


def write_tone(path: Path, seconds: float, frequency: float = 440.0) -> None:
    rate = 48000
    count = max(int(seconds * rate), 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for index in range(count):
            sample = int(6000 * math.sin(2 * math.pi * frequency * index / rate))
            frames.extend(struct.pack("<h", sample))
        handle.writeframes(frames)


def write_manifest(job: Path, shots: list[tuple[str, int, str]], *, project_id: str = PROJECT_ID) -> dict:
    fps = 30
    cursor = 0
    rows = []
    for index, (code, frames, narration) in enumerate(shots, start=1):
        rows.append({
            "shotId": f"shot-{index:03d}",
            "code": code,
            "startFrame": cursor,
            "durationFrames": frames,
            "endFrameExclusive": cursor + frames,
            "narration": narration,
        })
        cursor += frames
    manifest = {
        "schemaVersion": "blueprint.render-manifest.v1",
        "quality": "previs",
        "projectId": project_id,
        "revision": 5,
        "fps": fps,
        "width": 540,
        "height": 960,
        "totalFrames": cursor,
        "productionLocked": False,
        "shots": rows,
    }
    raw = (json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    job.mkdir(parents=True, exist_ok=True)
    (job / "render_manifest.json").write_bytes(raw)
    (job / "render_manifest.sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n", encoding="utf-8")
    return manifest


def write_silent_movie(path: Path, seconds: float) -> None:
    run_tool(find_tool("ffmpeg"), [
        "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=0x101820:s=540x960:r=30:d={seconds}",
        "-c:v", "libtheora", "-q:v", "6", str(path),
    ])


def test_missing_narration_fails_before_mixing(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_RENDER_JOBS_ROOT", str(tmp_path))
    job = tmp_path / str(uuid.uuid4())
    write_manifest(job, [("SH_001", 15, "First line."), ("SH_002", 15, "Second line.")])
    try:
        align_narration(job.name)
    except AudioAssemblyError as exc:
        assert "SH_001" in str(exc) and "SH_002" in str(exc)
    else:
        raise AssertionError("missing narration was accepted")
    assert not (job / "narration_mix.wav").exists()


def test_fourteen_shot_pilot_timing_is_aligned(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_RENDER_JOBS_ROOT", str(tmp_path))
    plan = json.loads((Path(__file__).resolve().parents[2] / "docs" / "examples" / "BS-M4-PILOT-STAGE-PLAN.json").read_text(encoding="utf-8"))
    shots = [(row["code"], row["durationFrames"], row["narration"]) for row in plan["shots"]]
    job = tmp_path / str(uuid.uuid4())
    write_manifest(job, shots)
    for code, _frames, _narration in shots:
        write_tone(job / "narration" / f"{code}.wav", 0.2, 330 + len(code))
    alignment = align_narration(job.name)
    assert alignment["totalFrames"] == 2490
    assert alignment["durationSeconds"] == 83.0
    assert len(alignment["shots"]) == 14
    assert alignment["shots"][0]["startSeconds"] == 0
    assert alignment["shots"][1]["startSeconds"] == 4
    assert alignment["shots"][-1]["code"] == "SH_014"
    assert alignment["shots"][-1]["startSeconds"] == 77
    assert abs(alignment["mixedDurationSeconds"] - 83.0) < 0.05
    cues = caption_cues(json.loads((job / "render_manifest.json").read_text(encoding="utf-8")))
    assert cues[0][0] == 0
    assert cues[1][0] == 4000
    assert cues[0][1] == 3999
    assert cues[-1][0] == 77000


def test_assemble_muxes_audio_and_burned_captions(client, tmp_path, monkeypatch):
    api, _db_file = client
    monkeypatch.setenv("BLUEPRINT_RENDER_JOBS_ROOT", str(tmp_path / "jobs"))
    created = api.post("/api/projects", json={"id": PROJECT_ID, "name": "Pilot 1", "fps": 30})
    assert created.status_code == 201, created.text
    before = api.get(f"/api/projects/{PROJECT_ID}/snapshot").json()["revision"]
    job_id = str(uuid.uuid4())
    job = tmp_path / "jobs" / job_id
    manifest = write_manifest(job, [("SH_001", 15, "You mute the chat."), ("SH_002", 15, "You sip tea & look.")])
    write_tone(job / "narration" / "SH_001.wav", 0.4, 440)
    write_tone(job / "narration" / "SH_002.wav", 0.8, 550)
    write_silent_movie(job / "pilot-previs.ogv", 1.0)
    assembled = api.post(f"/api/projects/{PROJECT_ID}/renders/{job_id}/assemble", json={"burnCaptions": True})
    assert assembled.status_code == 201, assembled.text
    body = assembled.json()
    assert body["audioStatus"] == "aligned"
    assert body["tracksPresent"] == 2
    assert body["burnedCaptions"] is True
    assert body["previewUrl"].endswith("/pilot-preview.mp4")
    assert body["downloadUrl"].endswith("/pilot-final.mp4")
    preview = api.get(body["previewUrl"])
    final = api.get(body["downloadUrl"])
    captions = api.get(body["captionsUrl"])
    assert preview.status_code == 200 and preview.content[4:8] == b"ftyp"
    assert final.status_code == 200 and "attachment" in final.headers["content-disposition"]
    assert b"You mute the chat." in captions.content
    assert b"tea &amp; look." in captions.content
    probed = json.loads(run_tool(find_tool("ffprobe"), [
        "-v", "error", "-show_entries", "stream=codec_name,width,height",
        "-show_entries", "format=duration", "-of", "json", str(job / "pilot-final.mp4"),
    ]))
    codecs = {stream["codec_name"] for stream in probed["streams"]}
    assert codecs == {"h264", "aac"}
    video = next(stream for stream in probed["streams"] if stream["codec_name"] == "h264")
    assert (video["width"], video["height"]) == (540, 960)
    assert abs(float(probed["format"]["duration"]) - 1.0) < 0.05
    after = api.get(f"/api/projects/{PROJECT_ID}/snapshot").json()["revision"]
    assert after == before
    write_captions(job, manifest)
    assert (job / "captions.srt").is_file()
