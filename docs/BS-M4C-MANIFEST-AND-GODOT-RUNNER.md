# BLUEPRINT STUDIOS — BS-M4-C: Full Pilot Previsualization & Render Manifest Compiler

**Milestone status:** Source handoff. Python integration tests pass against the BS-M2 data model; **Godot 4.7.2 runtime test is required on the owner's computer**. Existing M4-B five-second render remains intact. No 83-second video has been rendered in this package.

## 1. Merge prerequisites and compatibility

- Complete and merge M3. Do not replace live M3 media modules with any older version.
- The compiler reads the existing SQLAlchemy `Project`, `Shot`, `Asset`, `AssetVersion`, `ShotAssetLink` classes directly. It requires a consistent SQLite snapshot, 30 fps, the 14 original shot IDs and timings, and exactly matching pinned links.
- The media resolver currently expects an `AssetVersion.sha256` (or optional `blob_sha256`) plus a `MediaBlob` row and a relative path under `backend/data/media/ab/cd/<sha>` (or `BLUEPRINT_MEDIA_ROOT`). **RECONCILE** this adapter with M3's final `MediaBlob` API/relative-path contract before using real uploads.
- No database schema migration is needed for this phase. In particular, the compiler does not advance versions, repin assets, or mutate live project tables.
- M2.2 transaction service may add a snapshot helper: use its read-only snapshot abstraction if needed, but do not copy stale database records into parallel stores.

## 2. Files added (additive)

```text
backend/app/services/render_manifest.py            # Pure compile-and-stage service
backend/app/api/render_manifests.py                # Optional local API route
backend/tests/test_m4c_manifest.py                # 9 regression tests
godot_render/scripts/RenderManifestReader.gd      # Manifest and SHA gate
godot_render/scripts/PilotDirectorRunner.gd       # Deterministic 14-shot runner
godot_render/scenes/DirectorPilot.tscn            # Dedicated pilot scene
godot_render/proof/pinned_phone.png               # Existing M4-B verified fixture (same bytes)
docs/examples/BS-M4-PILOT-STAGE-PLAN.json         # Authoring plan; not a production-approved rig map
tools/build_m4c_manifest.py                      # Read-only local CLI compiler
tools/run_m4c_pilot.ps1                          # PowerShell movie launcher
tools/verify_m4c_video.py                       # ffprobe technical validation
docs/BS-M4C-MANIFEST-AND-GODOT-RUNNER.md
```

Keep existing `godot_render/scripts/DirectorRunner.gd` and `godot_render/scenes/DirectorProof.tscn` untouched. The **new** `PilotDirectorRunner.gd` performs the multi-shot update; this preserves the previously accepted M4-B proof and makes regressions easier to isolate. If source project uses an alternate project.godot, keep its existing renderer and viewport set to 540×960 for this previs pass.

### Optional FastAPI route registration

In `backend/app/main.py`, add `render_manifests` to the existing router imports and register exactly once alongside the existing routers:

```python
from .api import render_manifests
# inside create_app():
app.include_router(render_manifests.router)
```

`POST /api/projects/blueprint-pilot-01/render-manifests`

```json
{ "quality": "previs", "allowProxy": true }
```

Returns `jobId`, project revision, `manifestRelativePath`, frame count, and unresolved/stand-in status. **This API only freezes a job bundle; it does NOT launch Godot or start the render queue.** Do not expose the API beyond loopback.

## 3. Manifest rules and locking

Output folder (generated; Git-ignored):

```text
data/renders/jobs/<job-uuid>/
├── render_manifest.json
├── render_manifest.sha256
├── media/<sha256>.png
├── media/<sha256>.glb  [if uploaded]
└── pilot-previs.ogv    [after Movie Maker]
```

- A job binds the project **revision** and the exact stage-plan source SHA-256.
- Each shot binds stable `shotId`, `code`, `startFrame`, `durationFrames`, `endFrameExclusive`, `camera`, `setKey`, `performance`, and `narration`.
- Every linked asset references the precise `assetId`, `pinnedVersion` and (when present) a SHA-256 verified physical file staged into the job folder, with a second post-copy digest check.
- The manifest itself is canonicalized and hashed; Godot validates `render_manifest.sha256` and every staged dependency before starting.
- Missing legacy versions **may not** acquire fake file hashes. In `previs --allow-proxy`, such dependencies are explicitly represented as `verified=false`, `sha256=null`, `resolution=UNRESOLVED_PROXY`; only the visual stand-in PNG is real and verified. This renders a timing/shot-transition diagnostic animatic, NOT the actual film artwork.
- Hash mismatch, external paths, obsolete/overlapping shot plans, broken references or undeclared shot assets ALWAYS fail—even with proxies enabled.
- Production quality requires stageApproval=APPROVED, mapped actions, verified asset versions, a verified visual adapter, and actual synchronized VO. The current plan is **DRAFT_UNMAPPED**. Even after plan approval, M4-C deliberately blocks final production until the 3D rig-action and VO/audio renderer exist in M4-D/E.
- Scene action IDs (e.g., `relief_exhale`, `shield_mug`) are **carried forward as named staging metadata**, not silently executed. Only camera cuts, a simple moving image, text guide and stage-color changes are currently implemented.

## 4. Exact Pilot 1 frame mapping (half-open)

