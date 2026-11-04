extends Node3D
## Production master for the 2490-frame pilot.
## Refuses a previs manifest. Does not start Movie Maker by itself.

const ActorRigController = preload("res://scripts/ActorRigController.gd")
const TOTAL_FRAMES := 2490

var _rig: Node
var _lighting: Node
var _active_profile: String = ""


func _ready() -> void:
	var actor: Node = get_node_or_null("ApartmentSet/Actor_Lead")
	_lighting = get_node_or_null("ApartmentSet/LightingRig")
	_rig = ActorRigController.new()
	_rig.name = "ActorRigController"
	add_child(_rig)
	_rig.bind_actor(actor)
	if not bool(_rig.call("load_contracts")):
		push_error("M4E_PRODUCTION_REFUSED contracts did not load")
		return
	var manifest_path: String = _manifest_argument()
	if manifest_path.is_empty():
		print("M4E_PRODUCTION_IDLE frames=2490 shots=14")
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("M4E_PRODUCTION_REFUSED manifest is not JSON")
		get_tree().quit(2)
		return
	var decision: Dictionary = accept_manifest(parsed)
	if not bool(decision.get("ok", false)):
		push_error("M4E_PRODUCTION_REFUSED " + str(decision.get("error", "")))
		get_tree().quit(2)


func production_ready() -> bool:
	return _rig != null and bool(_rig.call("production_ready"))


func accept_manifest(manifest: Dictionary) -> Dictionary:
	if str(manifest.get("quality", "")) != "production":
		return {"ok": false, "error": "Production director refuses a previs manifest and will not fall back"}
	if not bool(manifest.get("productionLocked", false)):
		return {"ok": false, "error": "Production director refuses an unlocked manifest"}
	if int(manifest.get("totalFrames", 0)) != TOTAL_FRAMES or int(manifest.get("fps", 0)) != 30:
		return {"ok": false, "error": "Production manifest must stay 2490 frames at 30 fps"}
	if not production_ready():
		return {"ok": false, "error": "Production director refuses unresolved rig, morph, action, or lighting dependencies"}
	return {"ok": true}


func schedule_frame(frame: int) -> Dictionary:
	var sample_variant: Variant = _rig.call("evaluate_frame", frame)
	if typeof(sample_variant) != TYPE_DICTIONARY:
		return {"ok": false, "frame": frame}
	var sample: Dictionary = sample_variant
	if bool(sample.get("ok", false)) and _lighting != null:
		var profile: String = str(sample.get("lightingProfile", ""))
		if profile != _active_profile:
			_lighting.call("apply_profile", profile)
			_active_profile = profile
	return sample


func dry_run() -> Dictionary:
	var cuts: PackedStringArray = PackedStringArray()
	var previous: String = ""
	for frame in TOTAL_FRAMES:
		var sample: Dictionary = schedule_frame(frame)
		if not bool(sample.get("ok", false)):
			return {"ok": false, "frame": frame}
		var code: String = str(sample.get("code", ""))
		if code != previous:
			cuts.append(code)
			previous = code
	var finished: bool = cuts.size() == 14 and cuts[0] == "SH_001" and cuts[13] == "SH_014"
	return {"ok": finished, "cuts": cuts.size(), "frames": TOTAL_FRAMES}


func _manifest_argument() -> String:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var index: int = args.find("--manifest")
	if index >= 0 and index + 1 < args.size():
		return str(args[index + 1])
	return ""
