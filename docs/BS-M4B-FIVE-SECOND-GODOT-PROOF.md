# BLUEPRINT STUDIOS — M4-B: pinned media → Godot Movie Maker proof

## Contract

- Exactly one original **example** physical PNG (`godot_render/proof/pinned_phone.png`) is pinned by `assetId`, `pinnedVersion`, and SHA-256 in `pinned_asset.json`.
- `PinnedAssetResolver.gd` verifies the SHA-256 **of the file bytes** before decoding it into an ImageTexture. If bytes change, it fails and requests an error exit instead of rendering an unverified replacement.
- `DirectorRunner.gd` creates a deliberately minimal moving, labeled 2D stage. Frame-dependent motion is driven by an integer frame counter.
- CLI `--fixed-fps 30 --quit-after 150 --write-movie` controls capture frame count and graceful writer termination. The script does not call `quit()` after 5s while recording; doing so can end on the wrong boundary.
- `verify_m4b_proof.py` checks actual recorded video frames (150), FPS (30), dimensions (540×960), duration (~5s), and pinned fixture SHA-256. An exit code 0 alone is **not** proof of video validity.

> The fixture is NOT the existing M3 `ast-phone`/v2. It is a new original test fixture (`proof-phone`/v1). M4 production must resolve the real `(assetId, pinnedVersion)` from the M3 immutable blob table, pin its computed digest in a frozen render manifest, and copy/stage it as `res://staged/...` without rewriting the original version.

## Drop-in monorepo structure

```
BLUEPRINT-STUDIOS/
├── godot_render/
│   ├── project.godot
│   ├── scenes/DirectorProof.tscn
│   ├── scripts/DirectorRunner.gd
│   ├── scripts/PinnedAssetResolver.gd
│   └── proof/{pinned_asset.json,pinned_phone.png}
├── tools/{run_m4b_proof.ps1,verify_m4b_proof.py}
└── docs/BS-M4B-FIVE-SECOND-GODOT-PROOF.md
```

Run after M3 commits and your feature branch is based on latest main. These are additive files and do not alter the existing React or FastAPI code. Add `/data/renders/` and `/godot_render/.godot/` to the root `.gitignore` if not already present.

## Windows PowerShell — recommended windowed GPU render

```powershell
# Repo root
& .\tools\run_m4b_proof.ps1 -GodotExe 'C:\path\to\Godot_v4.7.2-stable_win64_console.exe'
```

Or run Godot directly:

```powershell
New-Item -ItemType Directory -Force .\data\renders\bs-m4b | Out-Null
& 'C:\path\to\Godot_v4.7.2-stable_win64_console.exe' `
  --path (Resolve-Path .\godot_render).Path `
  --write-movie (Join-Path (Resolve-Path .\data\renders\bs-m4b).Path 'm4b-proof.avi') `
  --fixed-fps 30 --quit-after 150
python .\tools\verify_m4b_proof.py .\data\renders\bs-m4b\m4b-proof.avi
```

Godot writes a valid AVI only when it shuts down normally. Do not force-stop it using Ctrl+C. The wrapper checks the requested version, run exit code and the FFprobe result. Install FFmpeg to make `ffprobe` available in PATH; Python 3.11+ is needed for the verifier. During the test Godot renders 540×960 to reduce cost, not the final 1080×1920 master.

Optional `-Headless` switch is **experimental only**. Godot's headless display driver is commonly a dummy renderer, so it can render blank output or fail; use a normal windowed invocation to establish the baseline first. For a GPU-assisted render server, configure a suitable supported display/rendering context rather than assuming `--headless` provides one.

## Expected pass signals

- Console contains `M4B_PIN_OK id=proof-phone version=1 sha256=...`.
- Video contains a moving smartphone graphic and changing frame counter.
- Python verifier returns `PASS: 150 frames at 30 FPS, 540x960, 5.000s`.
- On changing a single PNG byte without updating the manifest, Godot reports `M4B_PIN_FAIL`; no production-quality render can be marked complete.

## Engineering caveats / next steps

1. **Render staging:** M3 media downloads are stored content-addressably outside Godot. M4 must stage a pinned, checksum-verified copy into a render job folder accessible as `res://staged/`. Do not pass arbitrary user filesystem paths or update existing media files in place.
2. **Real rig support:** PNG is an asset-path proof, not a GLB/rig importer. Use Godot's asset import pipeline and a validated mapping for GLB/GLTF/PNG/WAV before the full pilot.
3. **Per-frame action control:** The smoke animation is written in GDScript for one shot. The full timeline runner will read a separate approved 14-shot staging plan, instantiate prepared scenes and evaluate authored keyframes at global frame indices.
4. **Determinism:** The test is intentionally simple. Future render contracts should record the renderer/Godot version, output profile, each pinned blob hash, frame-count verification and manifest hash; exact binary video hashes can vary with encoder settings and machine.
5. **Recovery:** On failed renders or incorrect frame count, retain logs and mark the render job failed, not complete. Do not overwrite prior approved exports.
6. **Windows PS policy:** If PowerShell blocks unsigned scripts, start a temporary process with `-ExecutionPolicy Bypass` under your own security policy; you may also copy and run the documented direct commands without changing machine policy.

## Suggested commits

`test(bs-m4b): add pinned-asset Godot five-second Movie Maker proof`

Upon local proof success:

`docs(bs-m4b): record verified 150-frame Godot capture and ffprobe results`

## Official reference

- https://docs.godotengine.org/en/stable/tutorials/animation/creating_movies.html
- https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html
- https://docs.godotengine.org/en/stable/classes/class_hashingcontext.html