| Shot | Start frame | End frame (exclusive) | Runtime |
|---|---:|---:|---:|
| SH_001 | 0 | 120 | 0:00–0:04 |
| SH_002 | 120 | 300 | 0:04–0:10 |
| SH_003 | 300 | 450 | 0:10–0:15 |
| SH_004 | 450 | 600 | 0:15–0:20 |
| SH_005 | 600 | 780 | 0:20–0:26 |
| SH_006 | 780 | 960 | 0:26–0:32 |
| SH_007 | 960 | 1170 | 0:32–0:39 |
| SH_008 | 1170 | 1380 | 0:39–0:46 |
| SH_009 | 1380 | 1560 | 0:46–0:52 |
| SH_010 | 1560 | 1740 | 0:52–0:58 |
| SH_011 | 1740 | 1920 | 0:58–1:04 |
| SH_012 | 1920 | 2130 | 1:04–1:11 |
| SH_013 | 2130 | 2310 | 1:11–1:17 |
| SH_014 | 2310 | 2490 | 1:17–1:23 |

No frame 2490 is rendered; `--quit-after 2490` closes the movie after exactly 2490 frame iterations.

## 5. Run from Windows PowerShell

With virtual environment enabled and M3 SQLite data present, from the repository root:

```powershell
python -m pytest backend/tests/test_m4c_manifest.py -q -c backend/pyproject.toml

# Freeze a 540x960 9:16 preliminary timing test with an EXPLICIT stand-in:
python tools/build_m4c_manifest.py --project-id blueprint-pilot-01 --quality previs --allow-proxy

# Compile, start Godot Movie Maker, and verify the produced 83-second movie:
.\tools\run_m4c_pilot.ps1 -GodotExe 'C:\path\to\Godot_v4.7.2-stable_win64_console.exe' -AllowProxy
```

Alternatively, pass an existing compiled manifest to the launcher without creating a second job:

```powershell
.\tools\run_m4c_pilot.ps1 -GodotExe 'C:\path\to\Godot_v4.7.2-stable_win64_console.exe' -SkipCompile -ManifestPath 'C:\repo\BLUEPRINT-STUDIOS\data\renders\jobs\<job-id>\render_manifest.json'
```

The launcher uses a **windowed Godot 4.7.2 baseline** and equivalent arguments:

```powershell
& $GodotExe --path $godotProject --scene 'res://scenes/DirectorPilot.tscn' --write-movie $output --fixed-fps 30 --quit-after 2490 -- --manifest $ManifestPath
```

The `--` separator passes the manifest argument to `OS.get_cmdline_user_args()`. Use the provided Movie Maker launcher rather than killing Godot with Ctrl+C; abrupt termination can leave invalid movie headers.

After rendering, `verify_m4c_video.py` uses FFprobe's decoded-frame count and checks `2490` video frames, `30 FPS`, `540x960`, `83.0s`. It cannot establish narrative quality. Review all 14 hard cuts visually, and verify `M4C_SHOT_START` lines in the Godot log.

If Movie Maker `.ogv` isn't supported by the installed Godot binary, switch output to `.avi` while retaining all validation gates. `--headless` can produce empty/black frames and is not the acceptance default.

## 6. Known deliberate limits

- The demo image is the original M4-B smartphone proof fixture, reused as a clearly labeled timing proxy if project media is missing. **There are no fabricated character performances.**
- Movie Maker output contains no narration yet. The manifest includes narration timing text, but audio ingest/sync, caption burning, 3D rigging, real stage assembly, PNG storyboard source selection, batch rendering and final H.264 encoding belong to M4-D/E.
- M3 adds `MediaBlob` and a nullable `AssetVersion.blob_sha256` FK. The compiler requires a valid MediaBlob FK plus physical integrity checks when that model is available. If M3 refactors these fields, update this resolver and re-run integration tests.
- Performance testing: the 540×960 movie is intentionally a reduced-resolution preview. Recording all 2490 frames to AVI may consume substantial disk space. Monitor capacity and prefer OGV or shot image sequences according to local GPU/runtime needs.
- Build/test integration checks do not prove that the Godot runner itself compiled; run the real engine on Windows and inspect the first, cut-transition, and final output frames.

## 7. Commit and release acceptance

```powershell
git switch main
git pull --ff-only
git switch -c feature/bs-m4c-pilot-render-manifest
# Extract ZIP preserving file paths, stage plan and tested M4-B proof.
python -m pytest backend/tests -q -c backend/pyproject.toml
npm run build
npm test
git add backend/app/services/render_manifest.py backend/app/api/render_manifests.py backend/tests/test_m4c_manifest.py godot_render/scripts/RenderManifestReader.gd godot_render/scripts/PilotDirectorRunner.gd godot_render/scenes/DirectorPilot.tscn godot_render/proof/pinned_phone.png docs/examples/BS-M4-PILOT-STAGE-PLAN.json docs/BS-M4C-MANIFEST-AND-GODOT-RUNNER.md tools/build_m4c_manifest.py tools/run_m4c_pilot.ps1 tools/verify_m4c_video.py
git commit -m "feat(bs-m4c): freeze pinned render manifests and drive 14-shot Godot previs"
git push -u origin feature/bs-m4c-pilot-render-manifest
```

Ensure the existing `.gitignore` excludes `/data/renders/`, `/backend/data/media/`, `godot_render/.godot/` and generated videos; do not commit actual media, databases, movie output or GPU caches. If you registered the optional API route, include `backend/app/main.py` in the commit.

**Acceptance gate:** manifest hashes verified, all 14 shot cuts logged, 2490-frame movie verified, original M4-B proof still passes, no pinned versions changed, existing frontend/CI tests pass. Any producer-facing claim of "final pilot animation" is blocked until approved character rigs/sets and M4-D audio/caption QC exist.
