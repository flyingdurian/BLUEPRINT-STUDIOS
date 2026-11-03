# BLUEPRINT STUDIOS — BS-M4-E: Production-Quality Render & Visual Polish

**Status:** Architectural specification / asset-production contract; not a claim that approved rigs, eight sculpted expressions, or final Godot renders exist.

**Engine:** Godot 4.7.2 stable, Godot project's Forward+ renderer; Blender (or comparable DCC) for source authoring; glTF 2.0 binary (`.glb`) for interchange; deterministic 30 fps Movie Maker rendering.

**Authoritative inputs:** Current SQLite project snapshot; SHA-256 pinned AssetVersion and MediaBlob records; the approved 14-shot M4-C stage plan; the completed M4-D narration/caption/video-assembly contract (inspect **actual current branch** before integration). Preserve total duration **83.000 seconds = 2,490 frames** and the M4-C half-open shot intervals. Do not change narration, camera cuts or timing as an incidental art pass.

**Release interpretation:** BS-M4E-A is a rig contract and pose-deformation test; B is authoring/interpreting the action library; C is eight facial poses; D is apartment lighting and hero materials; E is deterministic shot integration and final QC. Content is only called *production quality* after owner art signoff and a real end-to-end render. Distinguish technical readiness from artistic acceptance.

## 1. Architectural decisions

- **Director OS/SQLite** is the authoring source of truth. Assets exist as immutable verified blob hashes and logical AssetVersion references; shots hold `pinnedVersion`. Godot is a rendering worker and does not make unsaved production decisions.
- **One character rig**, multiple reusable animation clips and eight expression **presets** backed by a consistent set of named morph targets. This is not eight separate incompatible face meshes.
- **Shot staging plan** adds explicit `rigVersion`, `actionId`, `startFrameLocal`, `durationFrames`, `facePose`, `cameraPreset`, `propOwnership` / `propAnchor` and `lightPreset`. Freeform screenplay prose never directly drives transforms.
- **Frame-deterministic evaluation**: given `(manifest_hash, shot_id, local_frame)` the Godot worker should compute the same camera, pose, face, prop transform, light parameters and visibility every time. It must support seek-to-frame and out-of-order per-shot render testing; no reliance on accumulated delta, physics simulation or random wandering.
- **Two quality profiles**: `animation_review` at 540×960 (allow approved test assets only, clearly watermark PREVIEW) and `final` at 1080×1920 30 fps (only approved, verified assets and animation bindings). Preserve the exact 2,490-frame output and M4-D audio timing.
- **Original art IP**: the protagonist's identity, proportions, clothing, palette and apartment must be approved for BLUEPRINT STUDIOS and not reconstructed from the reference creator's identifiable avatar, costumes, blue sofa and shot language.

## 2. Source asset and production handoff pipeline

```text
DCC source (.blend or equivalent; owner-controlled)
  -> mesh/topology, UV, PBR materials, armature, morph sculpting, keyed clips
  -> rig validation (rest pose, naming, weights, face shape consistency)
  -> glTF binary export (.glb) with skin, named shape keys, animation actions
  -> import into Godot 4.7.2 as imported scene / animation libraries
  -> Godot wrapper PackedScene (.tscn), rebind textures/materials/cameras, add BoneAttachment3D sockets
  -> static pose test + attachment test + 8-face turntable + shot action tests
  -> media ingestion (M3) of export files, SHA-256 fingerprint, immutable AssetVersion
  -> project shot assets remain pinned; adopter explicitly chooses new version
  -> M4-C frozen manifest records exact versions and hashes
  -> M4-D remains responsible for VO/captions/final mux; M4-E feeds polished video frames.
```

Keep editable DCC files in a separate project source folder or versioned art repository, or import them as source-type media blobs. **A `.glb` is a production interchange artifact, not an editable character master**; SHA-256 protects its bytes, not the correctness of topology or retargeting.

