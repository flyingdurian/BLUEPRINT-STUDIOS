# BLUEPRINT STUDIOS — M4E-E: Full Production Integration & Automated QC

**Status:** Normative *design specification* and reference QC implementation. Not a claim of an approved rig or a completed final render. **Target:** Godot 4.7.2, Forward+, 1080 × 1920 (9:16), 30 CFR fps, **14 shots / 2,490 frames / 83.000 s**. **Input source:** authoritative project graph in SQLite, pinned SHA-256 media, stage plan `docs/examples/BS-M4-PILOT-STAGE-PLAN.json`, M4E rig/action/facial/lighting contracts, existing M4-D narration alignment and captions.

## 0. Repository reconciliation / release decision

The repository was inspected on `feature/bs-m4e-production-rig` (the default `main` branch is behind this work at the time of writing). The existing `backend/app/services/render_manifest.py` emits `blueprint.render-manifest.v1` with `stagePlanStatus: DRAFT_UNMAPPED`, `productionLocked: false`, `performance.execute: false` and a 540×960 previs viewport. The stage plan itself marks performance and shot approvals as pending. `godot_render/scripts/PilotDirectorRunner.gd` is a previs runner; it explicitly logs rather than executes actions. M4-D currently accepts only the v1 schema and its encoder writes `pilot-final.mp4` immediately. THESE ARE RELEASE BLOCKERS for production. This spec prescribes additive, versioned upgrades, not simple booleans toggled to pass. Cursor must inspect its working branch immediately before modifying files.

**Mandatory decision:** `quality=production` has no `allow_proxy` parameter and cannot use placeholders. No approval can be inferred from asset presence, validator pass, or generated fixtures. A real owner signoff is separately recorded per rig identity/look, per-shot staging, and final contact-sheet / render.

## 1. Architecture — sources, seal, execute, attest, inspect, publish

```text
SQLite snapshot + 14-shot staging plan + pinned AssetVersion/MediaBlob hashes
  + Godot capability report (real imported resource names/paths)
  + approved rig/action/morph/light registry + owner approvals
       │  validate all dependencies; recompute hashes
       ▼
Production Manifest Compiler (render-manifest.v2, immutable render job)
       │  manifest SHA-256 sidecar; staged immutable media and scene resources
       ▼
Godot ProductionDirector (global integer frame 0..2489; pure seek evaluation)
       │  1080×1920 frames + render_trace.jsonl + engine_preflight.json
       ▼
FFmpeg candidate assembly (silent intermediate + M4-D narration + subtitles)
       │  pilot-candidate.mp4; audio_alignment.json; captions.vtt; assembly.json
       ▼
Python QC: frame timestamps + actual decoded video + content/material telemetry
       │  + optional alignment PCM correlation + human-review evidence
       ▼
QC PASS and OWNER FINAL APPROVAL → atomic promotion to pilot-final.mp4
QC FAIL/INCOMPLETE → retain candidate and report, never publish 'final'
```

Save the exact compiler revision, Godot engine version/hash, renderer, script/resource hashes, JSON contract hashes, final image profiles, FFmpeg invocation, and output media SHA-256. File-content hashes attest source bytes; a successful run never changes the underlying SQLite edit state.

## 2. Production manifest compiler: `backend/app/services/render_manifest.py`

### Schema upgrade and M4-D compatibility

- Introduce `blueprint.render-manifest.v2` for locked production. Preserve the v1 `projectId`, `revision`, `fps`, `totalFrames`, `shots`, `stagePlanSha256` and shot fields so existing screens remain understandable.
- **Do not feed v2 directly to M4-D's current v1-only `audio_assembler.py`.** Either update its schema validator to accept **both** v1 and v2 with shared validated shot timing, or generate a separately hashed M4-D audio manifest whose shot table hash equals the parent v2 manifest. Prefer a shared typed schema function used by both producers.
- Retain the existing v1 previs pathway and M4-B's five-second proof as regression fixtures. Do not downgrade production to v1 to avoid an adapter.
- Build in an isolated temp job directory; validate and stage all bytes, then atomically seal the manifest and mark job `MANIFEST_LOCKED`. On errors, leave no job marked locked.

### Mandatory checks before production manifest sealing

