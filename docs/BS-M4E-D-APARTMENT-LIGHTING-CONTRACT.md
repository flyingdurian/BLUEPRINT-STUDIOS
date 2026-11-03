# BLUEPRINT STUDIOS — M4E-D: Apartment Studio Lighting v2

**Status:** Look-dev recipe and integration contract. Not approved as final look until real materials and actor are rendered and reviewed. **Engine:** Godot 4.7.2, Forward+, no physical light units, 1080×1920 master, 30 fps, 2,490 frames. **Normative machine contract:** `docs/examples/BS-M4E-D-LIGHTING-PROFILES-v2.json`.

## 1. Hard constraints

- M4-C owns camera cuts, exact shot timing and frozen render manifest. M4-D owns voiceover, captions and MP4 output. Lighting is a versioned dependency loaded from the **frozen** render job, not dynamically edited during rendering.
- One `WorldEnvironment` per active viewport. Prefer a single render-level node; do not instantiate a second environment when swapping into the nonliteral host-desk set. Per-camera `CameraAttributes` overrides must be explicit and match the fixed-exposure policy.
- Lock **Forward+**, `rendering/lights_and_shadows/use_physical_light_units=false` before tuning numerical `light_energy`. If later adopting physical lumens/lux, the numeric intensities in this spec are not transferable without re-calibration.
- No auto-exposure, no depth-of-field, no lens glow, no SSR/SSIL, no motion blur or dynamic exposure during baseline acceptance. Global manual tonemapping `Environment.TONE_MAPPER_FILMIC` and exposure `1.0`. Camera auto exposure is a `CameraAttributes` property, **not `Environment.auto_exposure_*`**.
- All look-dev positions are expressed in meters, with actor root `(0,0,0)`, +Y up, camera generally along +Z looking toward −Z; camera/collider artist must inspect the real set before approving transforms. `DirectionalLight3D` position is immaterial to illumination, its **basis / direction** matters; `look_at()` is recommended to derive its orientation from named stage anchors.

## 2. Godot node hierarchy and configuration

```text
ProductionRenderRoot
├── WorldEnvironment (WorldEnvironment; one active instance)
├── LightingRig (Node3D)
│   ├── WindowKey (DirectionalLight3D)
│   ├── FaceFill (OmniLight3D)
│   └── RimAccent (SpotLight3D)
├── ActiveSet (ApartmentNook OR HostDesk)
├── Actor_Lead
└── CameraRig (Camera3D, manifest-controlled)
```

### Light baselines (`apartment_day` profile)

| Godot property | Window key / DirectionalLight3D | Fill / OmniLight3D | Rim / SpotLight3D |
|---|---|---|---|
| Color (suggested look) | `#fff0dc` (warm neutral) | `#e2ecff` (subtle cool) | `#e8edff` |
| `light_energy` | **1.45** | **0.35** | **0.24** |
| `shadow_enabled` | **true** | false | false |
| `position` (starting m) | `(-3.2,4.5,1.5)` | `(1.3,2.2,2.5)` | `(1.6,2.7,-1.8)` |
| `look_at` target (m) | `(0,1.3,0)` | n/a | `(0,1.35,0)` |
| Attenuation / cone | n/a | `omni_range=4`, `omni_attenuation=1` | `spot_range=5`, `spot_angle=32°` (radius, not full width), `spot_attenuation=1` |
| Other | `light_angular_distance=.6` | `light_specular=.35` | `spot_angle_attenuation=1`, `light_specular=.35` |

Key shadow settings: `directional_shadow_mode=SHADOW_PARALLEL_4_SPLITS`; `directional_shadow_max_distance=10m`; `directional_shadow_blend_splits=false`; `directional_shadow_fade_start=.85`; `shadow_blur=1.3`; `shadow_bias=.08`; `shadow_normal_bias=1.4`. Shadow bias/normal bias are intentionally *only starting values*: tune from rendered frames to avoid acne vs floating objects. Because only the key casts shadows, soft set grounding comes from the key and modest SSAO; never add a gratuitous second shadow-casting light simply to darken mug contact.

### WorldEnvironment values

