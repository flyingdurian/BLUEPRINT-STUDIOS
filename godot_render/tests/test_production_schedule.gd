extends SceneTree
## Schedules all 2490 frames without writing a movie.


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var packed: PackedScene = load("res://scenes/ProductionMaster.tscn") as PackedScene
	if packed == null:
		push_error("M4E_FAIL ProductionMaster.tscn did not load")
		quit(2)
		return
	var director: Node = packed.instantiate()
	root.add_child(director)
	if bool(director.call("production_ready")):
		push_error("M4E_FAIL unresolved production was marked ready")
		quit(2)
		return
	var previs: Dictionary = director.call("accept_manifest", {"quality": "previs", "productionLocked": false, "fps": 30, "totalFrames": 2490})
	if bool(previs.get("ok", false)):
		push_error("M4E_FAIL previs manifest was accepted")
		quit(2)
		return
	var locked: Dictionary = director.call("accept_manifest", {"quality": "production", "productionLocked": true, "fps": 30, "totalFrames": 2490})
	if bool(locked.get("ok", false)):
		push_error("M4E_FAIL locked manifest bypassed the rig gate")
		quit(2)
		return
	var checks: Array = [
		[0, "SH_001", 0, "medium_three_quarter", "apartment_day", "relieved"],
		[119, "SH_001", 119, "medium_three_quarter", "apartment_day", "relieved"],
		[120, "SH_002", 0, "wide_profile", "apartment_day", "relieved"],
		[1379, "SH_008", 209, "symmetric_wide", "apartment_day", "confident"],
		[1380, "SH_009", 0, "split_call", "apartment_day", "polite"],
		[2489, "SH_014", 179, "medium_to_wide", "apartment_day", "deadpan"],
	]
	for entry in checks:
		var row: Array = entry
		var sample: Dictionary = _sample(director, int(row[0]))
		var repeat: Dictionary = _sample(director, int(row[0]))
		if not _same_sample(sample, repeat):
			push_error("M4E_FAIL seek changed frame %d" % int(row[0]))
			quit(2)
			return
		if str(sample.get("code", "")) != str(row[1]) or int(sample.get("localFrame", -1)) != int(row[2]):
			push_error("M4E_FAIL frame %d mapped to %s local %d" % [int(row[0]), sample.get("code", ""), int(sample.get("localFrame", -1))])
			quit(2)
			return
		if str(sample.get("cameraPreset", "")) != str(row[3]) or str(sample.get("lightingProfile", "")) != str(row[4]):
			push_error("M4E_FAIL frame %d camera or lighting drifted" % int(row[0]))
			quit(2)
			return
		if str(sample.get("facePose", "")) != str(row[5]) or bool(sample.get("productionReady", true)):
			push_error("M4E_FAIL frame %d face pose or production flag drifted" % int(row[0]))
			quit(2)
			return
		if not bool(sample.get("propOk", false)):
			push_error("M4E_FAIL frame %d did not place props" % int(row[0]))
			quit(2)
			return
	var outside: Dictionary = _sample(director, 2490)
	if bool(outside.get("ok", true)):
		push_error("M4E_FAIL frame 2490 was inside the timeline")
		quit(2)
		return
	var host: Dictionary = _sample(director, 1560)
	if str(host.get("code", "")) != "SH_010" or str(host.get("lightingProfile", "")) != "host_desk":
		push_error("M4E_FAIL SH_010 did not select the host desk profile")
		quit(2)
		return
	var walked: Dictionary = director.call("dry_run")
	if not bool(walked.get("ok", false)) or int(walked.get("frames", 0)) != 2490 or int(walked.get("cuts", 0)) != 14:
		push_error("M4E_FAIL dry run did not cover 14 shots and 2490 frames")
		quit(2)
		return
	print("M4E_SCHEDULE_OK frames=2490 shots=14")
	print("M4E_PRODUCTION_REFUSED")
	quit(0)


func _sample(director: Node, frame: int) -> Dictionary:
	var report: Variant = director.call("schedule_frame", frame)
	if typeof(report) != TYPE_DICTIONARY:
		return {}
	return report


func _same_sample(left: Dictionary, right: Dictionary) -> bool:
	if str(left.get("code", "")) != str(right.get("code", "")) or int(left.get("localFrame", -1)) != int(right.get("localFrame", -2)):
		return false
	var first: Vector3 = left.get("phone", Vector3.INF)
	var second: Vector3 = right.get("phone", Vector3.INF)
	return first.is_equal_approx(second)
