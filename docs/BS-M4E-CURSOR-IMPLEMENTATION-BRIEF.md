# Cursor handoff — BS-M4-E production animation and lighting

**Objective:** Replace the approved previsualization proxies with a character rig, authored reusable actions, facial morph system and physically coherent apartment lighting, while maintaining all M4-C/M4-D frame/audio/export invariants. Do not treat a correct video file as equivalent to accepted animation quality.

## Mandatory readiness gate (before coding)

1. Inspect the currently checked-out Git branch and its actual source; do **not** reconstruct M4-D from older public GitHub `main`. Review Godot scene scripts, manifest schema, M3 MediaBlob API, M2.2 atomic snapshot logic, M4-D mux/captions and available final assets. Output SHA, branch name, existing tests and a diff-aware integration plan.
2. Read `docs/BS-M4E-PRODUCTION-RIG-FACE-LIGHTING.md` and four `docs/examples/BS-M4E-*.json` reference contracts. Treat numeric artistic settings as unapproved starting points. Reconcile API renames without altering pinned versions or M4-D timing.
3. Identify actual artwork/rigs available. **No generic placeholder character accepted as a final rig**; if owner-approved identity master is missing, build rig validation harnesses and a test dummy but leave production-quality gate BLOCKED until owner provides/approves character art.
4. Preserve M4-B proof, M4-C `PilotDirectorRunner.gd`, M4-D rendering and mux controls; put production paths in new files (`ProductionShotDirector.gd`, `ActorRigController.gd`, etc.).

## Proposed additive repository paths

```text
godot_render/
  actors/lead/Actor_Lead.tscn
  actors/lead/LeadRigController.gd
  actors/lead/LeadFaceController.gd
  animations/LeadBodyLibrary.tres            # generated/imported from verified .glb
  scenes/sets/ApartmentNook.tscn
  scenes/sets/HostDeskCutaway.tscn
  scripts/ProductionShotDirector.gd
  scripts/PropSocketResolver.gd
  scripts/CameraPresetController.gd
  lighting/ApartmentDayEnvironment.tres
  lighting/ApartmentLighting.tscn
  tests/test_lead_import.gd
  tests/test_action_frame_seek.gd
  tests/test_prop_attachment.gd
  tests/test_face_presets.gd
backend/app/services/production_stage_validation.py
backend/tests/test_m4e_contract.py
docs/BS-M4E-PRODUCTION-RIG-FACE-LIGHTING.md
docs/examples/BS-M4E-*.json
```

Actual implementation names may vary but must remain additive and clear. Source `.blend` and generated `.glb` should follow the existing M3 immutable media source/export convention rather than importing unverified file paths.

## Ordered development gates

**M4E-A rig:** Build import validator to reject missing canonical 40 bones, wrong bind meshes, missing 3 sockets, scale drift and morph inconsistency. Make a turnaround and three grip-contact views. Present identity/rig for owner approval. Do not infer a model exists from the example `BS-M4E-RIG-CONTRACT.json`.

**M4E-B motion:** Implement a registry matching all 34 action IDs in stage plan to clips/composites/effects. Author minimum action clips with rigidly staged phone/mug movements. For `SH_002`, `SH_005`, `SH_009`, `SH_013`, export 2–5 second motion proofs with continuity screenshots. Test seeking arbitrary local frames and re-evaluating the same frame identically.

**M4E-C face:** Sculpt 22 named blend shapes on a topology-locked FaceMesh. Implement blend targets through `MeshInstance3D.find_blend_shape_by_name()` / `set_blend_shape_value()`; cache indices at import and treat missing morph as error. Implement eight weight-vector presets from JSON; add explicit 3–5-frame blink cues and eye-bone gaze. Render 8×3 contact sheets and transition examples; request owner signoff.

**M4E-D environment:** Build apartment room and 3-point light setup plus WorldEnvironment. Capture SH_002/SH_005/SH_008/SH_009/SH_013 side-by-side baseline, soft-shadow, improved look. Do not enable multiple WorldEnvironment instances; lock exposure and tonemapper. Verify lighting with and without captions at 540×960 and 1080×1920.

**M4E-E full assembly:** Bump versioned approved art assets via M3; stage exact SHA-pinned bytes; require `stageApproval=APPROVED` and resolved actions, morph targets and socket bindings in production manifest. Render 2490 frames at 30 fps via Movie Maker, run existing M4-D audio/caption mux unchanged, verify ffprobe frame/duration/sync, and visually inspect selected frames and all cut boundaries. Only request full owner final signoff after technical + visual QA pass.

## Non-negotiable constraints

- No alteration of 14 shot IDs, frame boundaries (0 to 2490 exclusive), VO narration or approved subtitles without explicit story revision.
- No fake rig animation: `ActionLibrary` names in a JSON file are not playable clips. Validate actual Godot AnimationPlayer/AnimationLibrary resources and bone transforms.
- No fake facial deformations: a weight-mapping JSON alone is not sufficient. Require actual imported morph target names and visible mesh deformation.
- No collision/position drift of phone/mug between shot contexts. Test grasp offsets and shot-wise prop ownership.
- No overwrite of existing asset versions or source hashes. New visual art must have approved IDs and immutable version records.
- No background asynchronous work promises. Each development checkpoint returns files, executed tests, real screenshots/movie samples and explicit blockers or owner signoff question.
- No commit directly to main; branch and run frontend/backend/render CI and QA before PR.

## Example commit sequence

```text
feat(bs-m4e): add canonical lead rig contract and Godot import validator
feat(bs-m4e): implement deterministic action registry and prop sockets
feat(bs-m4e): add named facial morph presets and validation proofs
feat(bs-m4e): stage cinematic apartment lighting and vertical lookdev
feat(bs-m4e): integrate approved rig assets into locked pilot renderer
```

**First developer action:** report the exact current branch and all real art assets available. Start M4E-A source validator and character rig proof. If owner-approved character artwork is absent, stop **final-art acceptance** only, not infrastructure or validation work.