Minimum deliverables per version: `lead_v001.blend`, `lead_v001.glb`, `rig_contract.json`, `facial_preset.json`, `actions_manifest.json`, `neutral-front.png`, `neutral-profile.png`, `expressions-contact-sheet.png`, `grip-test.mp4`, `rig_validation.json`, owner approval and exact content SHA-256. Don't ship a production asset merely because the file imported without errors.

### Mesh and import conventions

- Canonical scale: meters, Y-up in Godot; author to roughly 1.7 m **provisional** character height, approved during identity review. No negative scales, unapplied transforms or nonuniform rest-scale inherited by sockets. Front / axis conventions must be documented in `rig_contract.json`.
- Source exports with stable armature names and named skins; body meshes and face morph targets with matching vertex counts/order and UVs. Face morphs preserve the neutral mesh topology and do not alter UV indexing.
- GlTF import: check `Skeleton3D` hierarchy, `Skin` binds, animation paths, blend shape names and correct normal/tangent transforms. **Explicitly bind each MeshInstance3D to its Skeleton3D path**; Godot 4.6+ changed the default skeleton-path behavior. Failure is a hard blocker.
- For a stylized rig, use maximum four skinning influences per vertex as default production target; inspect deformation quality at shoulders, wrists, thighs and elbows. Corrective shapes optional only if identified visually and validated in Godot.
- Material identity: shader parameters and texture versions are separately versioned; no hidden dependency on texture files outside the frozen render job.

## 3. Protagonist skeleton — minimum canonical 40-bone contract

**Proposed deformation skeleton** (the artist may add twist/corrective bones, but must not remove/rename these canonical drivers without a schema migration):

| Group | Mandatory names | Count |
|---|---|---:|
| Central chain | `Root`, `Hips`, `Spine_01`, `Spine_02`, `Chest`, `Neck`, `Head`, `Jaw` | 8 |
| Shoulder + arms (both sides) | `Clavicle_{L,R}`, `UpperArm_{L,R}`, `LowerArm_{L,R}`, `Hand_{L,R}` | 8 |
| Legs and feet (both sides) | `UpperLeg_{L,R}`, `LowerLeg_{L,R}`, `Foot_{L,R}`, `Toe_{L,R}` | 8 |
| Hands and grip (each side) | `Thumb_01`, `Thumb_02`, `Index_01`, `Index_02`, `Middle_01`, `Middle_02`, `RingPinky_01` suffixed `_L` or `_R` | 14 |
| Gaze (both eyes) | `Eye_L`, `Eye_R` | 2 |
| **Total** | | **40** |

`CharacterRoot` is a **Node3D** for world placement and is not counted as a bone. Use left/right suffixes consistently. A neutral or A-pose is the animation reset baseline; record a dedicated seated rest pose as a reusable clip rather than making the skeleton's binding rest permanently seated.

### Skeleton node organization in Godot

```text
Actor_Lead (Node3D: instance identity and transform)
├── Visual (Node3D)
│   ├── Armature / Skeleton3D
│   │   ├── Grip_R (BoneAttachment3D -> Hand_R)
│   │   │   └── Socket_R (Node3D calibrated offset)
│   │   └── Grip_L (BoneAttachment3D -> Hand_L)
│   │       └── Socket_L (Node3D calibrated offset)
│   ├── BodyMesh (MeshInstance3D -> Skeleton3D)
│   ├── FaceMesh (MeshInstance3D -> Skeleton3D, morph targets)
│   └── EyeMeshes (can be skinned or child transforms)
├── AnimationPlayer (authored clips/AnimationLibrary)
├── AnimationTree (optional, only if frame-safe manual sampling is demonstrated)
└── RigDirector (script, frame-driven pose and facial evaluator)
```

Godot's `BoneAttachment3D` can follow a named bone and `MeshInstance3D` exposes named blend shapes. Use these documented mechanisms instead of per-frame guessing at wrist locations. The attached prop is a separate versioned scene instance, not baked permanently into the imported actor model.