| Gate | Proof and failure mode |
|---|---|
| Shot graph | Exactly 14 unique IDs, codes SH_001..SH_014, contiguous half-open intervals `[startFrame,endFrameExclusive)`, order unchanged, last exclusive frame = 2490, `fps=30`. |
| Stage approvals | Each shot has an approval receipt from owner-reviewed staging; no `DRAFT_UNMAPPED`, `PENDING`, or `APPROVED_PROXY_ONLY_FOR_PREVIS` statuses. Explicit approval record is immutable and tied to stage-plan SHA-256. |
| Verified media | Every required version has `verified=true`, `resolution=VERIFIED_BLOB`, `sha256`, `MediaBlob` and a file. Recompute SHA-256 on staged bytes and reject mismatch. Reject unsafe paths, media MIME mismatch, or unregistered external dependencies. |
| Rig | Pinned `ast-lead` asset version points to actual imported rig bytes and matches approved rig identity receipt; `Skeleton3D` has each of the **40 exact names**, correct explicit mesh `skeleton` bindings and calibrated sockets `phone_grip_r/l`, `mug_grip_r`, table/drawer rests. Validation report comes from Godot runtime inspection, not merely hand-authored JSON. |
| Face | `FaceMesh` exists and `find_blend_shape_by_name` finds every **22 exact case-sensitive channels**; eight expression presets are complete, finite, in `[0,1]` and version-pinned. Strict set equality is the minimum; extra morph channels may exist but cannot substitute for required names. |
| Actions | All **34 unique stage-plan action IDs** resolve through the registered Godot ActionLibrary to an exact `AnimationLibrary` + clip, deterministic facial evaluator, keyed prop operation, camera/graphic action, or documented hold. All resources exist and are executable. **An action ID is not necessarily an AnimationPlayer clip**; do not create fake empty animation clips for face/cut/hold events. |
| Runtime | Godot capability report tied to same staged resource hashes and exporter/build version confirms 14 camera presets, sets, action registry, morphs, sockets, material bindings, and import health. No placeholders, unknown actions, dynamically downloaded textures, or unresolved paths. |
| Rendering | 1080×1920, Forward+, 30 fps, exactly 2490 output frames; locked apartment lighting profile and fixed exposure, explicit color pipeline. |
| Audio | M4-D audio alignment, referenced WAVs and captions are hashed and tied to the same shot timetable; silence is only permitted when explicitly authored. |
| Reproducibility | `render_manifest.json` canonical bytes plus `render_manifest.sha256`; stage media copied/hardlinked into job staging with integrity check and file path isolation. |

**Godot capability report generation and hashing (avoid circular dependencies):** Use a separate import/preflight scene to load the real rig and libraries and emit **`engine_capabilities.json` before manifest compilation**; this report binds the rig/media source hashes and contains **no** final manifest hash. The compiler verifies it, hashes it, and includes its hash in the v2 manifest. During the subsequent render, Godot emits **`engine_preflight.json` with `manifestSha256`**, which is **not hashed into that manifest** (that would create an impossible hash cycle). QC checks both files against their respective hashes and source identities. A handwritten registry containing `status: READY` is NOT enough.

**Race protection**: Read SQLite in one consistent read transaction; do not write project data or increment revision. If the graph changed before staging completes, either lock against the chosen revision and keep it independently sealed or reject the job and request recompile. The render always uses the frozen input, not the current editor state.

### Manifest v2 additions (illustrative fields)

```json
{
  "schemaVersion": "blueprint.render-manifest.v2",
  "quality": "production",
  "productionLocked": true,
  "proxy": false,
  "standIn": null,
  "projectId": "blueprint-pilot-01",
  "revision": 42,
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "totalFrames": 2490,
  "stagePlanStatus": "APPROVED",
  "production": {
    "rigAssetId": "ast-lead",
    "rigPinnedVersion": 4,
    "rigSha256": "<real_64_hex_digest>",
    "skeletonContractSha256": "<real_64_hex_digest>",
    "faceContractSha256": "<real_64_hex_digest>",
    "actionRegistrySha256": "<real_64_hex_digest>",
    "lightingContractSha256": "<real_64_hex_digest>",
    "engineCapabilitiesSha256": "<real_64_hex_digest>",
    "ownerApprovalReceiptSha256": "<real_64_hex_digest>",
    "renderPreset": "final_vertical_9x16",
    "requiredMorphNames": ["<all 22 exact names, not elided in actual manifest>"],
    "requiredActionIds": ["<all 34 exact IDs, not elided in actual manifest>"]
  },
  "shots": ["<14 full v1-compatible shots, each with approved actionCues and faceCues>"]
}
```

