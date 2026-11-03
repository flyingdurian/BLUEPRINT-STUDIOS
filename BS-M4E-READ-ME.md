# BLUEPRINT STUDIOS — M4-E Production Visual System

**This is a specification package**, not a Godot patch and not a completed animated episode. Unzip the contents into `BLUEPRINT-STUDIOS/` with the same relative paths (all files under `docs/` and `tools/`). No existing React, backend or Godot files should be overwritten by this package.

Contents:

- `docs/BS-M4E-PRODUCTION-RIG-FACE-LIGHTING.md` — main architecture, asset production pipeline, body rig, facial system, materials, apartment staging, lighting, frame invariants, approval gates.
- `docs/BS-M4E-CURSOR-IMPLEMENTATION-BRIEF.md` — actionable phased instructions for Cursor.
- `docs/examples/BS-M4E-RIG-CONTRACT.json` — proposed 40-bone skeleton names and prop sockets.
- `docs/examples/BS-M4E-FACIAL-RIG.json` — 22 morph channels and eight facial preset weight vectors.
- `docs/examples/BS-M4E-ACTION-BINDINGS.json` — mapping of all 34 staging action IDs with suggested 14-shot frame windows, plus prop ownership.
- `docs/examples/BS-M4E-LIGHTING-PRESETS.json` — baseline Forward+ lighting and 9:16 composition constraints.
- `tools/validate_m4e_design.py` — schema/context sanity check against existing M4-C stage plan (not a Godot rig or animation runtime test).

Suggested documentation commit:

`docs(bs-m4e): specify production rig, facial morphs and studio lighting`

Validate example contracts:

`python tools/validate_m4e_design.py --plan docs/examples/BS-M4-PILOT-STAGE-PLAN.json`

If M4-C stage plan lives elsewhere, pass its current path; it must retain the 34 action identifiers or the mapping must be reviewed and updated.

**Important:** numeric face weights, skeleton scale and lighting energies are unapproved lookdev starting values. The user must approve character identity and visual look before final rendering. Godot 4.7.2 engine runtime tests and actual artwork are not supplied in this docs-only handoff.