| Target resource/property | Start value | Reason |
|---|---|---|
| `Environment.background_mode` | `BG_COLOR` | reproducible background |
| `Environment.background_color` | `#262d36` | muted neutral behind set |
| `Environment.ambient_light_source` | `AMBIENT_SOURCE_COLOR` | controlled fill |
| `Environment.ambient_light_color` | `#c6d0de` | neutral-cool bounce |
| `Environment.ambient_light_energy` | `0.35` | avoid crushed shadows |
| `Environment.reflected_light_source` | `REFLECTION_SOURCE_DISABLED` | avoid unstable specular sky reflections |
| `Environment.tonemap_mode` | `TONE_MAPPER_FILMIC` | fixed highlight roll-off |
| `Environment.tonemap_exposure` | `1.0` | locked exposure |
| `Environment.ssao_enabled` | `true` | local contact shading only |
| `Environment.ssao_intensity` | `0.65` | subtle, not muddy |
| `Environment.ssao_radius` | `0.45` | compact apartment set |
| `Environment.ssao_power` | `1.1` | conservative AO curve |
| `Environment.ssil_enabled`, `.ssr_enabled` | `false` | no screen-space flicker during acceptance |
| `Environment.glow_enabled`, `.fog_enabled` | `false` | no bloom on captions/phone UI |
| `CameraAttributesPractical.auto_exposure_enabled` | `false` | no bright/dark pumping across cuts |
| `CameraAttributesPractical.exposure_multiplier` | `1.0` | uniform camera response |
| `CameraAttributesPractical.dof_blur_near_enabled`, `dof_blur_far_enabled` | `false` | clear face and props |

### Quality-level ProjectSettings (locked per render profile)

```text
rendering/lights_and_shadows/use_physical_light_units = false
rendering/lights_and_shadows/directional_shadow/size = 4096
rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality = 2
rendering/lights_and_shadows/positional_shadow/atlas_size = 4096
rendering/anti_aliasing/quality/msaa_3d = 2  # Godot's 4x MSAA enum
rendering/anti_aliasing/quality/use_taa = false
rendering/anti_aliasing/quality/use_debanding = true
```

Apply and verify project-start-only settings **before** rendering; do not call `ProjectSettings.set_setting` in an already-running scene and assume the renderer reconfigures. Both 540×960 preview and 1080×1920 final inherit the same shot camera composition and color pipeline. Do not layer TAA on top of 4×MSAA without an A/B render—TAA is known to ghost some skinned meshes in Godot's current implementation.

### Shot profile overrides

- `apartment_day` — default for apartment. Use the same key direction and WorldEnvironment for all relevant shots.
- `phone_insert` — identical environment/key, fill energy `0.42`, rim energy `0.10`; do **not** brighten UI via physically exaggerated emission or bloom. Enable only on a shot explicitly named in manifest.
- `host_desk` — separate nonliteral geometry with key energy `1.20`, fill `0.50`, rim `0.18`, but **same Filmic tonemap, fixed exposure and single WorldEnvironment**.

No per-shot exposure curves. All numerical changes in the JSON must be reflected in a new look-dev profile version/hashes and pinned into the render job. Do not change M4-C `cameraPreset` definitions as a workaround for a light in the wrong place.

## 3. Materials and portrait rendering

Starting `StandardMaterial3D` roughness: stylized skin `.68`, sofa fabric `.86`, ceramic mug `.38`, phone frame `.42`; metallic on fabric must remain zero. Phone screen UI should usually be a dedicated overlay or controlled emissive texture, tested for clipping and legibility. Lighting must preserve identifiable skin tone, cheek silhouette, eyelid shading, fingers on props, and surface contact. No approval by numbers alone.

Canvas 1080×1920 native 9:16, preview 540×960. Composition guide is **editor-only**: x=130..950, y=230..1460 for principal subject/phone, not universally safe for any platform UI. Preserve M4-D caption area. Inspect SH_002 (mug contact), SH_005 (face/mug/hand), SH_009 (frozen close-up), SH_013 (drawer contact) and SH_014 (final deadpan) at full resolution and at 25% zoom.

## 4. Acceptance and regression tests

1. Confirm one active `WorldEnvironment`, no Camera3D auto-exposure override; all light properties set from validated JSON and one Filmic tonemapping profile.
2. Gray-card calibration: neutral swatch should maintain a consistent encoded output across equivalent camera changes; target < **±0.15 stops** *unintentional* exposure delta (instrumentation target, not artistic guarantee).
3. Shadows: no acne, Peter-Panning, unstable split transitions, facial jitter, mug/finger shadow clipping; key only casts shadows in initial profile.
4. Smartphone visibility: no bloom/white-out on screen, UI contrast survives downscaling; caption glyphs unaffected by Godot postfx.
5. Repeat rendering: at the same frame on the same GPU/driver/settings, lossless PNG hashes should match or trigger investigation. Do **not** promise byte-perfect cross-GPU determinism.
6. Technical visual review: RGB reference cards, skin color and exposure consistency at 1080×1920 for three representative shots; no unexpectedly crushed blacks, clipped face highlights or false contact shadows.
7. Lock look-dev revisions and manifest hashes before rendering all 2,490 frames. Reject final export if a required lighting resource is missing, instead of silently substituting unlit material.

**Source of truth:** current Godot stable class docs for `DirectionalLight3D`, `OmniLight3D`, `SpotLight3D`, `Light3D`, `Environment`, `WorldEnvironment`, `CameraAttributes` and `ProjectSettings`. Engine minor-version property availability must be checked on the installed Godot 4.7.2 binary during integration.
