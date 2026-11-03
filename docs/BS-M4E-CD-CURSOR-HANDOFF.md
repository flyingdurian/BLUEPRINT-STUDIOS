# Cursor implementation directive — BLUEPRINT STUDIOS M4E-C + M4E-D

**Context:** User reports Cursor is implementing M4E-A / M4E-B now. This package is for the *next* phases. Do not overwrite in-flight code. After A/B merge, pull the actual branch and confirm Godot 4.7.2 runtime, imported skeleton mesh and live render manifest before writing integration code.

## Source and non-regression priority

1. Existing M4-C 14-shot 2,490-frame half-open timeline and M4-D audio/caption/export are **unchanged**.
2. Existing M4E-A 40-bone skeleton (`Eye_L`,`Eye_R`,`Jaw`, hand sockets), actual rig node paths, M4E-B action registration/prop timing are authoritative. If mesh differs from proposed paths, adapt only wrapper configuration, not names in facial JSON without approval.
3. M3 immutable media blob SHA-256 and shot pinned versions remain authoritative. Asset updates always require new versions and explicit adoption; add hash and version to frozen render manifests.
4. Do **not** replace the working five-second Godot proof or previsualization runner.

## Integration phase C: facial morphs

- Add a production `FaceMorphController.gd` to the existing rig wrapper, using `FaceMorphControllerExample.gd` only as an initial API shape. Load `BS-M4E-C-FACE-PRESETS-v2.json` as a staged, hashed manifest dependency (not from mutable editor files during render).
- At import validate exactly the required 22 channel **names** and their mesh indices using `find_blend_shape_by_name`; validate every preset includes all 22 weights. 8 presets required. Extra channel => warning + review; missing => hard fail in final mode.
- Implement `evaluate(shotId,localFrame)` as a pure deterministic function with `smoothstep`. Apply all weights each frame. Maintain jaw/gaze via separate explicit drivers; pre-author blink schedule, no random blink.
- Establish 24-image full-resolution contact sheet (8 expressions × three angles), plus separate neutral reference. Add mesh validity and non-destructive tests on imported `.glb`.
- Demonstrate SH_004 polite→confused, SH_009 polite→frozen, SH_014 exhausted→deadpan; compare repeat/seek-to-frame results. User must sign off on facial identity and deformations before C acceptance.

## Integration phase D: lighting

- Create one active `WorldEnvironment` and LightingRig nodes, no secondary WorldEnvironment in host cutaway. Use `StudioLightingBuilderExample.gd` only as a starter, not as a replacement for existing set hierarchy.
- Read `BS-M4E-D-LIGHTING-PROFILES-v2.json`, validate node names, Forward+ mode, fixed exposure, Filmic, shadows, and source color. Apply `apartment_day`, `phone_insert`, `host_desk` profiles only where named by an approved staging cue; if no cue exists, add explicit cue data rather than guessing from prose.
- Apply ProjectSettings shadow atlas, anti-aliasing, and physically based units **at project launch before rendering**, verify actual Godot 4.7.2 property availability.
- Produce full-resolution A/B contact sheets: SH_002, SH_005, SH_009, SH_013, SH_014 with neutral shader vs final; test both 540×960 review and 1080×1920 final.
- Manually calibrate key direction/energy and shadow bias after visual inspection; any change is a versioned, pinned look-dev revision. Do not bake unreviewed hard-coded lighting into action clips.

## Quality gates / tests

- Run `python tools/validate_m4e_cd.py --stage-plan docs/examples/BS-M4-PILOT-STAGE-PLAN.json` (pass actual stage-plan location if different).
- Unit: 22 exact names x 8 complete presets, 0..1 numeric weights, 3 known profile names, consistent half-open cue coverage, no unapproved physical-light-unit conversion.
- Godot headless import test when available for shape lookup and GDScript compilation. **Visual rendering requires real graphics device**; verify windowed or supported offline Movie Maker path.
- Frame sampling: render exact still of SH_009 at global frame 1404 repeatedly with randomized prior seek order; same rendered pose and stable lighting. Verify 14 shots retain timestamps and caption/audio sync after the change.
- Block final mode on missing rig shape/lighting resource, incorrect blob hash, missing action clips, or unapproved visual asset version. Degrade only in explicit PREVIS mode with watermarked fallback.
- Report exact branch name, parent SHA, changed files, tests, Godot version, render examples and any unverified visual claims. Obtain owner signoff at M4E-C and M4E-D visual approval gates.

## Suggested commits

`feat(bs-m4e-c): add deterministic facial morph contracts and expression evaluator`

`feat(bs-m4e-d): integrate locked Forward+ apartment lighting profiles`

**This deliverable is a design contract, not runtime-tested character animation or final approved lighting.**
