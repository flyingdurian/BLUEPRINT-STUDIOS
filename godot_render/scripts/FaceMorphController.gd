extends Node
## M4E-C production morph evaluator.
## Reads the 22-channel v2 contract and samples presets from the shot's local frame.
## Sampling is a pure function of (shot, local frame). It does not use tweens or elapsed time.
## The named triangle harness is not sculpted art. Final mode refuses it.

@export var face_mesh_path: NodePath = ^"../CharacterRoot/Visual/FaceMesh"

var _face: MeshInstance3D
var _channels: Array[String] = []
var _indices: Dictionary = {}
var _presets: Dictionary = {}
var _shots: Array = []
var _ready_for_render: bool = false
var _extra_channel_warning: bool = false


func initialize_contract(path: String, final_mode: bool = false) -> bool:
	_ready_for_render = false
	_extra_channel_warning = false
	_channels.clear()
	_indices.clear()
	_presets.clear()
	_shots.clear()
	_face = get_node_or_null(face_mesh_path) as MeshInstance3D
	if _face == null or _face.mesh == null:
		push_error("M4E-C: missing FaceMesh or Mesh resource")
		return false
	if not FileAccess.file_exists(path):
		push_error("M4E-C: face contract missing: " + path)
		return false
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("M4E-C: contract is not a JSON object")
		return false
	var contract: Dictionary = parsed
	if str(contract.get("schemaVersion", "")) != "blueprint.face_morphs.v2":
		push_error("M4E-C: wrong face contract schema version")
		return false
	var channels_input: Array = contract.get("channels", [])
	if channels_input.size() != 22:
		push_error("M4E-C: expected precisely 22 named target channels")
		return false
	for entry_variant in channels_input:
		if typeof(entry_variant) != TYPE_DICTIONARY:
			return false
		var entry: Dictionary = entry_variant
		var channel_name: String = str(entry.get("name", ""))
		var shape_index: int = _face.find_blend_shape_by_name(StringName(channel_name))
		if channel_name.is_empty() or _indices.has(channel_name) or shape_index < 0:
			push_error("M4E-C: duplicate or missing mesh target: " + channel_name)
			return false
		_indices[channel_name] = shape_index
		_channels.append(channel_name)
	if _face.mesh.has_method("get_blend_shape_count"):
		var shape_count: int = int(_face.mesh.call("get_blend_shape_count"))
		if shape_count > _channels.size():
			_extra_channel_warning = true
			push_warning("M4E-C: extra blend shape channel requires review")
	var pose_variant: Variant = contract.get("presets", {})
	if typeof(pose_variant) != TYPE_DICTIONARY:
		return false
	var poses: Dictionary = pose_variant
	if poses.size() != 8:
		push_error("M4E-C: 8 named expression presets required")
		return false
	for pose_name_variant in poses.keys():
		var pose_name: String = str(pose_name_variant)
		var pose_data: Dictionary = poses[pose_name]
		var weights: Dictionary = pose_data.get("weights", {})
		if weights.size() != 22:
			push_error("M4E-C: incomplete weights for " + pose_name)
			return false
		for channel_index in _channels.size():
			var required_name: String = _channels[channel_index]
			if not weights.has(required_name):
				push_error("M4E-C: missing " + required_name + " for " + pose_name)
				return false
			var weight: float = float(weights[required_name])
			if is_nan(weight) or weight < 0.0 or weight > 1.0:
				push_error("M4E-C: invalid weight for " + pose_name)
				return false
		_presets[pose_name] = weights
	if not _load_shots(path.get_base_dir().path_join("BS-M4E-CD-SHOT-BINDINGS-v1.json")):
		return false
	if final_mode and str(_face.get_meta("face_status", "")) == "NAMED_HARNESS_NOT_SCULPTED":
		push_error("M4E-C: final mode refuses the named harness. Sculpted shapes are required.")
		return false
	_ready_for_render = true
	return true


func production_shapes_ready() -> bool:
	if not _ready_for_render or _face == null:
		return false
	return str(_face.get_meta("face_status", "")) != "NAMED_HARNESS_NOT_SCULPTED"


func has_shot(shot_id: String) -> bool:
	return not _shot(shot_id).is_empty()


func preset_weight(pose_name: String, channel_name: String) -> float:
	if not _presets.has(pose_name):
		return -1.0
	var weights: Dictionary = _presets[pose_name]
	return float(weights.get(channel_name, -1.0))


func evaluate(shot_id: String, local_frame: int) -> Dictionary:
	if not _ready_for_render:
		return _result(false, {}, false, 0.0, "", "")
	var shot: Dictionary = _shot(shot_id)
	if shot.is_empty():
		var cleared: Dictionary = _neutral_weights()
		return _result(false, cleared, _apply(cleared), 0.0, "neutral", "neutral")
	var cue: Dictionary = _cue_at(shot, local_frame)
	if cue.is_empty():
		var cleared_cue: Dictionary = _neutral_weights()
		return _result(false, cleared_cue, _apply(cleared_cue), 0.0, "neutral", "neutral")
	var from_pose: String = str(cue.get("from", ""))
	var to_pose: String = str(cue.get("to", ""))
	var start_frame: int = int(cue.get("startLocalFrame", -1))
	var end_frame: int = int(cue.get("endLocalFrameExclusive", -1))
	var sampled: Dictionary = _sample(from_pose, to_pose, local_frame, start_frame, end_frame)
	if not bool(sampled.get("ok", false)):
		var cleared_sample: Dictionary = _neutral_weights()
		return _result(false, cleared_sample, _apply(cleared_sample), 0.0, from_pose, to_pose)
	var weights: Dictionary = _overlay_blink(sampled["weights"], shot, local_frame)
	return _result(true, weights, _apply(weights), float(sampled["eased"]), from_pose, to_pose)