Angle-bracket entries above are **placeholders in documentation only**, not valid manifest input. The actual sealed manifest is exhaustive and all hashes are computed from staged files.

Extend each shot with `actionCues: [{actionId, driver, resource, startLocalFrame, endLocalFrameExclusive, layer, weight?}]`, `faceCues: [{startLocalFrame,endLocalFrameExclusive,from,to}]`, `lightingPreset`, `cameraPreset`, `setKey`, `propBindings: [{assetId, pinnedVersion, socket, switchLocalFrame}]`, `overlayCues`, `asset` hashes and approval receipt identity. Use the M4E action bindings as the design seed, but require actual runtime file verification before marking the cues executable.

## 3. Godot master orchestrator

**Do not replace M4-B `DirectorRunner.gd`.** Introduce `ProductionDirectorRunner.gd` plus narrow services: `ProductionManifestReader.gd`, `ProductionStageAssembler.gd`, `ActionEvaluator.gd`, `FaceMorphController.gd`, `PropAttachmentEvaluator.gd`, `CameraRigEvaluator.gd`, `RenderTelemetry.gd`. Their job: `evaluate_global_frame(int)` is the one source of truth. Godot Movie Maker controls the frame advances; the runner evaluates one intended integer frame per `_process()` tick and emits one telemetry record. The CLI uses `--fixed-fps 30 --quit-after 2490` and does not `quit()` early on normal completion.

### Frame evaluation ordering (idempotent, seek-safe)

1. Assert `0 <= f < 2490`; binary-search active shot with `startFrame <= f < endFrameExclusive` (or cached index that can rewind). Compute `local = f - startFrame`.
2. Reset animation, face, prop and camera **in-memory evaluation state** to canonical shot baseline for this *specific* frame; no dependence on the previous tick or undocumented accumulated pose state. Do not reinstantiate the entire scene on every frame.
3. Activate the shot's approved set and camera preset. For camera transitions, interpolate camera transforms using a frame-indexed curve; hard cuts activate at the first frame of the next shot.
4. Evaluate action cues at `(local-startLocalFrame)/30`. Use `AnimationPlayer.seek(time,true,true)` for deterministic sampled animation *after* selecting the correct clip; `update_only=true` skips audio/method/event tracks, which must be handled through **explicit state evaluators**. A shared animation scheduler handles conflicting tracks and authored layer weights (base, upper-body, head, hands, face); never rely on implicit `animation_finished` signals.
5. Evaluate all **22** facial weights from approved expression cues at the exact local frame. Write each via `MeshInstance3D.set_blend_shape_value`, including zeros; ensure intentional no-blink overrides for SH_009.
6. Evaluate prop attachment ownership and calibrated transform for the exact frame: hand ↔ table ↔ drawer. `SH_002` mug sip, `SH_005` protective mug, `SH_008` phone set-down, `SH_013` drawer transfer are mandatory contact tests. Switching anchor must retain prop visual continuity.
7. Evaluate graphic overlays, subtitles safe-zone and lighting preset from the frozen manifest, then record immutable per-frame telemetry (shot ID, actions, camera, morph count/checksum, sockets, material validation results).
8. Let Movie Maker capture. On startup failure, record error and exit nonzero **before** opening a success-status job. On normal end, leave shutdown to CLI frame-count limit, flush telemetry on completion.

**Determinism**: no uncontrolled physics, randomness, wall-clock timers, asynchronous animation loads, editor-only `NodePath` assumptions or unseeded procedural motion. A jump directly to f=1,380 (SH_009 start) must produce the same state as sequential playback. Frame-0/last-frame/shot-boundary testing is mandatory. Use `AnimationPlayer` path/track constraints validated in Godot; imported animation clips must not rely on method/audio side effects during seeking (Godot documents that seek skips intervening events).

