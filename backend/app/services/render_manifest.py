"""Freeze a read-only Pilot 1 render job. This does not launch Godot or mutate the graph."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .media_store import blob_file, media_root, relative_blob_path

SCHEMA_VERSION = "blueprint.render-manifest.v1"
PLAN_SCHEMA = "blueprint.shotstageplan.v1"
TOTAL_FRAMES = 2490
FPS = 30
STAGE_SIZE = (540, 960)
PROOF_SHA256 = "7d0dafde014627adfb2f35ab9cc434a67ec1fa8918a3c16b29a0db023c327491"
MEDIA_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "model/gltf-binary": ".glb",
    "model/gltf+json": ".gltf",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/webm": ".webm",
}


class ManifestCompileError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def default_plan_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "examples" / "BS-M4-PILOT-STAGE-PLAN.json"


def default_jobs_root() -> Path:
    override = os.getenv("BLUEPRINT_RENDER_JOBS_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "data" / "renders" / "jobs"


def proof_png_path() -> Path:
    return Path(__file__).resolve().parents[3] / "godot_render" / "proof" / "pinned_phone.png"


def compile_render_manifest(db: Session, project_id: str, *, quality: str = "previs", allow_proxy: bool = False,
                            plan_path: Path | None = None, jobs_root: Path | None = None,
                            job_id: str | None = None) -> dict[str, object]:
    """Resolve pinned versions against the media library and write one immutable job bundle."""
    if quality not in {"previs", "production"}:
        raise ManifestCompileError("Quality must be previs or production")
    plan_file = plan_path or default_plan_path()
    plan, plan_sha = _load_plan(plan_file)
    project = db.get(m.Project, project_id)
    if project is None:
        raise ManifestCompileError("Project not found", 404)
    if project.fps != FPS:
        raise ManifestCompileError("Pilot previs requires a 30 fps project")
    shots = list(db.scalars(select(m.Shot).where(m.Shot.project_id == project_id).order_by(m.Shot.start_frame)))
    _assert_database_matches_plan(db, project_id, shots, plan)
    if quality == "production":
        raise ManifestCompileError(_production_block_reason(plan))
    if quality == "previs" and not allow_proxy:
        # Checked again per asset so a missing file cannot be silently omitted.
        pass
    planned_by_id = {item["shotId"]: item for item in plan["shots"]}
    resolved = [_resolve_shot(db, shot, planned_by_id[shot.id]) for shot in _ordered(shots)]
    unresolved = sum(1 for shot in resolved for asset in shot["assets"] if not asset["verified"])
    if unresolved and not allow_proxy:
        missing = next(asset for shot in resolved for asset in shot["assets"] if not asset["verified"])
        raise ManifestCompileError(
            f"Pinned asset {missing['assetId']} v{missing['pinnedVersion']} has no verified media blob")
    root = jobs_root or default_jobs_root()
    job = job_id or str(uuid.uuid4())
    job_dir = root / job
    job_dir.mkdir(parents=True, exist_ok=False)
    try:
        for shot in resolved:
            for asset in shot["assets"]:
                if asset["verified"]:
                    _stage_verified(asset, job_dir)
        stand_in = None
        if allow_proxy:
            stand_in = _stage_stand_in(job_dir)
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "quality": quality,
            "projectId": project.id,
            "revision": project.revision,
            "fps": FPS,
            "width": STAGE_SIZE[0],
            "height": STAGE_SIZE[1],
            "totalFrames": TOTAL_FRAMES,
            "quitAfterFrame": TOTAL_FRAMES,
            "stagePlanSha256": plan_sha,
            "stagePlanStatus": "DRAFT_UNMAPPED",
            "productionLocked": False,
            "proxy": bool(allow_proxy and unresolved),
            "standIn": stand_in,
            "shots": resolved,
        }
        encoded = _canonical_bytes(manifest)
        manifest_path = job_dir / "render_manifest.json"
        manifest_path.write_bytes(encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        (job_dir / "render_manifest.sha256").write_text(digest + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    try:
        relative = manifest_path.resolve().relative_to(Path(__file__).resolve().parents[3]).as_posix()
    except ValueError:
        relative = manifest_path.as_posix()
    return {
        "job_id": job,
        "project_id": project.id,
        "revision": project.revision,
        "manifest_path": manifest_path,
        "manifest_relative_path": relative,
        "manifest_sha256": digest,
        "frame_count": TOTAL_FRAMES,
        "shot_count": len(resolved),
        "unresolved_count": unresolved,
        "stand_in": stand_in is not None,
        "quality": quality,
    }


def _canonical_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _load_plan(path: Path) -> tuple[dict, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ManifestCompileError(f"Stage plan is not readable: {path}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestCompileError("Stage plan is not valid JSON") from exc
    if plan.get("schemaVersion") != PLAN_SCHEMA:
        raise ManifestCompileError("Unsupported stage plan schema")
    if plan.get("fps") != FPS or plan.get("totalFrames") != TOTAL_FRAMES:
        raise ManifestCompileError("Stage plan must cover exactly 2490 frames at 30 fps")
    shots = plan.get("shots")
    if not isinstance(shots, list) or len(shots) != 14:
        raise ManifestCompileError("Stage plan must contain the 14 Pilot 1 shots")
    ordered = sorted(shots, key=lambda shot: int(shot.get("startFrame", -1)))
    cursor = 0
    seen: set[str] = set()
    for shot in ordered:
        start = int(shot.get("startFrame", -1))
        duration = int(shot.get("durationFrames", -1))
        end = int(shot.get("endFrameExclusive", -1))
        shot_id = str(shot.get("shotId", ""))
        if shot_id in seen:
            raise ManifestCompileError(f"Duplicate shot in stage plan: {shot_id}")
        seen.add(shot_id)
        if start != cursor or duration < 1 or end != start + duration:
            raise ManifestCompileError("Stage plan shots overlap, leave a gap, or disagree with their durations")
        performance = shot.get("performance") or {}
        if performance.get("status") != "DRAFT_UNMAPPED":
            raise ManifestCompileError("Only the draft stage plan can be frozen by this compiler")
        cursor = end
    if cursor != TOTAL_FRAMES:
        raise ManifestCompileError("Stage plan does not end at frame 2490")
    plan["shots"] = ordered
    return plan, digest


def _production_block_reason(plan: dict) -> str:
    approvals = {shot.get("stageApproval") for shot in plan["shots"]}
    return (
        "Production quality is blocked: stage approval is "
        f"{', '.join(sorted(str(item) for item in approvals))}, performances are DRAFT_UNMAPPED, "
        "and the M4-D/E rig-action and narration renderers are not part of this compiler"
    )


def _assert_database_matches_plan(db: Session, project_id: str, shots: list[m.Shot], plan: dict) -> None:
    by_id = {shot.id: shot for shot in shots}
    if len(by_id) != len(shots) or len(shots) != 14:
        raise ManifestCompileError("Project must contain exactly the 14 original Pilot 1 shots")
    for planned in plan["shots"]:
        shot = by_id.get(planned["shotId"])
        if shot is None:
            raise ManifestCompileError(f"Project is missing {planned['shotId']}")
        if shot.code != planned["code"] or shot.start_frame != planned["startFrame"] or shot.duration_frames != planned["durationFrames"]:
            raise ManifestCompileError(f"{shot.code} timing or code does not match the stage plan")
        if shot.narration != planned["narration"]:
            raise ManifestCompileError(f"{shot.code} narration does not match the stage plan")
        links = list(db.scalars(select(m.ShotAssetLink).where(m.ShotAssetLink.shot_id == shot.id)))
        pinned = {link.asset_id for link in links}
        expected = set(planned.get("linkedAssetIds") or [])
        if pinned != expected:
            extra = sorted(pinned - expected)
            missing = sorted(expected - pinned)
            raise ManifestCompileError(
                f"{shot.code} pins do not match the stage plan (undeclared {extra or '-'}, missing {missing or '-'})")
        for link in links:
            version = db.get(m.AssetVersion, (link.asset_id, link.pinned_version))
            asset = db.get(m.Asset, link.asset_id)
            if version is None or asset is None or asset.project_id != project_id:
                raise ManifestCompileError(f"Broken pin {link.asset_id} v{link.pinned_version} on {shot.code}")


def _ordered(shots: list[m.Shot]) -> list[m.Shot]:
    return sorted(shots, key=lambda shot: shot.start_frame)


def _resolve_shot(db: Session, shot: m.Shot, planned: dict) -> dict:
    assets = []
    for asset_id in planned["linkedAssetIds"]:
        link = db.get(m.ShotAssetLink, (shot.id, asset_id))
        if link is None:
            raise ManifestCompileError(f"Broken reference {asset_id} on {shot.code}")
        assets.append(_resolve_asset(db, link))
    performance = planned["performance"]
    return {
        "shotId": shot.id,
        "code": shot.code,
        "startFrame": shot.start_frame,
        "durationFrames": shot.duration_frames,
        "endFrameExclusive": shot.start_frame + shot.duration_frames,
        "narration": shot.narration,
        "setKey": planned["setKey"],
        "camera": planned["camera"],
        "performance": {
            "actionIds": list(performance.get("actionIds") or []),
            "requiredBindings": list(performance.get("requiredBindings") or []),
            "status": performance.get("status"),
            "execute": False,
        },
        "overlayCue": planned.get("overlayCue"),
        "assets": assets,
    }


def _resolve_asset(db: Session, link: m.ShotAssetLink) -> dict:
    version = db.get(m.AssetVersion, (link.asset_id, link.pinned_version))
    asset = db.get(m.Asset, link.asset_id)
    if version is None or asset is None:
        raise ManifestCompileError(f"Broken pin {link.asset_id} v{link.pinned_version}")
    _assert_safe_relative(version.relative_path, f"{link.asset_id} version path")
    base = {
        "assetId": asset.id,
        "name": asset.name,
        "pinnedVersion": link.pinned_version,
        "verified": False,
        "sha256": None,
        "resolution": "UNRESOLVED_PROXY",
        "relativePath": None,
        "mediaType": None,
    }
    digest = version.blob_sha256
    if not digest:
        return base
    if version.sha256 and version.sha256 != digest:
        raise ManifestCompileError(f"{asset.id} v{version.version} hash does not match its media blob")
    blob = db.get(m.MediaBlob, digest)
    if blob is None:
        raise ManifestCompileError(f"{asset.id} v{version.version} points at a missing media blob")
    _assert_safe_relative(blob.relative_path, f"{asset.id} blob path")
    if blob.relative_path != relative_blob_path(digest):
        raise ManifestCompileError(f"{asset.id} blob path is not the content-addressed library path")
    source = _verified_blob_file(digest)
    extension = MEDIA_EXTENSIONS.get(blob.media_type)
    if extension is None:
        raise ManifestCompileError(f"{asset.id} media type cannot be staged")
    base.update({
        "verified": True,
        "sha256": digest,
        "resolution": "VERIFIED_BLOB",
        "relativePath": f"media/{digest}{extension}",
        "mediaType": blob.media_type,
        "_source": str(source),
    })
    return base


def _verified_blob_file(digest: str) -> Path:
    root = media_root().resolve()
    source = blob_file(digest).resolve()
    if root not in source.parents:
        raise ManifestCompileError("Media blob path escapes the media library")
    if not source.is_file():
        raise ManifestCompileError(f"Media blob {digest} is not on disk")
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != digest:
        raise ManifestCompileError(f"Media blob {digest} does not match its bytes and was not overwritten")
    return source


def _stage_verified(asset: dict, job_dir: Path) -> None:
    source = Path(str(asset.pop("_source")))
    destination = job_dir / str(asset["relativePath"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != asset["sha256"]:
        raise ManifestCompileError(f"Staged copy of {asset['assetId']} failed the second digest check")


def _stage_stand_in(job_dir: Path) -> dict:
    source = proof_png_path()
    if hashlib.sha256(source.read_bytes()).hexdigest() != PROOF_SHA256:
        raise ManifestCompileError("M4-B stand-in fixture failed its digest check")
    relative = f"media/{PROOF_SHA256}.png"
    destination = job_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != PROOF_SHA256:
        raise ManifestCompileError("Staged stand-in failed the second digest check")
    return {
        "role": "timing-proxy",
        "label": "M4-B smartphone proof fixture",
        "sha256": PROOF_SHA256,
        "relativePath": relative,
        "verified": True,
        "mediaType": "image/png",
    }


def _assert_safe_relative(value: str | None, label: str) -> None:
    if value is None:
        return
    normalized = value.replace("\\", "/")
    if not normalized or normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
        raise ManifestCompileError(f"{label} escapes the media library")