func evaluate_cue(from_pose: String, to_pose: String, local_frame: int, start_frame: int, end_exclusive: int) -> bool:
	if not _ready_for_render:
		return false
	var sampled: Dictionary = _sample(from_pose, to_pose, local_frame, start_frame, end_exclusive)
	if not bool(sampled.get("ok", false)):
		return false
	return _apply(sampled["weights"])


func apply_gaze(yaw_degrees: float, pitch_degrees: float) -> Dictionary:
	var yaw: float = clampf(yaw_degrees, -20.0, 20.0)
	var pitch: float = clampf(pitch_degrees, -12.0, 12.0)
	var skeleton: Skeleton3D = get_node_or_null("../CharacterRoot/Visual/Skeleton3D") as Skeleton3D
	if skeleton == null:
		return {"ok": false, "yaw": yaw, "pitch": pitch}
	var basis: Basis = Basis.from_euler(Vector3(deg_to_rad(pitch), deg_to_rad(yaw), 0.0))
	var rotation: Quaternion = basis.get_rotation_quaternion()
	var left: int = skeleton.find_bone("Eye_L")
	var right: int = skeleton.find_bone("Eye_R")
	if left < 0 or right < 0:
		return {"ok": false, "yaw": yaw, "pitch": pitch}
	skeleton.set_bone_pose_rotation(left, rotation)
	skeleton.set_bone_pose_rotation(right, rotation)
	return {"ok": true, "yaw": yaw, "pitch": pitch}


func _load_shots(path: String) -> bool:
	if not FileAccess.file_exists(path):
		push_error("M4E-C: shot binding file missing: " + path)
		return false
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		return false
	var contract: Dictionary = parsed
	if str(contract.get("schemaVersion", "")) != "blueprint.shot_face_light_binding.v1":
		push_error("M4E-C: wrong shot binding schema")
		return false
	var examples_variant: Variant = contract.get("examples", [])
	if typeof(examples_variant) != TYPE_ARRAY:
		return false
	_shots = examples_variant
	return true


func _shot(shot_id: String) -> Dictionary:
	for entry_variant in _shots:
		if typeof(entry_variant) != TYPE_DICTIONARY:
			continue
		var shot: Dictionary = entry_variant
		if str(shot.get("shotId", "")) == shot_id or str(shot.get("code", "")) == shot_id:
			return shot
	return {}


func _cue_at(shot: Dictionary, local_frame: int) -> Dictionary:
	var cues_variant: Variant = shot.get("faceCues", [])
	if typeof(cues_variant) != TYPE_ARRAY:
		return {}
	var cues: Array = cues_variant
	for entry_variant in cues:
		if typeof(entry_variant) != TYPE_DICTIONARY:
			continue
		var cue: Dictionary = entry_variant
		var start_frame: int = int(cue.get("startLocalFrame", -1))
		var end_frame: int = int(cue.get("endLocalFrameExclusive", -1))
		if local_frame >= start_frame and local_frame < end_frame:
			return cue
	return {}


func _sample(from_pose: String, to_pose: String, local_frame: int, start_frame: int, end_exclusive: int) -> Dictionary:
	if not _presets.has(from_pose) or not _presets.has(to_pose):
		return {"ok": false}
	if start_frame < 0 or end_exclusive <= start_frame:
		return {"ok": false}
	var u: float = clampf(float(local_frame - start_frame) / float(end_exclusive - start_frame), 0.0, 1.0)
	var eased: float = u * u * (3.0 - 2.0 * u)
	var before: Dictionary = _presets[from_pose]
	var after: Dictionary = _presets[to_pose]
	var weights: Dictionary = {}
	for channel_index in _channels.size():
		var channel_name: String = _channels[channel_index]
		var start_weight: float = float(before[channel_name])
		var end_weight: float = float(after[channel_name])
		weights[channel_name] = clampf(lerpf(start_weight, end_weight, eased), 0.0, 1.0)
	return {"ok": true, "weights": weights, "eased": eased}


func _overlay_blink(weights: Dictionary, shot: Dictionary, local_frame: int) -> Dictionary:
	var events_variant: Variant = shot.get("blinkEvents", [])
	if typeof(events_variant) != TYPE_ARRAY:
		return weights
	var events: Array = events_variant
	var blinking: bool = false
	for event_variant in events:
		if typeof(event_variant) != TYPE_DICTIONARY:
			continue
		var event: Dictionary = event_variant
		var start_frame: int = int(event.get("startLocalFrame", -1))
		var end_frame: int = int(event.get("endLocalFrameExclusive", start_frame + 4))
		if local_frame >= start_frame and local_frame < end_frame:
			blinking = true
	if not blinking:
		return weights
	var posed: Dictionary = weights.duplicate()
	posed["LidClose_L"] = 1.0
	posed["LidClose_R"] = 1.0
	return posed


func _neutral_weights() -> Dictionary:
	var weights: Dictionary = {}
	for channel_index in _channels.size():
		weights[_channels[channel_index]] = 0.0
	return weights


func _apply(weights: Dictionary) -> bool:
	if _face == null:
		return false
	for channel_index in _channels.size():
		var channel_name: String = _channels[channel_index]
		var shape_index: int = int(_indices[channel_name])
		if shape_index < 0 or not weights.has(channel_name):
			return false
		_face.set_blend_shape_value(shape_index, float(weights[channel_name]))
	return true


func _result(ok: bool, weights: Dictionary, applied: bool, eased: float, from_pose: String, to_pose: String) -> Dictionary:
	return {
		"ok": ok,
		"weights": weights,
		"applied": applied,
		"eased": eased,
		"from": from_pose,
		"to": to_pose,
		"channel_count": weights.size(),
	}
