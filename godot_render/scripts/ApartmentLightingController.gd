extends Node3D
## M4E-D production lighting rig.
## One WorldEnvironment, three lights, Filmic tonemap, fixed exposure.
## Profile overrides are deep-merged onto apartment_day at the shot boundary.
## This scene does not change the proof project's renderer.

const PROFILE_IDS: PackedStringArray = ["apartment_day", "phone_insert", "host_desk"]

@export var world_environment_path: NodePath = ^"../WorldEnvironment"

var _profiles: Dictionary = {}
var _baseline: Dictionary = {}
var _shots: Array = []
var _spec_status: String = ""
var _initialized: bool = false


func _ready() -> void:
	var path: String = _default_contract_path()
	if FileAccess.file_exists(path):
		initialize_contract(path)


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
	_spec_status = str(contract.get("specStatus", ""))
	var profiles_variant: Variant = contract.get("profiles", {})
	if typeof(profiles_variant) != TYPE_DICTIONARY:
		return false
	_profiles = profiles_variant
	var declared: Array = _profiles.keys()
	if declared.size() != PROFILE_IDS.size():
		push_error("M4E-D: lighting profile set does not match the contract")
		return false
	for profile_index in PROFILE_IDS.size():
		if not _profiles.has(PROFILE_IDS[profile_index]):
			push_error("M4E-D: missing lighting profile " + PROFILE_IDS[profile_index])
			return false
	var baseline_variant: Variant = _profiles.get("apartment_day", {})
	if typeof(baseline_variant) != TYPE_DICTIONARY:
		return false
	_baseline = baseline_variant
	var world: WorldEnvironment = get_node_or_null(world_environment_path) as WorldEnvironment
	if world == null or _baseline.is_empty():
		push_error("M4E-D: missing WorldEnvironment or apartment daylight profile")
		return false
	if not _apply_environment(world, contract):
		return false
	if not _load_shots(path.get_base_dir().path_join("BS-M4E-CD-SHOT-BINDINGS-v1.json")):
		return false
	_initialized = true
	return apply_profile("apartment_day")


func contract_ready() -> bool:
	return _initialized


func lookdev_approved() -> bool:
	return _spec_status == "LOOKDEV_APPROVED"


func renderer_is_forward_plus() -> bool:
	return str(ProjectSettings.get_setting("rendering/renderer/rendering_method", "")) == "forward_plus"


func final_render_allowed() -> bool:
	return _initialized and lookdev_approved() and renderer_is_forward_plus()


func apply_for_shot(shot_id: String) -> bool:
	for entry_variant in _shots:
		if typeof(entry_variant) != TYPE_DICTIONARY:
			continue
		var shot: Dictionary = entry_variant
		if str(shot.get("shotId", "")) == shot_id or str(shot.get("code", "")) == shot_id:
			return apply_profile(str(shot.get("lightingProfile", "")))
	push_error("M4E-D: no lighting profile for " + shot_id)
	return false


