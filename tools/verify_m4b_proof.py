#!/usr/bin/env python3
"""Verify pinned fixture identity and produced video. stdlib + ffprobe only."""
from __future__ import annotations
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'godot_render'
MANIFEST = PROJECT / 'proof' / 'pinned_asset.json'
EXPECTED_FPS = 30
EXPECTED_FRAMES = 150
EXPECTED_SIZE = (540, 960)


def verify(video_path: pathlib.Path) -> None:
    spec = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert spec['fps'] == EXPECTED_FPS, 'Incorrect manifest FPS'
    assert spec['durationFrames'] == EXPECTED_FRAMES, 'Incorrect manifest length'
    asset = spec['asset']
    assert asset['assetId'] == 'proof-phone' and asset['pinnedVersion'] == 1, 'Wrong test asset/version'
    assert asset['path'] == 'res://proof/pinned_phone.png', 'Unexpected asset path'
    real_path = PROJECT / 'proof' / 'pinned_phone.png'
    assert hashlib.sha256(real_path.read_bytes()).hexdigest() == asset['sha256'], 'Pinned asset digest mismatch'
    assert video_path.is_file() and video_path.stat().st_size > 10_000, 'Video missing or empty'

    probe = shutil.which('ffprobe')
    if not probe:
        raise RuntimeError('ffprobe is required. Install FFmpeg and add it to PATH.')
    cmd = [probe, '-v', 'error', '-count_frames', '-select_streams', 'v:0',
           '-show_entries', 'stream=width,height,r_frame_rate,nb_read_frames',
           '-show_entries', 'format=duration', '-of', 'json', str(video_path)]
    data = json.loads(subprocess.check_output(cmd, text=True, timeout=120))
    streams = data.get('streams') or []
    assert streams, 'No decodable video stream'
    s = streams[0]
    frames = int(s['nb_read_frames'])
    width, height = int(s['width']), int(s['height'])
    fps_num, fps_den = map(int, s['r_frame_rate'].split('/'))
    actual_fps = fps_num / fps_den
    duration = float(data['format']['duration'])
    assert frames == EXPECTED_FRAMES, f'Frame count must be 150, got {frames}'
    assert abs(actual_fps - EXPECTED_FPS) < 0.01, f'Expected 30 FPS, got {actual_fps}'
    assert (width, height) == EXPECTED_SIZE, f'Unexpected dimensions: {(width, height)}'
    assert abs(duration - 5.0) < 0.05, f'Expected 5.000 s, got {duration:.3f} s'
    print(f'PASS: {frames} frames at {actual_fps:g} FPS, {width}x{height}, {duration:.3f}s')
    print(f'PASS: pinned fixture {asset["assetId"]}@v{asset["pinnedVersion"]} sha256={asset["sha256"]}')


if __name__ == '__main__':
    target = (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'renders' / 'bs-m4b' / 'm4b-proof.avi')
    try:
        verify(target.resolve())
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