### Prop anchors and continuity

| Binding | Owner/socket | Required authored test |
|---|---|---|
| `phone_grip_r` | `Hand_R` and its calibrated socket transform | Screen faces the actor in SH_003/006; fingertips do not pierce chassis |
| `phone_grip_l` | `Hand_L` for two-handed typing variant | Dynamic transition SH_007/012; no hand teleport |
| `mug_grip_r` | `Hand_R` with cup-specific grasp offset | Handle aligned; mug held upright during SH_002 sip; lip to rim while head inclines |
| `table_phone_rest` | Stage-owned Node3D in the apartment | Place phone on side table after SH_008, exactly once, no pop at handover |
| `drawer_phone_rest` | Stage-owned Node3D parented to drawer interior | SH_013 hand -> inside drawer at keyed release frame; remains there in SH_014 |

**No physics simulation for authored prop handoffs during Movie Maker**. Ownership is a deterministic function of `(shot,local_frame)`; evaluate socket transforms after skeletal pose evaluation and resolve prop world transform. A handoff stores/calculates an exact transition transform and is re-evaluable at any frame; avoid incremental `reparent()`-only state transitions that depend on playing from frame zero.

Continuity test cases: `SH_001` phone in hand; SH_002 table; SH_003/004 phone at ear; SH_006/007 phone at typing position; SH_008 table; SH_009 phone at call pose; SH_010 conceptual phone copies; SH_011/012 in hand; SH_013 drawer; SH_014 phone hidden inside closed drawer. **Each shot may have an independent setup pose**, so no hidden continuity assumptions between cuts.

## 4. Reusable animation library

Use namespaced AnimationLibrary IDs. Every source action in the existing stage plan (34 unique `actionIds`) must resolve to a published clip, a scripted expression/prop action, or a deliberate authored composite. Missing IDs are build blockers.

| Layer | Reusable actions | Typical duration target | Owner-signoff focus |
|---|---|---|---|
| Core body | `body/seated_neutral`, `body/sip`, `body/recline`, `body/slump`, `body/defensive_palm`, `body/shield_object`, `body/phone_to_ear`, `body/putdown`, `body/drawer_reach`, `body/host_chaos` | 0.4–2.5s | Silhouette, balanced spine, hand reach, sit/contact |
| Hands | `hands/thumb_tap`, `hands/type_loop`, `hands/scroll`, `hands/grip_phone`, `hands/grip_mug`, `hands/release` | 0.1–1.2s | Finger/phone registration and clear key shapes |
| Head/eyes | `head/look_at_mug`, `head/side_eye`, `head/hesitate`, `head/nod`, `head/freeze_nod`, `head/panic_swivel` | 0.15–1.0s | Gaze direction, believable exaggerated timing |
| Breathing/reactions | `react/exhale_relief`, `react/deadpan_hold`, `react/anticipation_hold`, `react/freeze`, `react/eyebrow_bounce` | 0.2–1.5s | Stillness must be intentional; no wiggle-cutout motion |
| Effects (no bones) | `ui/notification_count`, `ui/aunt_call`, `ui/chat_send`, `ui/thankyou_flood`, `ui/badge_reveal`, `ui/cut_to_black` | storyboard-keyed | Distinguish 2D overlay tracks from skeleton animation |

**Evaluation requirements:** Define action windows in integer local frames. For each output frame: identify shot -> reset to approved shot baseline -> evaluate body and hand pose clips at absolute local times -> evaluate head/gaze -> evaluate face preset blend -> evaluate attachment transforms -> evaluate camera and lights -> evaluate overlay cues. Random seeds are fixed in the frozen manifest. No `delta`-driven advancement or arbitrary autoplays in final mode; turn off physics-based jiggle or bake it to clips. For overlapping clips, define channel masks and explicit weights, never implicit last-writer-wins behavior.