### Execution evidence

- `engine_capabilities.json`: pre-manifest real imported-resource inspection, source hashes, action resolvability, material/texture inventory; **no manifest digest**. `engine_preflight.json` (post-manifest): `manifestSha256`, `engineVersion`, `rigSha256`, `boneNames` (40 exact), `blendShapeNames` (22 exact), action resolutions (34), camera presets (14), `surfacesValidated`, `materialErrors`, `missingTextures`, `socketErrors`, `sceneWarnings`, `approvedSourceDigest`.
- `render_trace.jsonl`: **2490** ordered records with `frame`, `shotId`, `cameraPreset`, `faceChannelCount`, `startedActions` (list for that frame), `socketErrors`, `materialErrors`, `missingTextures`; optional pose/camera checksums and screenshot reference IDs. The frame trace attests evaluator progress but is not sufficient alone to prove the movie encoder wrote every frame.
- `godot.log` and movie output logs: parser errors, import failures, shader warnings, texture load errors, crash/exit code. Production fails if known error patterns are present, even if video exists.
- `render_frame_index.json`: ideally capture explicit frame-to-render/PTS mapping for later correlation.

**Do not confuse a telemetry event with real visual proof.** Engine checks prove structural assignments; a misplaced texture, hand intersection or ugly expression may still need automated image comparison or human review.

## 4. QC verification architecture and thresholds

**Reference script:** `tools/qc_production_render.py` in this package implements the structural baseline, can return PASS/FAIL and writes a JSON report. It deliberately does **not** claim complete aesthetic/material/audio verification solely from an MP4. Add a separate optional waveform-correlation plugin and golden-frame visual test module after their actual M4-D integration is inspected.

| QC gate | Evidence | Release condition |
|---|---|---|
| Contract integrity | Sealed manifest hash sidecar, engine preflight matching hash, asset digests | 14 shots / 2490 / 30 / 1080×1920 / production lock / no proxy / approved IDs; no mismatch. |
| Rig+action+materials | Godot engine preflight + per-frame telemetry | 40 exact bones, 22 exact shapes, 34 registered/used action IDs, expected sockets, real materials and explicit required texture properties; no missing/failed imports. |
| Timeline/frame integrity | FFprobe `-count_frames` and decoded `best_effort_timestamp_time` | 2490 decoded frames, constant 30 fps, monotonic presentation timestamps spaced 1/30 s (small container rounding tolerance). |
| Video encoding | FFprobe streams | 1080x1920 H.264 `yuv420p` SDR Rec.709-tagged output, exactly 83 s video timeline. |
| Audio structure | M4-D `audio_alignment.json`, `narration_mix.wav`, final AAC stream | 14 aligned entries, 48 kHz audio, 83 s program, expected per-shot start frames, no missing tracks, known loudness and clipping gate. |
| Audio *content alignment* | PCM comparison of `narration_mix.wav` to decoded movie audio using normalized cross-correlation around known voice windows | Max frame-aligned offset <= 1 video frame; if confidence is low, **INCOMPLETE**, not PASS. AAC priming/codec delay must be compensated consistently. |
| Captions | `captions.vtt` cues and final output/mux receipt | Valid boundaries, all 14 required cues, correct textual correspondence, no overlaps, phone-safe placement. Burned-in readability additionally requires image inspection. |
| Visual anomalies | Import/material logs, engine texture inventory, golden still frame comparisons | Missing material = fail; *actual texture rendering correctness* needs reference image compare. Negative test for missing texture required. |
| Intentional holds | Shot animation semantics | Identical consecutive pixels may be intentional (SH_008 hold, SH_009 freeze, SH_014 black). Never classify all duplicate images as dropped frames. |
| Black frames | Timeline action allowances | Only authored black intervals allowed; unexpected contiguous black durations fail if images available. |
| Final approval | Owner-reviewed contact sheets and full pilot | QC technically passes **and** artistic approval receipt exists; only then publish final. |

**What cannot be proven from MP4 metadata alone:** Missing textures that were silently replaced by a valid shader/material, bad rig intersections, wrong emotion despite legal weight values, audio narration words aligned semantically, and frame content that is repeated due to an intended static hold vs a rendering fault. Use exported engine evidence plus golden frames and owner review; do not overstate automation.

