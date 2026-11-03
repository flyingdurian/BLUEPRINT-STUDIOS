extends SceneTree
## Headless seek check for M4E-C weights and M4E-D light values.
## This does not render a contact sheet and does not approve the face or the look.

const LeadFaceHarness = preload("res://actors/lead/LeadFaceHarness.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var face_path: String = _repo_file("BS-M4E-C-FACE-PRESETS-v2.json")
	var actor_scene: PackedScene = load("res://actors/lead/ActorLead.tscn") as PackedScene
	if actor_scene == null:
		push_error("M4E_FAIL ActorLead.tscn did not load")
		quit(2)
		return
	var actor: Node3D = actor_scene.instantiate() as Node3D
	root.add_child(actor)
	var face: MeshInstance3D = actor.get_node_or_null("CharacterRoot/Visual/FaceMesh") as MeshInstance3D
	var controller: Node = actor.get_node_or_null("FaceMorphController") as Node
	if face == null or controller == null:
		push_error("M4E_FAIL face controller is not on the actor")
		quit(2)
		return
	var probe: Node = Node.new()
	probe.set_script(load("res://scripts/FaceMorphController.gd"))
	var bare: MeshInstance3D = MeshInstance3D.new()
	bare.name = "FaceMesh"
	bare.mesh = BoxMesh.new()
	probe.add_child(bare)
	root.add_child(probe)
	probe.set("face_mesh_path", NodePath("FaceMesh"))
	if bool(probe.call("initialize_contract", face_path, true)):
		push_error("M4E_FAIL final mode accepted a mesh with no blend shapes")
		quit(2)
		return
	if not LeadFaceHarness.install(face, face_path):
		push_error("M4E_FAIL named face harness did not install")
		quit(2)
		return
	if not bool(controller.call("initialize_contract", face_path, false)):
		push_error("M4E_FAIL face contract did not bind")
		quit(2)
		return
	if bool(controller.call("production_shapes_ready")):
		push_error("M4E_FAIL harness was treated as sculpted art")
		quit(2)
		return
	if bool(controller.call("has_shot", "SH_004")):
		push_error("M4E_FAIL SH_004 was treated as an authored cue")
		quit(2)
		return
	if not bool(controller.call("evaluate_cue", "polite", "confused", 0, 0, 18)):
		push_error("M4E_FAIL polite to confused sample failed")
		quit(2)
		return
	if not _shape_equals(face, "Smile_L", float(controller.call("preset_weight", "polite", "Smile_L"))):
		push_error("M4E_FAIL polite to confused did not start on polite")
		quit(2)
		return
	var first: Dictionary = _evaluate(controller, "SH_009", 0)
	var repeat_first: Dictionary = _evaluate(controller, "SH_009", 0)
	var mid: Dictionary = _evaluate(controller, "SH_009", 12)
	var held: Dictionary = _evaluate(controller, "SH_009", 24)
	var jumped: Dictionary = _evaluate(controller, "shot-014", 30)
	var returned: Dictionary = _evaluate(controller, "SH_009", 0)
	if not bool(first.get("ok", false)) or int(first.get("channel_count", 0)) != 22:
		push_error("M4E_FAIL SH_009 did not return 22 weights")
		quit(2)
		return
	if not _weights_close(first["weights"], repeat_first["weights"]) or not _weights_close(first["weights"], returned["weights"]):
		push_error("M4E_FAIL shuffled seek did not reproduce SH_009 frame 0")
		quit(2)
		return
	if not _weights_close(first["weights"], _preset_vector(controller, "polite")):
		push_error("M4E_FAIL SH_009 frame 0 is not polite")
		quit(2)
		return
	if not _weights_close(held["weights"], _preset_vector(controller, "frozen")):
		push_error("M4E_FAIL SH_009 frame 24 is not frozen")
		quit(2)
		return
	if absf(float(held["weights"]["LidClose_L"])) > 0.000001 or absf(float(held["weights"]["LidClose_R"])) > 0.000001:
		push_error("M4E_FAIL frozen hold applied an unscheduled blink")
		quit(2)
		return
	var expected_mid: float = lerpf(float(controller.call("preset_weight", "polite", "Smile_L")), float(controller.call("preset_weight", "frozen", "Smile_L")), 0.5)
	if absf(float(mid["weights"]["Smile_L"]) - expected_mid) > 0.000001:
		push_error("M4E_FAIL SH_009 midpoint missed smoothstep")
		quit(2)
		return
	var confused: Dictionary = _evaluate(controller, "SH_005", 0)
	var suspicious: Dictionary = _evaluate(controller, "SH_005", 18)
	var exhausted: Dictionary = _evaluate(controller, "SH_014", 0)
	if not _weights_close(confused["weights"], _preset_vector(controller, "confused")):
		push_error("M4E_FAIL SH_005 frame 0 is not confused")
		quit(2)
		return
	if not _weights_close(suspicious["weights"], _preset_vector(controller, "suspicious")):
		push_error("M4E_FAIL SH_005 frame 18 is not suspicious")
		quit(2)
		return
	if not _weights_close(exhausted["weights"], _preset_vector(controller, "exhausted")):
		push_error("M4E_FAIL SH_014 frame 0 is not exhausted")
		quit(2)
		return
	if not _weights_close(jumped["weights"], _preset_vector(controller, "deadpan")):
		push_error("M4E_FAIL SH_014 frame 30 is not deadpan")
		quit(2)
		return
	if absf(float(jumped["weights"]["LidClose_L"]) - 1.0) <= 0.000001:
		push_error("M4E_FAIL deadpan hold closed the lids")
		quit(2)
		return
	if not _mesh_matches(face, returned["weights"]):
		push_error("M4E_FAIL mesh blend values do not match the sampled vector")
		quit(2)
		return
	var skeleton: Skeleton3D = actor.get_node("CharacterRoot/Visual/Skeleton3D") as Skeleton3D
	var jaw_index: int = skeleton.find_bone("Jaw")
	var eye_index: int = skeleton.find_bone("Eye_L")
	var jaw_before: Quaternion = skeleton.get_bone_pose_rotation(jaw_index)
	var gaze: Dictionary = controller.call("apply_gaze", 40.0, -30.0)
	if absf(float(gaze.get("yaw", 99.0)) - 20.0) > 0.000001 or absf(float(gaze.get("pitch", 99.0)) + 12.0) > 0.000001:
		push_error("M4E_FAIL gaze clamp missed ±20 yaw or ±12 pitch")
		quit(2)
		return
	var eye_after_gaze: Quaternion = skeleton.get_bone_pose_rotation(eye_index)
	_evaluate(controller, "SH_009", 24)
	if not _same_quat(jaw_before, skeleton.get_bone_pose_rotation(jaw_index)):
		push_error("M4E_FAIL JawDrop also rotated the jaw bone")
		quit(2)
		return
	if not _same_quat(eye_after_gaze, skeleton.get_bone_pose_rotation(eye_index)):
		push_error("M4E_FAIL morph evaluate changed the eye gaze")
		quit(2)
		return
	if bool(controller.call("initialize_contract", face_path, true)):
		push_error("M4E_FAIL final mode accepted the named harness")
		quit(2)
		return
	var lighting_scene: PackedScene = load("res://scenes/sets/ApartmentLighting.tscn") as PackedScene
	if lighting_scene == null:
		push_error("M4E_FAIL ApartmentLighting.tscn did not load")
		quit(2)
		return
	var lighting: Node = lighting_scene.instantiate()
	root.add_child(lighting)
	var worlds: Array = lighting.find_children("*", "WorldEnvironment", true, false)
	if worlds.size() != 1:
		push_error("M4E_FAIL lighting scene must have one WorldEnvironment")
		quit(2)
		return
	var rig: Node = lighting.get_node("LightingRig")
	if not bool(rig.call("contract_ready")):
		push_error("M4E_FAIL lighting contract did not initialize")
		quit(2)
		return
	if bool(rig.call("final_render_allowed")) or bool(rig.call("lookdev_approved")) or bool(rig.call("renderer_is_forward_plus")):
		push_error("M4E_FAIL provisional lighting was marked final")
		quit(2)
		return
	var world: WorldEnvironment = lighting.get_node("WorldEnvironment") as WorldEnvironment
	var attributes: CameraAttributesPractical = world.camera_attributes as CameraAttributesPractical
	if world.environment == null or world.environment.tonemap_mode != Environment.TONE_MAPPER_FILMIC:
		push_error("M4E_FAIL tonemap is not Filmic")
		quit(2)
		return
	if not is_equal_approx(world.environment.tonemap_exposure, 1.0) or attributes == null or attributes.auto_exposure_enabled:
		push_error("M4E_FAIL exposure is not fixed at 1.0")
		quit(2)
		return
	if world.environment.ssil_enabled or world.environment.glow_enabled or world.environment.ssr_enabled or world.environment.fog_enabled:
		push_error("M4E_FAIL a disabled environment effect is on")
		quit(2)
		return
	if not world.environment.ssao_enabled:
		push_error("M4E_FAIL SSAO is off")
		quit(2)
		return
	var key: DirectionalLight3D = rig.get_node("WindowKey") as DirectionalLight3D
	var fill: OmniLight3D = rig.get_node("FaceFill") as OmniLight3D
	var rim: SpotLight3D = rig.get_node("RimAccent") as SpotLight3D
	if not bool(rig.call("apply_profile", "host_desk")):
		push_error("M4E_FAIL host_desk profile did not apply")
		quit(2)
		return
	if not is_equal_approx(key.light_energy, 1.2) or not is_equal_approx(fill.light_energy, 0.5) or not is_equal_approx(rim.light_energy, 0.18):
		push_error("M4E_FAIL host_desk energies do not match the contract")
		quit(2)
		return
	if not bool(rig.call("apply_profile", "phone_insert")):
		push_error("M4E_FAIL phone_insert profile did not apply")
		quit(2)
		return
	if not is_equal_approx(key.light_energy, 1.45) or not is_equal_approx(fill.light_energy, 0.42) or not is_equal_approx(rim.light_energy, 0.1):
		push_error("M4E_FAIL phone_insert did not inherit the apartment key")
		quit(2)
		return
	if not is_equal_approx(fill.position.x, 1.3) or not is_equal_approx(fill.position.y, 2.2) or not is_equal_approx(fill.position.z, 2.5):
		push_error("M4E_FAIL phone_insert replaced the fill position")
		quit(2)
		return
	if not key.shadow_enabled or fill.shadow_enabled or rim.shadow_enabled:
		push_error("M4E_FAIL shadow policy does not match the contract")
		quit(2)
		return
	if key.directional_shadow_mode != DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS:
		push_error("M4E_FAIL key shadow mode is not four splits")
		quit(2)
		return
	if not is_equal_approx(rim.spot_angle, 32.0):
		push_error("M4E_FAIL rim spot angle is not 32")
		quit(2)
		return
	if not bool(rig.call("apply_for_shot", "SH_009")) or not is_equal_approx(key.light_energy, 1.45):
		push_error("M4E_FAIL SH_009 did not return to apartment_day")
		quit(2)
		return
	print("M4E_FACE_OK channels=22 presets=8")
	print("M4E_FACE_SEEK_OK")
	print("M4E_FACE_SH004_CUE_ABSENT")
	print("M4E_FACE_ART_BLOCKED")
	print("M4E_LIGHT_OK profiles=apartment_day,phone_insert,host_desk")
	print("M4E_LIGHT_LOOKDEV_BLOCKED")
	print("M4E_LIGHT_FORWARD_PLUS_BLOCKED")
	quit(0)


func _evaluate(controller: Node, shot_id: String, local_frame: int) -> Dictionary:
	var report: Variant = controller.call("evaluate", shot_id, local_frame)
	if typeof(report) != TYPE_DICTIONARY:
		return {}
	return report


func _preset_vector(controller: Node, pose_name: String) -> Dictionary:
	var sample: Dictionary = _evaluate(controller, "SH_009", 0)
	var weights: Dictionary = {}
	var source: Dictionary = sample.get("weights", {})
	for channel_name in source.keys():
		weights[channel_name] = float(controller.call("preset_weight", pose_name, str(channel_name)))
	return weights


func _weights_close(left: Dictionary, right: Dictionary) -> bool:
	if left.size() != 22 or right.size() != 22:
		return false
	for channel_name in left.keys():
		if absf(float(left[channel_name]) - float(right.get(channel_name, -1.0))) > 0.000001:
			return false
	return true


func _shape_equals(face: MeshInstance3D, channel_name: String, expected: float) -> bool:
	var shape_index: int = face.find_blend_shape_by_name(StringName(channel_name))
	if shape_index < 0:
		return false
	return absf(face.get_blend_shape_value(shape_index) - expected) <= 0.000001


func _mesh_matches(face: MeshInstance3D, weights: Dictionary) -> bool:
	for channel_name in weights.keys():
		if not _shape_equals(face, str(channel_name), float(weights[channel_name])):
			return false
	return weights.size() == 22


func _same_quat(left: Quaternion, right: Quaternion) -> bool:
	return absf(left.x - right.x) <= 0.000001 and absf(left.y - right.y) <= 0.000001 and absf(left.z - right.z) <= 0.000001 and absf(left.w - right.w) <= 0.000001


func _repo_file(file_name: String) -> String:
	var project: String = ProjectSettings.globalize_path("res://").trim_suffix("/").trim_suffix("\\")
	return project.get_base_dir().path_join("docs/examples").path_join(file_name)