`AnimationPlayer` plus imported AnimationLibrary clips is the recommended first implementation. `AnimationTree` is optional when manual deterministic evaluation is proven; idle/physics-driven tree playback can break exact-frame reproducibility. Use a neutral `RESET` pose and consistent rest transforms to prevent stale weights between shots.

## 5. Facial system: eight expressions, one topology

The eight requirements are **named emotion presets**; each is a weight vector over independent neutral-relative morph targets. The DCC artist must sculpt the `FaceMesh` target set with exact names from `docs/examples/BS-M4E-FACIAL-RIG.json` and verify it through Godot's `find_blend_shape_by_name()` before rendering. Numeric weights are **initial design targets**, subject to approved visual calibration.

**Core 22 target channels**: `BrowInnerUp`, `BrowOuterUp_L/R`, `BrowDown_L/R`, `EyeWide_L/R`, `EyeSquint_L/R`, `LidClose_L/R`, `CheekRaise_L/R`, `Smile_L/R`, `Frown_L/R`, `LipPress`, `MouthOpen`, `JawDrop`, `MouthTight`, `MouthCornerDown`. They should be available as distinct named morphs or equivalent verified controls, not merely labels in JSON. Two orbital eye bones provide gaze independently. `Jaw` bone is optional for future speech animation but should not double-apply `JawDrop` without a defined additive rule.

| Preset | Signature deformation | Shots | Main risk |
|---|---|---|---|
| `relieved` | Soft lids, subtle cheeks, mild smile; brows neutral | SH_001, SH_002 | Reads sleepy rather than victorious |
| `polite` | Small symmetrical smile, slight raised outer brow | SH_004, SH_009 (initial) | Too friendly/overacted; no tension |
| `suspicious` | Asymmetric squint/brow lower, tightened lip, offset gaze | SH_003, SH_005 | Too angry; eyebrow intersections |
| `confused` | Inner brow raised, slight mouth gap, one brow higher | SH_006 | Unreadable under phone insert; use when visible |
| `confident` | Defined small smile, cheek lift, focused eyelids | SH_007, SH_008 | Makes character smug rather than naive |
| `frozen` | Eyes open, lifted brows, jaw slack; still pupils | SH_009 | Eye bulge/mesh self-intersection |
| `deadpan` | Relaxed/flat brows, very slight lip compression, no blinking during hold | SH_011, SH_014 | Totally unexpressive; needs held gaze |
| `exhausted` | Inner brows, heavy lids, slight corners down, jaw lowered | SH_012, SH_013 | Same as sad; emphasize energy loss and posture |

Preset blending: interpolate **per shape** between named weight vectors over authored local-frame ranges. Start every shot in an explicitly named preset (or `neutral`) with no inherited weights. Clamp per-channel values to `[0,1]`; enforce compatible pairs such as EyeWide vs EyeSquint and Smile vs Frown by normalization or an artist-tested corrective system. Composite brow and cheek asymmetry only where tested. Blink keys are short authored events (e.g. 3–5 frames at 30 fps) and never substitute for eye contact or head movement.

**Face QA matrix:** render 8 presets as close-ups at frontal / 45-degree / profile angles, with all values recorded, at 540×960 and 1080×1920. Check vertex order, eyes/lips sealing, asymmetry, silhouette at mobile size, face under actual light, morph interpolation and extreme clip combination. A single missing blend shape blocks the rig version. Narration is mostly an external VO, not diegetic hero speech; full phoneme lip sync is not a release prerequisite for this pilot unless later dialogue direction is approved.

## 6. Apartment nook: art direction, geometry and materials

A single, original stylized apartment set serves SH_001/002/004/005/007/008/009/011/013/014; SH_003/006/012 rely on phone inserts; SH_010 uses a distinct nonliteral host-desk cutaway. The material palette, blocking and character identity need an owner-approved style anchor before a final rig/model bake. The intent is **warm domestic intimacy that shifts into comic entrapment**, not copying the benchmark creator's furniture colors or lighting setup.

