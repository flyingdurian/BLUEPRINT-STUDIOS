#!/usr/bin/env python3
"""Check that a Pilot 1 previs movie is 2490 frames, 30 fps, 540x960, and 83 seconds."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

EXPECTED_FPS = 30
EXPECTED_FRAMES = 2490
EXPECTED_SIZE = (540, 960)
EXPECTED_SECONDS = 83.0


def find_ffprobe() -> str | None:
    """Find ffprobe even when this process inherited a PATH from before the install."""
    found = shutil.which("ffprobe")
    if found:
        return found
    if sys.platform != "win32":
        return None
    import winreg

    locations = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    for hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                raw, _kind = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        for entry in str(raw).split(";"):
            candidate = pathlib.Path(os.path.expandvars(entry.strip())) / "ffprobe.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def verify(video_path: pathlib.Path) -> None:
    if not video_path.is_file() or video_path.stat().st_size <= 10_000:
        raise RuntimeError("Video missing or empty")
    probe = find_ffprobe()
    if not probe:
        raise RuntimeError("ffprobe is required. Install FFmpeg and add it to PATH.")
    command = [
        probe, "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
        "-show_entries", "format=duration", "-of", "json", str(video_path),
    ]
    data = json.loads(subprocess.check_output(command, text=True, timeout=180))
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError("No decodable video stream")
    stream = streams[0]
    frames = int(stream["nb_read_frames"])
    width, height = int(stream["width"]), int(stream["height"])
    numerator, denominator = (int(part) for part in stream["r_frame_rate"].split("/"))
    actual_fps = numerator / denominator
    duration = float(data["format"]["duration"])
    if frames != EXPECTED_FRAMES:
        raise RuntimeError(f"Frame count must be 2490, got {frames}")
    if abs(actual_fps - EXPECTED_FPS) >= 0.01:
        raise RuntimeError(f"Expected 30 FPS, got {actual_fps}")
    if (width, height) != EXPECTED_SIZE:
        raise RuntimeError(f"Unexpected dimensions: {(width, height)}")
    if abs(duration - EXPECTED_SECONDS) >= 0.05:
        raise RuntimeError(f"Expected 83.000 s, got {duration:.3f} s")
    print(f"PASS: {frames} frames at {actual_fps:g} FPS, {width}x{height}, {duration:.3f}s")


if __name__ == "__main__":
    target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "")
    try:
        verify(target.resolve())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