func apply_profile(id: String) -> bool:
	if not _initialized or not _profiles.has(id):
		push_error("M4E-D: unavailable lighting profile " + id)
		return false
	var selected: Dictionary = _profiles[id]
	var merged: Dictionary = _baseline.duplicate(true)
	if id != "apartment_day":
		var overrides_variant: Variant = selected.get("overrides", {})
		if typeof(overrides_variant) != TYPE_DICTIONARY:
			return false
		merged = _deep_merge(merged, overrides_variant)
	var key: DirectionalLight3D = get_node_or_null("WindowKey") as DirectionalLight3D
	var fill: OmniLight3D = get_node_or_null("FaceFill") as OmniLight3D
	var rim: SpotLight3D = get_node_or_null("RimAccent") as SpotLight3D
	if key == null or fill == null or rim == null:
		push_error("M4E-D: missing one or more mandatory light nodes")
		return false
	var key_data: Dictionary = merged["key"]
	var fill_data: Dictionary = merged["fill"]
	var rim_data: Dictionary = merged["rim"]
	if str(key_data.get("directional_shadow_mode", "")) != "SHADOW_PARALLEL_4_SPLITS":
		push_error("M4E-D: unsupported directional shadow mode")
		return false
	key.position = _vector3(key_data["positionMeters"])
	key.look_at(_vector3(key_data["lookAtMeters"]), Vector3.UP)
	key.light_energy = float(key_data["light_energy"])
	key.light_color = Color.html(str(key_data["light_color"]))
	key.light_angular_distance = float(key_data["light_angular_distance"])
	key.shadow_enabled = bool(key_data["shadow_enabled"])
	key.shadow_blur = float(key_data["shadow_blur"])
	key.shadow_bias = float(key_data["shadow_bias"])
	key.shadow_normal_bias = float(key_data["shadow_normal_bias"])
	key.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	key.directional_shadow_max_distance = float(key_data["directional_shadow_max_distance"])
	key.directional_shadow_blend_splits = bool(key_data["directional_shadow_blend_splits"])
	key.directional_shadow_fade_start = float(key_data["directional_shadow_fade_start"])
	fill.position = _vector3(fill_data["positionMeters"])
	fill.light_color = Color.html(str(fill_data["light_color"]))
	fill.light_energy = float(fill_data["light_energy"])
	fill.omni_range = float(fill_data["omni_range"])
	fill.omni_attenuation = float(fill_data["omni_attenuation"])
	fill.light_specular = float(fill_data["light_specular"])
	fill.shadow_enabled = bool(fill_data["shadow_enabled"])
	rim.position = _vector3(rim_data["positionMeters"])
	rim.look_at(_vector3(rim_data["lookAtMeters"]), Vector3.UP)
	rim.light_color = Color.html(str(rim_data["light_color"]))
	rim.light_energy = float(rim_data["light_energy"])
	rim.spot_range = float(rim_data["spot_range"])
	rim.spot_angle = float(rim_data["spot_angle"])
	rim.spot_attenuation = float(rim_data["spot_attenuation"])
	rim.spot_angle_attenuation = float(rim_data["spot_angle_attenuation"])
	rim.light_specular = float(rim_data["light_specular"])
	rim.shadow_enabled = bool(rim_data["shadow_enabled"])
	return true


func _apply_environment(world: WorldEnvironment, contract: Dictionary) -> bool:
	var world_data: Dictionary = contract.get("globalEnvironment", {})
	var props: Dictionary = world_data.get("environment", {})
	var attributes_data: Dictionary = world_data.get("cameraAttributes", {})
	if str(props.get("tonemap_mode", "")) != "TONE_MAPPER_FILMIC":
		push_error("M4E-D: tonemap must be Filmic")
		return false
	if bool(props.get("ssil_enabled", false)) or bool(props.get("ssr_enabled", false)):
		push_error("M4E-D: SSIL and SSR stay off")
		return false
	if bool(props.get("glow_enabled", false)) or bool(props.get("fog_enabled", false)):
		push_error("M4E-D: glow and fog stay off")
		return false
	if bool(attributes_data.get("auto_exposure_enabled", true)):
		push_error("M4E-D: auto exposure stays off")
		return false
	var env: Environment = Environment.new()
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
	var attributes: CameraAttributesPractical = CameraAttributesPractical.new()
	attributes.auto_exposure_enabled = false
	attributes.exposure_multiplier = float(attributes_data.get("exposure_multiplier", 1.0))
	attributes.dof_blur_near_enabled = false
	attributes.dof_blur_far_enabled = false
	world.camera_attributes = attributes
	return true


func _deep_merge(base: Dictionary, overrides: Dictionary) -> Dictionary:
	var merged: Dictionary = base.duplicate(true)
	var keys: Array = overrides.keys()
	for index in keys.size():
		var key: Variant = keys[index]
		var override_value: Variant = overrides[key]
		if typeof(override_value) == TYPE_DICTIONARY and typeof(merged.get(key, null)) == TYPE_DICTIONARY:
			var child_base: Dictionary = merged[key]
			var child_over: Dictionary = override_value
			merged[key] = _deep_merge(child_base, child_over)
		else:
			merged[key] = override_value
	return merged


func _load_shots(path: String) -> bool:
	if not FileAccess.file_exists(path):
		push_error("M4E-D: shot binding file missing: " + path)
		return false
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		return false
	var contract: Dictionary = parsed
	var examples_variant: Variant = contract.get("examples", [])
	if typeof(examples_variant) != TYPE_ARRAY:
		return false
	_shots = examples_variant
	return true


func _vector3(value: Array) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


func _default_contract_path() -> String:
	var project: String = ProjectSettings.globalize_path("res://").trim_suffix("/").trim_suffix("\\")
	return project.get_base_dir().path_join("docs/examples/BS-M4E-D-LIGHTING-PROFILES-v2.json")