**Minimum modeled dressing:** floor, simple wall sections, window + frame, sofa with credible seat/arm support, side table with animated drawer, mug, phone. Background shelves/art and practical lamps optional but must not clutter captions or compete with the face. Establish 3D prop contact: feet to floor, hips to sofa, mug to hand/table, phone to grip/drawer.

Recommended material baseline: stylized PBR (`StandardMaterial3D`), modest micro-roughness variation, no exaggerated metallic furniture, neutral nonspecular fabrics, optional small roughness and AO textures. Use original design colors after art review. Screen illumination should be an emissive material/Canvas overlay without harsh bloom; avoid overly reflective phone surfaces that obscure on-screen UI. A subtle fabric normal map is optional; at 9:16 phone scale it should not generate shimmer.

### Godot scene structure

```text
ApartmentNook (Node3D)
├── Geometry (Walls, Floor, Sofa, Table, Drawer, Window)
├── PropAnchors (TablePhoneRest, DrawerPhoneRest, MugRest)
├── ActorAnchor (LeadActor instance)
├── Lighting
│   ├── KeySun (DirectionalLight3D)
│   ├── FaceFill (OmniLight3D / SpotLight3D)
│   └── RimAccent (SpotLight3D)
├── WorldEnvironment (single active instance)
├── CameraRig (Camera3D presets keyed per shot)
└── OverlayRoot (2D caption-safe HUD, chat cards and production FX)
```

The host-desk scene should not instantiate a competing WorldEnvironment at the same time. Use a render-level WorldEnvironment with per-shot overrides if required. Keep visual assets and Godot scene definitions under `godot_render/`; binary exports and textures are staged from verified M3 versions into each render job.

## 7. Lighting and shading: Forward+ production baseline

**Target:** Godot 4.7.2 **Forward+**, 1080×1920, 30 fps, offline Movie Maker; no realtime-mobile budget requirement for rendering on desktop. Forward+ supports higher-quality shadow filtering and SSAO/SSIL compared with Mobile/Compatibility, but final render cost must be measured.

| Parameter | Starting prescription | Finalization rule |
|---|---|---|
| Key | `DirectionalLight3D` coming from the apartment window, neutral warm daylight (art target ~4500–5500 K), initial `light_energy` ~1.2–1.8 | Tune against gray/skin swatches; Godot light color uses RGB rather than a guaranteed Kelvin slider |
| Fill | Soft unshadowed `OmniLight3D` near camera-side, initial energy ~0.25–0.55 | Raise dark eye/hand detail without flattening the face |
| Rim | Subtle `SpotLight3D` opposite the key, energy ~0.2–0.45 | Only enough to separate character from wall; avoid bright outline halo |
| Shadows | Key shadows ON; **one dominant shadow-casting light** in first pass; sensible bias/normal-bias; max shadow distance restricted to the compact room (~8–12m) | No acne, Peter-Panning or floating feet/mug; inspect SH_002/005/013 |
| Filter | Forward+ PCSS soft shadows if supported and desirable; test against ordinary PCF | Use project-quality settings; avoid excessive PCSS radius or noisy temporal shadow motion |
| Global illumination | Start with controlled ambient + subtle SSAO. Optional static lightmap GI after rig/geometry stabilize. SSIL only after side-by-side comparison | Don't enable costly effects by default without quality evidence |
| Environment | `WorldEnvironment` with controlled ambient, consistent tonemapper (prefer Filmic or ACES after A/B), **auto exposure OFF** for deterministic shot-to-shot consistency | No visible brightness pumping when switching cameras |
| Color pipeline | Establish a locked output transform and reference gray/color chart for all cameras; slight warm highlights, cooler shadow tones | Consistent across shots and final FFmpeg encode, avoid crushed blacks |
| Screen surface | Modest phone emissive texture/2D UI overlay; no lens bloom on text | UI remains readable at native 1080×1920 and downscaled phone size |

