extends SceneTree
## Headless structure and seek check. This does not approve character art.

const RigValidator = preload("res://scripts/RigValidator.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var packed: PackedScene = load("res://actors/lead/ActorLead.tscn")
	if packed == null:
		push_error("M4E_FAIL ActorLead.tscn did not load")
		quit(2)
		return
	var actor: Node3D = packed.instantiate() as Node3D
	if actor == null:
		push_error("M4E_FAIL ActorLead root is missing")
		quit(2)
		return
	root.add_child(actor)
	if str(actor.get_meta("rig_status", "")) != "TEST_DUMMY_NOT_APPROVED_ART":
		actor.set_meta("rig_status", "TEST_DUMMY_NOT_APPROVED_ART")
	var report: Dictionary = RigValidator.validate_actor(actor)
	if not bool(report.get("ok", false)):
		push_error("M4E_FAIL rig structure: " + _messages(report, "errors"))
		quit(2)
		return
	if bool(report.get("production_approved", false)):
		push_error("M4E_FAIL dummy was marked production approved")
		quit(2)
		return
	var first: Dictionary = actor.call("evaluate", "SH_001", 10)
	var repeat_first: Dictionary = actor.call("evaluate", "SH_001", 10)
	var handoff_start: Dictionary = actor.call("evaluate", "SH_008", 0)
	var handoff_mid: Dictionary = actor.call("evaluate", "SH_008", 39)
	var handoff_end: Dictionary = actor.call("evaluate", "SH_008", 78)
	var jumped: Dictionary = actor.call("evaluate_global", 2489)
	var returned: Dictionary = actor.call("evaluate", "SH_001", 10)
	if not _same_point(first, repeat_first) or not _same_point(first, returned):
		push_error("M4E_FAIL seek did not reproduce the phone transform")
		quit(2)
		return
	if _same_point(handoff_start, handoff_end) or _same_point(handoff_start, handoff_mid) or _same_point(handoff_mid, handoff_end):
		push_error("M4E_FAIL phone handoff did not move between grip and table")
		quit(2)
		return
	if _anchor(first, "phone") != "phone_grip_r":
		push_error("M4E_FAIL SH_001 phone is not on phone_grip_r")
		quit(2)
		return
	if _anchor(jumped, "phone") != "drawer_phone_rest":
		push_error("M4E_FAIL SH_014 phone is not on drawer_phone_rest")
		quit(2)
		return
	var left_hand: Dictionary = actor.call("evaluate", "SH_006", 4)
	if _anchor(left_hand, "phone") != "phone_grip_l":
		push_error("M4E_FAIL SH_006 phone is not on phone_grip_l")
		quit(2)
		return
	if _same_point(first, left_hand):
		push_error("M4E_FAIL left and right grips occupy the same point")
		quit(2)
		return
	var hidden: Dictionary = actor.call("evaluate", "SH_010", 12)
	var mug_placement: Variant = hidden.get("mug", {})
	var mug_visible := true
	if typeof(mug_placement) == TYPE_DICTIONARY:
		mug_visible = bool((mug_placement as Dictionary).get("visible", true))
	if mug_visible:
		push_error("M4E_FAIL SH_010 mug should be hidden")
		quit(2)
		return
	print("M4E_RIG_OK bones=40 sockets=phone_grip_r,phone_grip_l,mug_grip_r")
	print("M4E_PROP_SEEK_OK")
	print("M4E_PRODUCTION_BLOCKED")
	quit(0)


func _messages(report: Dictionary, key: String) -> String:
	var values: Variant = report.get(key, [])
	if typeof(values) != TYPE_ARRAY and typeof(values) != TYPE_PACKED_STRING_ARRAY:
		return str(values)
	var lines: PackedStringArray = []
	for entry in values:
		lines.append(str(entry))
	return ", ".join(lines)


func _anchor(result: Dictionary, prop: String) -> String:
	var placement: Variant = result.get(prop, {})
	if typeof(placement) != TYPE_DICTIONARY:
		return ""
	return str((placement as Dictionary).get("anchor", ""))


func _same_point(left: Dictionary, right: Dictionary) -> bool:
	if not bool(left.get("ok", false)) or not bool(right.get("ok", false)):
		return false
	var a: Vector3 = left.get("phone_position", Vector3.INF)
	var b: Vector3 = right.get("phone_position", Vector3.INF)
	return a.is_equal_approx(b)