### Candidate-first assembly / no premature final files

Modify `backend/app/services/ffmpeg_assembly.py` to render `.pilot-candidate.part.mp4` then atomically finalize `pilot-candidate.mp4`; **do not create `pilot-final.mp4` as M4-D currently does**. Run all QC gates using the candidate; if success and explicit owner acceptance, promote with an atomic same-filesystem `os.replace(candidate, pilot-final.mp4)` and write SHA-256 + `qc_report.json` + approval receipt. If failed, retain candidate and report, leave any previous approved final untouched. The separate 540×960 previs files keep their old names.

The QC script outputs machine-readable findings with severity (`BLOCKER`/`WARNING`/`INFO`), code, evidence, expected, actual, and optional `shotId`/`frame`. Report is immutable after promotion; later edits require new job and QC run.

## 5. Test plan / acceptance gates

**Preflight negatives:** Remove one bone; rename `EyeSquint_R`; change pinned GLB bytes; unregister `mug_sip`; use `PENDING` stage approval; point texture to missing file; use a 540×960 resolution; hide required clip behind an empty stub. Every case must fail closed.

**Determinism:** Compare state digests for frames 0, 119/120, 299/300, 1379/1380, 1559/1560, 2309/2310 and 2489, evaluated sequentially and in shuffled order. Check sockets and material inventory; ensure no unexpected frame- or timeline-state carryover.

**A/V QC negatives:** Cut one video frame; duplicate one timestamp; alter FPS to 29.97; shift mixed narration 100 ms; truncate audio; omit SH_009 caption; drop a narration WAV; change caption text; insert black frame outside approved interval; corrupt a PNG texture. Test that no `pilot-final.mp4` is published.

**Acceptance target:** all 14 shots execute authored actions and approved camera/face/lighting states; 2490 unique frame-index evaluation events; 2490 decoded video frames, CFR 30, 1080×1920; exact pinned media hashes and no unresolved dependencies; audio synced against M4-D alignment; 14 captions verified; material probes clean; owner approves final look. After PASS+approval, `pilot-final.mp4` is promoted.

## 6. Repository delta (additive; reconcile Cursor's live branch)

```text
backend/app/services/render_manifest.py     # extend v1 to strict v2 production
backend/app/services/production_preflight.py # NEW verifies actual engine report/approved registries
backend/app/services/ffmpeg_assembly.py      # candidate -> QC -> approved final
backend/app/services/audio_assembler.py      # v1/v2 common timeline validator
backend/app/api/render_jobs.py               # expose compile/render/QC state, not fake status
godot_render/scripts/ProductionDirectorRunner.gd # NEW; preserve original previs runner
godot_render/scripts/ActionEvaluator.gd      # author & wire existing 34 registry IDs
godot_render/scripts/ProductionTelemetry.gd  # record frame attestations
tools/qc_production_render.py                # NEW baseline + evolving plugins
tests/test_m4e_e_qc.py                      # negative/positive QC tests
docs/BS-M4E-E-PRODUCTION-INTEGRATION-QC.md  # THIS SPEC
```

**Suggested branches/commits:** `feature/bs-m4e-e-production-qc`; `feat(bs-m4e-e): lock production manifests and orchestrate 14-shot animation`; `test(bs-m4e-e): add QC gates and candidate-only final promotion`. No existing scene or user-approved art should be silently replaced.

## 7. Phased Cursor execution, not status theater

**E1:** Integrate source contracts, inspection report and production manifest compiler. Stop only for genuine unresolved owner approvals or missing art; provide precise shot IDs and assets, not generic blockers.

**E2:** Implement frame evaluator and telemetry; validate at critical shots and arbitrary frame order; preserve M4-B and M4-C.

**E3:** Render silent full pilot 1080×1920 and validate each frame/shot transition.

**E4:** M4-D candidate assembly, aligned narration, caption integrity, A/V QC and material probes.

**E5:** Full visual review contact sheet + approval receipt, only then promote to final. Publish evidence: SHA-256s, 14-shot trace, 34 actions, test counts, FFprobe report, errors and final screenshot/contact sheet. Never state production accepted based only on tests.
