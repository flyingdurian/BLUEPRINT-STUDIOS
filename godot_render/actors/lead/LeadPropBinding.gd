extends Node3D
## Places the phone and mug from the shot frame. Scrubbing recomputes the pose.
## It does not accumulate delta and it does not reparent the prop.

const PropSocketResolver = preload("res://scripts/PropSocketResolver.gd")

var _bindings: Dictionary = {}


func evaluate(shot_code: String, local_frame: int) -> Dictionary:
	if not _ensure_bindings():
		return {"ok": false, "error": "Action bindings are unavailable"}
	_refresh_skeleton()
	var phone_placement: Dictionary = PropSocketResolver.resolve(_bindings, shot_code, local_frame, "phone")
	var mug_placement: Dictionary = PropSocketResolver.resolve(_bindings, shot_code, local_frame, "mug")
	if not bool(phone_placement.get("ok", false)) or not bool(mug_placement.get("ok", false)):
		return {"ok": false, "phone": phone_placement, "mug": mug_placement}
	_place($Phone as Node3D, phone_placement)
	_place($Mug as Node3D, mug_placement)
	return {"ok": true, "phone": phone_placement, "mug": mug_placement, "phone_position": ($Phone as Node3D).global_position, "mug_position": ($Mug as Node3D).global_position}


func evaluate_global(global_frame: int) -> Dictionary:
	if not _ensure_bindings():
		return {"ok": false, "error": "Action bindings are unavailable"}
	var located: Dictionary = PropSocketResolver.shot_for_frame(_bindings, global_frame)
	if not bool(located.get("ok", false)):
		return located
	return evaluate(str(located["code"]), int(located["local_frame"]))


func _ensure_bindings() -> bool:
	if not _bindings.is_empty():
		return true
	var loaded: Dictionary = PropSocketResolver.load_bindings(_bindings_path())
	if not bool(loaded.get("ok", false)):
		push_error(str(loaded.get("error", "Action bindings are unavailable")))
		return false
	_bindings = loaded["bindings"]
	return true


func _bindings_path() -> String:
	var project := ProjectSettings.globalize_path("res://").trim_suffix("/").trim_suffix("\\")
	return project.get_base_dir().path_join("docs/examples/BS-M4E-ACTION-BINDINGS.json")


func _refresh_skeleton() -> void:
	var skeleton := get_node("CharacterRoot/Visual/Skeleton3D") as Skeleton3D
	skeleton.reset_bone_poses()
	skeleton.force_update_all_bone_transforms()


func _place(prop: Node3D, placement: Dictionary) -> void:
	var show_prop := bool(placement.get("visible", false))
	prop.visible = show_prop
	if not show_prop:
		return
	var from_node := _anchor(str(placement.get("from_anchor", "")))
	var to_node := _anchor(str(placement.get("to_anchor", "")))
	if from_node == null or to_node == null:
		push_error("Prop anchor is missing from the actor scene")
		return
	var blend := float(placement.get("blend", 0.0))
	prop.global_transform = from_node.global_transform.interpolate_with(to_node.global_transform, blend)


func _anchor(anchor: String) -> Node3D:
	var skeleton := get_node("CharacterRoot/Visual/Skeleton3D") as Skeleton3D
	var gripped := skeleton.get_node_or_null(NodePath(anchor)) as Node3D
	if gripped != null:
		return gripped
	return get_node_or_null(NodePath("StageAnchors/" + anchor)) as Node3D
