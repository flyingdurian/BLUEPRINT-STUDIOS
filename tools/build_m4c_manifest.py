#!/usr/bin/env python3
"""Freeze a Pilot 1 previs manifest. Does not launch Godot."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import build_engine, init_database, make_session_factory  # noqa: E402
from app.services.render_manifest import ManifestCompileError, compile_render_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a frozen Pilot 1 render manifest")
    parser.add_argument("--project-id", default="blueprint-pilot-01")
    parser.add_argument("--quality", choices=("previs", "production"), default="previs")
    parser.add_argument("--allow-proxy", action="store_true")
    parser.add_argument("--plan", type=Path, default=None)
    args = parser.parse_args()
    engine = build_engine()
    init_database(engine)
    factory = make_session_factory(engine)
    try:
        with factory() as db:
            result = compile_render_manifest(
                db, args.project_id, quality=args.quality, allow_proxy=args.allow_proxy, plan_path=args.plan)
    except ManifestCompileError as exc:
        print(f"M4C_COMPILE_FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"M4C_MANIFEST={result['manifest_path']}")
    print(
        f"M4C_JOB id={result['job_id']} revision={result['revision']} "
        f"frames={result['frame_count']} unresolved={result['unresolved_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
