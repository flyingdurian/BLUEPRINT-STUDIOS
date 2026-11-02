extends Node2D
## Five-second Movie Maker smoke test. End-of-recording is controlled by
## Godot CLI `--quit-after 150`, NOT by get_tree().quit() in _process().

const PinnedAssetResolver = preload("res://scripts/PinnedAssetResolver.gd")
const MANIFEST_PATH: String = "res://proof/pinned_asset.json"
const EXPECTED_FPS: int = 30
const EXPECTED_FRAMES: int = 150
const STAGE_WIDTH: int = 540
const STAGE_HEIGHT: int = 960

var _sprite: Sprite2D
var _counter_label: Label
var _tick: int = 0

func _ready() -> void:
    var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(MANIFEST_PATH))
    if typeof(data) != TYPE_DICTIONARY:
        _stop_with_error("Cannot parse pinned asset manifest")
        return
    var manifest: Dictionary = data
    if int(manifest.get("fps", 0)) != EXPECTED_FPS or int(manifest.get("durationFrames", 0)) != EXPECTED_FRAMES:
        _stop_with_error("Manifest must specify exactly 30 FPS and 150 frames")
        return
    var asset_data: Variant = manifest.get("asset", {})
    if typeof(asset_data) != TYPE_DICTIONARY:
        _stop_with_error("Manifest asset is not a dictionary")
        return
    var resolved: Dictionary = PinnedAssetResolver.load_verified_png(asset_data)
    if not bool(resolved.get("ok", false)):
        _stop_with_error(str(resolved.get("error", "Pinned asset verification failed")))
        return

    _sprite = Sprite2D.new()
    _sprite.name = "PinnedPhone"
    _sprite.texture = resolved["texture"]
    _sprite.position = Vector2(270.0, 510.0)
    add_child(_sprite)

    _label("BLUEPRINT STUDIOS  /  M4-B", Vector2(32, 40), 23, Color("#d0f2e9"))
    _label("PINNED VERSION PROOF", Vector2(32, 80), 17, Color("#8fa9b8"))
    _label("%s  •  v%d" % [resolved["assetId"], resolved["version"]], Vector2(32, 832), 23, Color("#d5e7f7"))
    _counter_label = _label("FRAME 000 / 150", Vector2(32, 880), 18, Color("#8fa9b8"))

    print("M4B_PIN_OK id=%s version=%s sha256=%s" % [resolved["assetId"], resolved["version"], resolved["sha256"]])
    print("M4B_RENDER_EXPECTED frames=150 fps=30 duration=5.000s")
    if not OS.has_feature("movie"):
        print("M4B_WARNING Not in Movie Maker mode; run via --write-movie --quit-after 150")
    set_process(true)

func _draw() -> void:
    draw_rect(Rect2(0, 0, STAGE_WIDTH, STAGE_HEIGHT), Color("#111925"), true)
    draw_rect(Rect2(25, 160, 490, 605), Color("#1d2b39"), true)
    draw_rect(Rect2(45, 185, 450, 565), Color("#26394b"), false, 3.0)
    draw_circle(Vector2(450, 276), 38.0, Color("#304b59"))

func _process(_delta: float) -> void:
    # Deterministic visual movement from integer frame indices, not wall time.
    # Godot Movie Maker drives the recording frame cadence via --fixed-fps 30.
    var frame_index: int = min(_tick, EXPECTED_FRAMES - 1)
    var phase: float = float(frame_index) / float(EXPECTED_FRAMES - 1)
    var ease: float = phase * phase * (3.0 - 2.0 * phase)
    _sprite.position = Vector2(270.0 + 58.0 * sin(phase * TAU), 510.0 - 65.0 * sin(ease * PI))
    _sprite.rotation = deg_to_rad(9.0 * sin(phase * TAU * 2.0))
    _sprite.scale = Vector2.ONE * (0.89 + 0.12 * ease)
    _counter_label.text = "FRAME %03d / 150" % (frame_index + 1)
    _tick += 1

func _label(text: String, at: Vector2, size_px: int, color: Color) -> Label:
    var node: Label = Label.new()
    node.text = text
    node.position = at
    node.add_theme_font_size_override("font_size", size_px)
    node.add_theme_color_override("font_color", color)
    add_child(node)
    return node

func _stop_with_error(reason: String) -> void:
    push_error("M4B_PIN_FAIL: " + reason)
    get_tree().quit(2)
