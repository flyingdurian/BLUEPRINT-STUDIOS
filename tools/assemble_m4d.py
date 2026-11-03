#!/usr/bin/env python3
"""Mix shot narration WAVs onto a frozen previs job and encode the H.264 MP4."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ffmpeg_assembly import assemble_distribution  # noqa: E402
from app.services.ffmpeg_bin import MediaToolError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble Pilot narration, captions, and an H.264 MP4")
    parser.add_argument("--job-id", default="")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--no-burn", action="store_true")
    args = parser.parse_args()
    job_id = args.job_id
    if args.manifest is not None:
        job_id = args.manifest.resolve().parent.name
    if not job_id:
        print("M4D_ASSEMBLE_FAIL: pass --job-id or --manifest", file=sys.stderr)
        return 1
    try:
        receipt = assemble_distribution(job_id, burn_captions=not args.no_burn)
    except MediaToolError as exc:
        print(f"M4D_ASSEMBLE_FAIL: {exc}", file=sys.stderr)
        return 1
    from app.services.audio_assembler import resolve_job
    final_name = receipt.get("final") or receipt["preview"]
    print(f"M4D_MP4={resolve_job(job_id) / final_name}")
    print(f"M4D_JOB id={job_id} burned={str(receipt['burnedCaptions']).lower()} duration={receipt['durationSeconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
