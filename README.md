# BLUEPRINT STUDIOS — M4E-C + M4E-D Contracts

This is an **additive, documentation-first** handoff for `flyingdurian/BLUEPRINT-STUDIOS`, intended after Cursor merges M4E-A / M4E-B. No existing code file should be overwritten.

Contents:
- `docs/BS-M4E-C-FACIAL-MORPH-CONTRACT.md`: exact 22-name contract, full preset explanation, deterministic face sampling
- `docs/BS-M4E-D-APARTMENT-LIGHTING-CONTRACT.md`: 1080×1920 Forward+ lighting, native Godot property names, shadow / tonemapping policy
- `docs/examples/BS-M4E-C-FACE-PRESETS-v2.json`: **normative full 176 weights** (22 x 8)
- `docs/examples/BS-M4E-D-LIGHTING-PROFILES-v2.json`: **normative lighting profiles**, environment, project settings
- `docs/examples/BS-M4E-CD-SHOT-BINDINGS-v1.json`: look-dev example facial cues for 3 shots
- `godot_render/scripts/FaceMorphControllerExample.gd`: example-only expression evaluator (not a replacement for Cursor modules)
- `godot_render/scripts/StudioLightingBuilderExample.gd`: example-only lighting builder (not a replacement for Cursor modules)
- `tools/validate_m4e_cd.py`: contract-only validator
- `docs/BS-M4E-CD-CURSOR-HANDOFF.md`: implementation and acceptance brief

Run from repository root (after extraction):

```bash
python tools/validate_m4e_cd.py --stage-plan docs/examples/BS-M4-PILOT-STAGE-PLAN.json
```

If stage-plan path differs, replace that path with the authoritative file from M4-C. The validator also runs without `--stage-plan` but then cannot assert stage-plan equality.

**Git:** commit the documentation JSON and validator as one atomic change after M4E-A/B are merged and current production contracts are checked. Suggested message:

`docs(bs-m4e-cd): lock 22-channel facial and Forward+ lighting contracts`

**Caution:** Numeric face weights, light intensity and positions are provisional look-dev values, not owner-approved final appearance. No new Godot render was executed in this package.
