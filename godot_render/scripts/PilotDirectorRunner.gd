extends Node2D
## 83-second Pilot 1 previs. Movie Maker must be launched with
## `--fixed-fps 30 --quit-after 2490`. This script does not call quit() on success.
## Stage action ids are logged and are not executed.

const RenderManifestReader = preload("res://scripts/RenderManifestReader.gd")
const TOTAL_FRAMES := 2490
const STAGE_WIDTH := 540
const STAGE_HEIGHT := 960

const SET_COLOR := {
	"apartment_nook": Color("#1b2836"),
	"phone_insert": Color("#102028"),
	"host_desk_cutaway": Color("#2c2433"),
}
const CAMERA_ANCHOR := {
	"medium_three_quarter": Vector2(250, 500),
	"wide_profile": Vector2(180, 560),
	"phone_extreme_closeup": Vector2(270, 430),
	"medium_front": Vector2(270, 480),
	"tight_mug_reaction": Vector2(320, 620),
	"over_shoulder_phone": Vector2(340, 540),
	"medium_phone_foreground": Vector2(300, 500),
	"symmetric_wide": Vector2(270, 580),
	"split_call": Vector2(160, 480),
	"cutaway_wide_reveal": Vector2(270, 420),
	"medium_deadpan": Vector2(270, 500),
	"over_shoulder_then_reaction": Vector2(360, 520),
	"drawer_closeup": Vector2(270, 680),
	"medium_to_wide": Vector2(270, 540),
}

var _shots: Array = []
var _pngs: Dictionary = {}
var _stand_in
var _sprite: Sprite2D
var _shot_label: Label
var _narration_label: Label
var _frame_label: Label
var _stage_color: Color = Color("#1b2836")
var _anchor: Vector2 = Vector2(270, 520)
var _active_code := ""
var _tick := 0


func _ready() -> void:
	var manifest_path := _manifest_argument()
	var loaded: Dictionary = RenderManifestReader.load_job(manifest_path)
	if not bool(loaded.get("ok", false)):
		_stop(str(loaded.get("error", "Manifest rejected")))
		return
	var manifest: Dictionary = loaded["manifest"]
	_shots = manifest["shots"]
	_pngs = loaded["textures"]
	_stand_in = loaded["stand_in"]
	_sprite = Sprite2D.new()
	_sprite.name = "TimingImage"
	add_child(_sprite)
	_shot_label = _label(Vector2(28, 36), 22, Color("#d0f2e9"))
	_narration_label = _label(Vector2(28, 760), 16, Color("#d5e7f7"))
	_narration_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_narration_label.size = Vector2(484, 110)
	_frame_label = _label(Vector2(28, 900), 16, Color("#8fa9b8"))
	_label(Vector2(28, 78), 14, Color("#8fa9b8")).text = "PREVIS  ·  ACTIONS HELD  ·  NOT CHARACTER ANIMATION"
	print("M4C_MANIFEST_OK revision=%d frames=2490 fps=30 sha256=%s" % [int(manifest.get("revision", 0)), _sidecar_digest(manifest_path)])
	print("M4C_RENDER_EXPECTED frames=2490 fps=30 duration=83.000s")
	if not OS.has_feature("movie"):
		print("M4C_WARNING Not in Movie Maker mode; run via --write-movie --fixed-fps 30 --quit-after 2490")
	set_process(true)


func _draw() -> void:
	draw_rect(Rect2(0, 0, STAGE_WIDTH, STAGE_HEIGHT), _stage_color, true)
	draw_rect(Rect2(24, 120, 492, 610), Color(1, 1, 1, 0.04), true)


func _process(_delta: float) -> void:
	if _tick >= TOTAL_FRAMES:
		return
	var shot := _shot_at(_tick)
	if shot.is_empty():
		_stop("No shot covers frame %d" % _tick)
		return
	var code := str(shot.get("code", ""))
	if code != _active_code:
		_active_code = code
		_cut_to(shot)
		var camera: Dictionary = shot.get("camera", {})
		var performance: Dictionary = shot.get("performance", {})
		var actions: PackedStringArray = PackedStringArray(performance.get("actionIds", []))
		print("M4C_SHOT_START code=%s frame=%d camera=%s" % [code, _tick, str(camera.get("preset", ""))])
		print("M4C_ACTION_HELD code=%s actions=%s" % [code, ",".join(actions)])
	_animate(shot, _tick)
	_frame_label.text = "FRAME %04d / 2490" % (_tick + 1)
	_tick += 1


func _cut_to(shot: Dictionary) -> void:
	var set_key := str(shot.get("setKey", ""))
	_stage_color = SET_COLOR.get(set_key, Color("#1b2836"))
	var camera: Dictionary = shot.get("camera", {})
	var preset := str(camera.get("preset", ""))
	if not CAMERA_ANCHOR.has(preset):
		print("M4C_CAMERA_UNMAPPED code=%s preset=%s" % [shot.get("code", ""), preset])
	_anchor = CAMERA_ANCHOR.get(preset, Vector2(270, 520))
	_sprite.texture = _texture_for(shot)
	if _sprite.texture == null:
		_stop("Shot %s has no verified image and no stand-in" % shot.get("code", ""))
		return
	_shot_label.text = "%s   %s" % [shot.get("code", ""), preset]
	_narration_label.text = str(shot.get("narration", ""))
	queue_redraw()


func _animate(shot: Dictionary, frame_index: int) -> void:
	var local: int = frame_index - int(shot.get("startFrame", 0))
	var duration: int = maxi(int(shot.get("durationFrames", 1)), 1)
	var phase := float(local) / float(duration)
	_sprite.position = _anchor + Vector2(36.0 * sin(phase * TAU), -28.0 * sin(phase * PI))
	_sprite.rotation = deg_to_rad(6.0 * sin(phase * TAU))
	_sprite.scale = Vector2.ONE * (0.72 + 0.08 * phase)


func _texture_for(shot: Dictionary) -> Texture2D:
	for asset_entry in shot.get("assets", []):
		var asset: Dictionary = asset_entry
		if bool(asset.get("verified", false)) and str(asset.get("mediaType", "")) == "image/png":
			var texture: Texture2D = _pngs.get(str(asset.get("sha256", "")), null)
			if texture != null:
				return texture
	return _stand_in


func _shot_at(frame_index: int) -> Dictionary:
	for entry in _shots:
		var shot: Dictionary = entry
		if frame_index >= int(shot.get("startFrame", 0)) and frame_index < int(shot.get("endFrameExclusive", 0)):
			return shot
	return {}


func _manifest_argument() -> String:
	var args := OS.get_cmdline_user_args()
	var index := args.find("--manifest")
	if index >= 0 and index + 1 < args.size():
		return str(args[index + 1])
	return ""


func _sidecar_digest(manifest_path: String) -> String:
	var sidecar := manifest_path.substr(0, manifest_path.length() - 5) + ".sha256" if manifest_path.ends_with(".json") else ""
	return FileAccess.get_file_as_string(sidecar).strip_edges()


func _label(at: Vector2, size_px: int, color: Color) -> Label:
	var node := Label.new()
	node.position = at
	node.add_theme_font_size_override("font_size", size_px)
	node.add_theme_color_override("font_color", color)
	add_child(node)
	return node


func _stop(reason: String) -> void:
	push_error("M4C_MANIFEST_FAIL: " + reason)
	get_tree().quit(2)
