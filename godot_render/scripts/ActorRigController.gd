extends Node
## Samples one production frame from the locked 14-shot plan.
## The result depends on the integer frame. It does not accumulate elapsed time.

const TOTAL_FRAMES := 2490

var _actor: Node = null
var _shots: Array = []
var _shot_index: PackedInt32Array = PackedInt32Array()
var _shot_bindings: Dictionary = {}
var _actions_resolved: bool = false
var _lighting_approved: bool = false
var _contracts_ready: bool = false


func bind_actor(actor: Node) -> void:
	_actor = actor


func load_contracts() -> bool:
	_contracts_ready = false
	_shots.clear()
	_shot_bindings.clear()
	_shot_index = PackedInt32Array()
	var plan: Dictionary = _read_json(_repo_file("BS-M4-PILOT-STAGE-PLAN.json"))
	var actions: Dictionary = _read_json(_repo_file("BS-M4E-ACTION-BINDINGS.json"))
	var lights: Dictionary = _read_json(_repo_file("BS-M4E-D-LIGHTING-PROFILES-v2.json"))
	if plan.is_empty() or actions.is_empty() or lights.is_empty():
		return false
	var shot_rows: Variant = plan.get("shots", [])
	var binding_rows: Variant = actions.get("shots", [])
	if typeof(shot_rows) != TYPE_ARRAY or shot_rows.size() != 14 or typeof(binding_rows) != TYPE_ARRAY:
		return false
	_shots = shot_rows
	_shot_index.resize(TOTAL_FRAMES)
	_shot_index.fill(-1)
	var cursor: int = 0
	for shot_number in _shots.size():
		var shot: Dictionary = _shots[shot_number]
		var start_frame: int = int(shot.get("startFrame", -1))
		var duration: int = int(shot.get("durationFrames", -1))
		var end_frame: int = start_frame + duration
		if start_frame != cursor or duration < 1 or end_frame > TOTAL_FRAMES:
			return false
		for frame in range(start_frame, end_frame):
			_shot_index[frame] = shot_number
		cursor = end_frame
	if cursor != TOTAL_FRAMES:
		return false
	for entry_variant in binding_rows:
		if typeof(entry_variant) != TYPE_DICTIONARY:
			return false
		var binding: Dictionary = entry_variant
		_shot_bindings[str(binding.get("code", ""))] = binding
	_actions_resolved = _registry_is_authored(actions)
	_lighting_approved = str(lights.get("specStatus", "")) == "LOOKDEV_APPROVED"
	_contracts_ready = true
	return true


func production_ready() -> bool:
	if not _contracts_ready or not _actions_resolved or not _lighting_approved:
		return false
	if _actor == null or str(_actor.get_meta("rig_status", "")) != "OWNER_APPROVED":
		return false
	var face: Node = _actor.get_node_or_null("FaceMorphController")
	if face == null or not bool(face.call("production_shapes_ready")):
		return false
	return true


func evaluate_frame(frame: int) -> Dictionary:
	if not _contracts_ready or frame < 0 or frame >= TOTAL_FRAMES:
		return {"ok": false, "frame": frame}
	var shot_number: int = _shot_index[frame]
	if shot_number < 0:
		return {"ok": false, "frame": frame}
	var shot: Dictionary = _shots[shot_number]
	var code: String = str(shot.get("code", ""))
	var local_frame: int = frame - int(shot.get("startFrame", 0))
	var binding: Dictionary = _shot_bindings.get(code, {})
	var camera: Dictionary = shot.get("camera", {})
	var preset: String = str(camera.get("preset", ""))
	if str(binding.get("cameraPreset", "")) != preset:
		return {"ok": false, "frame": frame, "code": code, "error": "camera preset does not match the stage plan"}
	var performance: Dictionary = shot.get("performance", {})
	var prop_ok: bool = false
	var phone: Vector3 = Vector3.ZERO
	if _actor != null:
		var prop_variant: Variant = _actor.call("evaluate", code, local_frame)
		if typeof(prop_variant) == TYPE_DICTIONARY:
			var prop: Dictionary = prop_variant
			prop_ok = bool(prop.get("ok", false))
			var phone_variant: Variant = prop.get("phone_position", Vector3.ZERO)
			if phone_variant is Vector3:
				phone = phone_variant
	return {
		"ok": true,
		"frame": frame,
		"code": code,
		"shotId": str(shot.get("shotId", "")),
		"localFrame": local_frame,
		"cameraPreset": preset,
		"lightingProfile": str(binding.get("lightingPreset", "")),
		"facePose": str(binding.get("initialFacePose", "")),
		"actionIds": performance.get("actionIds", []),
		"propOk": prop_ok,
		"phone": phone,
		"productionReady": production_ready(),
	}


func _registry_is_authored(actions: Dictionary) -> bool:
	if str(actions.get("status", "")) != "AUTHORED":
		return false
	var registry_variant: Variant = actions.get("actionRegistry", {})
	if typeof(registry_variant) != TYPE_DICTIONARY:
		return false
	var registry: Dictionary = registry_variant
	if registry.size() != 34:
		return false
	for key in registry.keys():
		var spec_variant: Variant = registry[key]
		if typeof(spec_variant) != TYPE_DICTIONARY:
			return false
		var spec: Dictionary = spec_variant
		if str(spec.get("status", "")) != "AUTHORED":
			return false
	return true


func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


func _repo_file(file_name: String) -> String:
	var project: String = ProjectSettings.globalize_path("res://").trim_suffix("/").trim_suffix("\\")
	return project.get_base_dir().path_join("docs/examples").path_join(file_name)