Godot's `Environment` stores ambient/tonemapping/effects, while **some environment quality parameters live in Project Settings**, not the Environment resource. One active `WorldEnvironment` per scene tree; camera-specific overrides are deliberate and tracked. Beware auto exposure and reactive screen-space effects during camera hard cuts.

**Material review:** use diffuse, roughness, normal and ambient-occlusion maps conservatively. Validate physical contacts, fabric folds, silhouetted gestures and temporal antialiasing at smartphone viewing size. Motion blur/DOF off during acceptance until stable framing and subtitles are proven. If enabling TAA/MSAA, review dark eyeliner/hair/phone text for shimmer and ghosting; choose and lock one tested antialias profile.

## 8. Vertical 9:16 cinematic requirements

- Final canvas **1080×1920** (9:16). All 14 original shot boundaries fixed; preview 540×960 uses the same normalized camera matrices/framing rules.
- Frame characters for portrait: face, phone and hands must remain readable without extreme horizontal cropping. For 2D cutaway overlays, stage in camera-safe space and avoid UI edges.
- Provisional safety guides at 1080×1920: keep primary faces and meaningful phone screens within `x=130..950`, `y=230..1460`. Reserve UI-dependent margins especially at top and bottom; verify against actual platform previews. These are design guides, **not universal TikTok/Instagram safe zones**.
- Production face coverage: eye line generally upper-to-middle third for medium shots, not off-screen at punchlines; SH_009 needs two simultaneous readable faces/surfaces; SH_005 hand/mug gag visible without becoming microscopic.
- Every `CameraPreset` in M4-C has one world-space transform, lens/orthographic-size, target, near/far clip and deterministic keyframes stored in the stage plan. Never generate final camera movement by accumulating offsets each `_process` call.

## 9. Per-shot action/facial/environment gates

| Shot | Face / body requirement | Prop/camera/lighting QC |
|---|---|---|
| SH_001 | relief exhale, shoulders drop; `relieved` | Phone mute visible; close camera, screen readable |
| SH_002 | seated comfortable, sip mug; `relieved` | Mug rim aligned to lip; daylight key produces credible cast shadow |
| SH_003 | hesitant finger + one suspicious eye; `suspicious` | Phone ECU, no clipped finger; call UI occupies shot only |
| SH_004 | smile becomes tense; `polite` -> `confused` | Defensive palm near face but no intersection |
| SH_005 | look to cup, protect like secret; `suspicious` | Both hands/mug not clipping; essential visual gag readable |
| SH_006 | speed-scroll; `confused` when visible | Chat UI supports actual narration; no complex full-scene geometry needed |
| SH_007 | deliberate typing; `confident` | Phone remains in grip, exact send overlay cue |
| SH_008 | put phone down, recline; `confident` -> `relieved` | True pause/hold; phone rests and remains still |
| SH_009 | nod freezes mid-motion; `polite` -> `frozen` | Aunt avatar clearly a 2D call graphic, split composition legible |
| SH_010 | frantic host desk performance; `confused`/`frozen` exaggerated | Clearly nonliteral scene; seven ringing phones as cloned props/overlays |
| SH_011 | long stare; `deadpan` | Thank-you UI doesn't cover eyebrows during key laugh |
| SH_012 | refusal stalls and shoulders sink; `exhausted` | Phone typing, instant reply, screen not occluded |
| SH_013 | phone in drawer; `exhausted` | Deterministic grip release then drawer closure |
| SH_014 | badge reveal then motionless stare; `deadpan` | Final phone remains hidden in closed drawer; hard cut at frame 2490 |

## 10. Deterministic renderer integration

The BS-M4C `PilotDirectorRunner.gd` remains the timing oracle; BS-M4D audio/caption compilation remains the finishing oracle. Implement `ProductionShotDirector.gd` and `ActorRigController.gd` as new modules and let M4C call them only when the `quality=final` manifest requires it. Don't overwrite M4-B proof or M4-C previs runner as a 'shortcut'. A production frame is valid only when all required action IDs, camera presets, pinned versions, shape targets, and prop sockets are verified at compile time.

