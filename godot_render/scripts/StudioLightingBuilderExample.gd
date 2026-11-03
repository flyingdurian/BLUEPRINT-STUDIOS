extends Node3D
## M4E-D example. Attach to LightingRig. Existing children:
## WindowKey:DirectionalLight3D, FaceFill:OmniLight3D, RimAccent:SpotLight3D
## WorldEnvironment is a sibling, accessed using the exported NodePath.
## Load validated profile JSON once; call apply_profile(id) at a shot boundary.

@export var world_environment_path: NodePath = ^"../WorldEnvironment"

var _profiles: Dictionary = {}
var _baseline: Dictionary = {}
var _initialized: bool = false

func initialize_contract(path: String) -> bool:
    _initialized = false
    if not FileAccess.file_exists(path):
        push_error("M4E-D: lighting contract missing: " + path)
        return false
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
    if typeof(parsed) != TYPE_DICTIONARY:
        return false
    var contract: Dictionary = parsed
    if str(contract.get("schemaVersion", "")) != "blueprint.apartment_lighting.v2":
        return false
    _profiles = contract.get("profiles", {})
    _baseline = _profiles.get("apartment_day", {})
    var world: WorldEnvironment = get_node_or_null(world_environment_path) as WorldEnvironment
    if world == null or _baseline.is_empty():
        push_error("M4E-D: missing WorldEnvironment / apartment daylight profile")
        return false
    var world_data: Dictionary = contract.get("globalEnvironment", {})
    var props: Dictionary = world_data.get("environment", {})
    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color.html(str(props.get("background_color", "#262d36")))
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color.html(str(props.get("ambient_light_color", "#c6d0de")))
    env.ambient_light_energy = float(props.get("ambient_light_energy", 0.35))
    env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
    env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
    env.tonemap_exposure = float(props.get("tonemap_exposure", 1.0))
    env.ssao_enabled = bool(props.get("ssao_enabled", true))
    env.ssao_intensity = float(props.get("ssao_intensity", 0.65))
    env.ssao_radius = float(props.get("ssao_radius", 0.45))
    env.ssao_power = float(props.get("ssao_power", 1.1))
    env.ssil_enabled = false
    env.ssr_enabled = false
    env.glow_enabled = false
    env.fog_enabled = false
    world.environment = env
    var attributes := CameraAttributesPractical.new()
    attributes.auto_exposure_enabled = false
    attributes.exposure_multiplier = 1.0
    attributes.dof_blur_near_enabled = false
    attributes.dof_blur_far_enabled = false
    world.camera_attributes = attributes
    _initialized = true
    return apply_profile("apartment_day")


func _vector3(value: Array) -> Vector3:
    return Vector3(float(value[0]), float(value[1]), float(value[2]))


func apply_profile(id: String) -> bool:
    if not _initialized or not _profiles.has(id):
        push_error("M4E-D: unavailable lighting profile " + id)
        return false
    var selected: Dictionary = _profiles[id]
    var merged: Dictionary = _baseline.duplicate(true)
    var overrides: Dictionary = selected.get("overrides", {})
    if id != "apartment_day":
        merged = merged.merged(overrides, true)
    var key: DirectionalLight3D = get_node_or_null("WindowKey") as DirectionalLight3D
    var fill: OmniLight3D = get_node_or_null("FaceFill") as OmniLight3D
    var rim: SpotLight3D = get_node_or_null("RimAccent") as SpotLight3D
    if key == null or fill == null or rim == null:
        push_error("M4E-D: missing one or more mandatory light nodes")
        return false
    var k: Dictionary = merged["key"]
    var f: Dictionary = merged["fill"]
    var r: Dictionary = merged["rim"]
    key.position = _vector3(k["positionMeters"])
    key.look_at(_vector3(k["lookAtMeters"]), Vector3.UP)
    key.light_energy = float(k["light_energy"])
    key.light_color = Color.html(str(k["light_color"]))
    key.light_angular_distance = float(k["light_angular_distance"])
    key.shadow_enabled = true
    key.shadow_blur = float(k["shadow_blur"])
    key.shadow_bias = float(k["shadow_bias"])
    key.shadow_normal_bias = float(k["shadow_normal_bias"])
    key.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
    key.directional_shadow_max_distance = float(k["directional_shadow_max_distance"])
    key.directional_shadow_blend_splits = false
    key.directional_shadow_fade_start = float(k["directional_shadow_fade_start"])
    fill.position = _vector3(f["positionMeters"])
    fill.light_color = Color.html(str(f["light_color"]))
    fill.light_energy = float(f["light_energy"])
    fill.omni_range = float(f["omni_range"])
    fill.omni_attenuation = float(f["omni_attenuation"])
    fill.light_specular = float(f["light_specular"])
    fill.shadow_enabled = false
    rim.position = _vector3(r["positionMeters"])
    rim.look_at(_vector3(r["lookAtMeters"]), Vector3.UP)
    rim.light_color = Color.html(str(r["light_color"]))
    rim.light_energy = float(r["light_energy"])
    rim.spot_range = float(r["spot_range"])
    rim.spot_angle = float(r["spot_angle"])
    rim.spot_attenuation = float(r["spot_attenuation"])
    rim.spot_angle_attenuation = float(r["spot_angle_attenuation"])
    rim.light_specular = float(r["light_specular"])
    rim.shadow_enabled = false
    return true
