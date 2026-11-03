# BLUEPRINT STUDIOS — M4E-C: Facial Morph Contract v2

**Status:** Design contract; numerical authoring values are provisional and require original-asset visual approval. **Engine:** Godot 4.7.2 Forward+, **master:** 1080×1920, 30 fps. **Upstream:** M4E-A's canonical 40-bone protagonist, M4E-B's frame-deterministic actions, M4-C's shot manifest. Do not modify M4-C timing (14 shots, 2,490 frames) or M4-D narration/caption mix.

## 1. Data authority and files

`docs/examples/BS-M4E-C-FACE-PRESETS-v2.json` is the normative contract. It is derived from the already-approved **naming convention and design baseline** in `BS-M4E-FACIAL-RIG.json` and preserves its original sparse nonzero weights, but expands every preset to **22 explicit channels**. This avoids state leakage when a nonzero blend shape from a previous shot is not reset. New names or weights require a versioned contract migration and visual review; do not silently rename artist-authored morphs to approximate ARKit or Blender aliases. All casing is significant.

Required node hierarchy (relative paths subject to M4E-A's actual rig):

```text
Actor_Lead
└── Visual
    ├── Skeleton3D
    └── FaceMesh (MeshInstance3D)
```

The 40 body bones include `Jaw`, `Eye_L`, and `Eye_R` as established earlier. The morph system is layered *on top* of those controls, never a second skeleton. The face mesh's `skeleton` property must be explicitly linked to the imported Skeleton3D, including for Godot 4.6+ import behavior.

## 2. Exact 22 morph channels (case-sensitive)

| Index* | Shape key | Driven region | Contract |
|---:|---|---|---|
| 0 | `BrowInnerUp` | Both inner brows | positive lift |
| 1 | `BrowOuterUp_L` | Left outer brow | isolated lift |
| 2 | `BrowOuterUp_R` | Right outer brow | isolated lift |
| 3 | `BrowDown_L` | Left brow | lower |
| 4 | `BrowDown_R` | Right brow | lower |
| 5 | `EyeWide_L` | Left eye | eye opening |
| 6 | `EyeWide_R` | Right eye | eye opening |
| 7 | `EyeSquint_L` | Left eye | tighten/squint |
| 8 | `EyeSquint_R` | Right eye | tighten/squint |
| 9 | `LidClose_L` | Left eyelid | close/blink |
| 10 | `LidClose_R` | Right eyelid | close/blink |
| 11 | `CheekRaise_L` | Left cheek | cheek elevation |
| 12 | `CheekRaise_R` | Right cheek | cheek elevation |
| 13 | `Smile_L` | Left mouth corner | rise |
| 14 | `Smile_R` | Right mouth corner | rise |
| 15 | `Frown_L` | Left mouth corner | frown |
| 16 | `Frown_R` | Right mouth corner | frown |
| 17 | `LipPress` | Both lips | lip closure/tension |
| 18 | `MouthOpen` | Mouth opening | part lips |
| 19 | `JawDrop` | Jaw-area morph | broad opening |
| 20 | `MouthTight` | Mouth | horizontal compression |
| 21 | `MouthCornerDown` | Both corners | pull downward |

*Indices denote canonical JSON serialization order **not** imported Godot shape indices. Always use `MeshInstance3D.find_blend_shape_by_name(StringName(name))`; error on `-1`. Every channel value is an absolute normalized float in `[0.0,1.0]`, neutral=0. Do not multiply by 100 when calling Godot. If DCC uses Blender shape keys, ensure glTF exports preserve names and topology exactly. Verify left/right from the **character's perspective**, not the camera's.

## 3. Expression preset data

Eight named expressions are required, keyed exactly `relieved`, `polite`, `suspicious`, `confused`, `confident`, `frozen`, `deadpan`, `exhausted`. Each `presets[name].weights` object must contain all 22 keys and **no extras**. The normative full **22×8=176 values** are in `BS-M4E-C-FACE-PRESETS-v2.json`.

Compact table of **nonzero** coefficients (every channel not shown here is explicitly `0.0` in JSON):

| Preset | Nonzero weights |
|---|---|
| relieved | `LidClose_L=.15`, `LidClose_R=.15`, `Smile_L=.35`, `Smile_R=.35`, `CheekRaise_L=.20`, `CheekRaise_R=.20` |
| polite | `BrowOuterUp_L=.12`, `BrowOuterUp_R=.12`, `Smile_L=.38`, `Smile_R=.38`, `LipPress=.14` |
| suspicious | `BrowDown_L=.55`, `BrowDown_R=.20`, `EyeSquint_L=.50`, `EyeSquint_R=.24`, `LipPress=.22`, `MouthTight=.40` |
| confused | `BrowInnerUp=.70`, `BrowOuterUp_L=.34`, `BrowOuterUp_R=.16`, `EyeWide_R=.25`, `MouthOpen=.20` |
| confident | `Smile_L=.50`, `Smile_R=.50`, `CheekRaise_L=.34`, `CheekRaise_R=.34`, `EyeSquint_L=.12`, `EyeSquint_R=.12` |
| frozen | `BrowInnerUp=.35`, `BrowOuterUp_L=.65`, `BrowOuterUp_R=.65`, `EyeWide_L=.80`, `EyeWide_R=.80`, `JawDrop=.55`, `MouthOpen=.22` |
| deadpan | `LipPress=.18`, `BrowDown_L=.08`, `BrowDown_R=.08`, `LidClose_L=.10`, `LidClose_R=.10` |
| exhausted | `LidClose_L=.42`, `LidClose_R=.42`, `BrowInnerUp=.28`, `Frown_L=.25`, `Frown_R=.25`, `MouthCornerDown=.38`, `JawDrop=.08` |

### Interpretation / conflicts

- Smile vs frown (same side), wide vs squint (same eye), lid close vs eye wide, and lip press vs mouth open are conflict pairs. The eight authored presets must not activate competing directions strongly at once. An authored combination may intentionally override this only with a documented corrective deformation and visual approval.
- `JawDrop` as a morph **does not authorize simultaneously rotating the `Jaw` bone**. Use a single master jaw driver or a weighted, audited combination; prevent double opening.
- Eye gaze is handled by bones `Eye_L`/`Eye_R` (clamped to ±20° yaw and ±12° pitch), not counted among these 22 morphs.
- Blink is a deterministic optional overlay on lid-close channels, exactly 4 frames by default; schedule per shot in the manifest. `frozen` and `deadpan` have no **unscheduled** blink. No random time-based blinks during Movie Maker.
- If an action requires a 23rd shape, keep it a separately versioned corrective shape and update the schema; do **not** silently make the contract '22 required plus arbitrary unknowns' in production mode.

## 4. Frame deterministic sampling

Use the shot’s local **integer** frame `n` (0-based). Every facial state is independently calculable for an arbitrary frame—no previous-frame cache, elapsed `delta`, tween that requires sequential playback, or random expression selection.

For a cue `[startLocalFrame,endLocalFrameExclusive)`, define `u=clamp((n-start)/(end-start),0,1)` and `e=u²(3−2u)`. Sample each channel as `w=(1−e)*presetA[c]+e*presetB[c]`, clamp to 0..1, and overwrite **all 22** channels on every evaluated frame. A held pose has `from==to`; outside the last authored range, explicit shot hold/end state should be defined. Do not derive a new shot's first pose from the previous shot's last pose: every shot can be evaluated independently.

Three example performance cues are supplied in `BS-M4E-CD-SHOT-BINDINGS-v1.json`: SH_005 confused→suspicious (mug); SH_009 polite→frozen (no blink); SH_014 exhausted→deadpan (no blink). Those cue times are **proposed look-dev timings** and require animator approval; they do not modify the established M4-C shot ranges.

### Integration contract

Add a dedicated `FaceMorphController` to the M4E-A rig wrapper; load the JSON contract at renderer initialization, verify its 22 target names and run self-test poses. The M4-C director supplies `(shotId, localFrame, faceCue)` to the controller; its output is a complete shape-weight vector. The shape controller never calls `get_tree().create_tween()` for production playback. A reference GDScript is included under `godot_render/scripts/FaceMorphControllerExample.gd` **as example-only**; do not overwrite any Cursor-created module without reconciliation.

## 5. Acceptance / visual tests

1. Import test on actual `.glb`: all 22 names exist in `FaceMesh`, no duplicate named shapes, expected mesh rest topology, explicit skeleton path and neutral pose.
2. Contact sheet: neutral plus all 8 expressions at front, 3/4, and side views, lit identically with M4E-D's look-dev profile. Submit at full resolution for owner review.
3. Transitions: SH_004 polite→confused, SH_009 polite→frozen at frame 24, SH_014 exhausted→deadpan; no popping, crossfades or face drift; no unscheduled blinking in frozen/deadpan.
4. Destructive negative test: remove a required target or rename casing; production validation **must fail closed**. An extra unapproved face channel requires an explicit review warning.
5. Random seek test: sample local frames in shuffled order and compare weights numerically within `1e−6`. Verify the returned state is unaffected by play history.
6. Deformation review: eyelids do not pierce eyeballs; lips do not intersect; head shape and character identity remain consistent through all expressions and relevant prop contact.

**Sources:** Godot `MeshInstance3D` official class reference (find blend shapes by name, get/set values) and 4.x glTF importer behavior. Actual runtime integration remains unverified until the M4E-A rig is provided.