**Recommended renderer schedule:** 

1. Load frozen manifest and validate project revision, all asset blob hashes and approved `stagePlanHash`.
2. Load only approved `.glb`/materials/audio/overlay assets staged under the render job; pre-import them into a Godot-local resource environment before offline rendering.
3. Validate all 40 canonical bones, 22 morph targets, action IDs and sockets; fail closed on missing production dependencies.
4. Per frame `n`: locate shot `[startFrame,endFrameExclusive)`, compute `local=n-start`, evaluate all authored controls at `local` exactly, pose skeleton and face, place props via anchors, select camera and lighting state, update graphic overlays and render.
5. Record 2490 frames, postprocess through existing M4-D pipeline and verify decoded frames, audio duration, caption timing, shot transitions and frozen manifest digest.

**Performance optimization**: precompute active shot lookup, retargeted animation sample data and face interpolation curves; cache shader compilation and media loads before initiating Movie Maker output. Never alter hashes or production assets while rendering.

## 11. Delivery and approval gates

| Gate | Deliverables | Hard pass condition |
|---|---|---|
| **M4E-A Rig** | Rigged source, `.glb`, skeleton validation, attachment scene, turnaround | 40 canonical bones; exact rest, tested pose deformation, no clipped grips |
| **M4E-B Motion** | Action library, action registry, 14-shot sample clips | **34 / 34 stage-plan action IDs resolved**; no frozen/static cutouts; deterministic frame seek |
| **M4E-C Face** | 22 morph targets, 8 preset map, three-angle face sheet | 8 distinct readable emotions, no morph/normal tearing, no inherited weights |
| **M4E-D Environment** | Godot apartment set, 3 light profile renders, material lookdev | Mobile legibility at 540×960; skin/props properly lit; shadow defects resolved |
| **M4E-E Integration** | Exact pinned job + 2490-frame final frames + M4-D mux + QC report | All 14 shots correct, 83s runtime, owner visual approval, existing backend/frontend/render tests pass |

**Owner signoffs:** Character identity before sculpt/rig; rig deformation/contact before motion library; eight face poses before full-shot authoring; apartment/lighting A/B before all-frame render; final 14-shot proof before publication. The owner can reject a rig or look without undermining the technical state of M4-C/M4-D.

**Regression tests:** strict versions/hashes; all stage action IDs mapped; 8 facial presets compile; 40 skeleton bones; visible hand contact in SH_002/005/013; shots 1/8/9/14 all have proper camera/light transitions; seek-to-frame invariance at 0,119,120,1379,1380,2489; render frame count 2490; no Godot errors; captions safe. Compare selected frames against *approved* look references, not unrelated AI outputs.

## 12. Integration warning / current visibility

The GitHub default branch inspected on 2026-11-02 still exposes older BS-M2 backend and the previous stage-plan handoff, while the user's reported M4-C/M4-D verification may reside on a branch or local working tree. **Cursor must inspect the actual merged branch/working tree before implementation and reconcile any changed manifest, media or mux contracts.** No speculative replacement of working source files.

## Official implementation references

- Godot 4.7.2 release: https://godotengine.org/article/maintenance-release-godot-4-7-2/
- MeshInstance3D blend shapes: https://docs.godotengine.org/en/4.7/classes/class_meshinstance3d.html
- BoneAttachment3D: https://docs.godotengine.org/en/4.7/classes/class_boneattachment3d.html
- AnimationPlayer and libraries: https://docs.godotengine.org/en/4.7/classes/class_animationplayer.html
- glTF/3D scene import: https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html
- WorldEnvironment: https://docs.godotengine.org/en/4.7/classes/class_worldenvironment.html
- Environment/lighting: https://docs.godotengine.org/en/4.7/tutorials/3d/environment_and_post_processing.html
