extends Node
## M4E-C example integration module. NOT an approved production animation.
## Attach to Actor_Lead. Configure face_mesh_path for imported rig wrapper.
## Invoke initialize_contract(absolute_or_res_path) once, then evaluate_cue()
## explicitly at every Movie Maker frame. No tweens or delta accumulation.

@export var face_mesh_path: NodePath = ^"Visual/FaceMesh"

var _face: MeshInstance3D
var _channels: Array[String] = []
var _indices: Dictionary = {}
var _presets: Dictionary = {}
var _ready_for_render: bool = false

func initialize_contract(path: String) -> bool:
    _ready_for_render = false
    _channels.clear()
    _indices.clear()
    _presets.clear()
    _face = get_node_or_null(face_mesh_path) as MeshInstance3D
    if _face == null or _face.mesh == null:
        push_error("M4E-C: missing FaceMesh or Mesh resource")
        return false
    if not FileAccess.file_exists(path):
        push_error("M4E-C: face contract missing: " + path)
        return false
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
    if typeof(parsed) != TYPE_DICTIONARY:
        push_error("M4E-C: contract is not JSON object")
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
        var name: String = str(entry.get("name", ""))
        var idx: int = _face.find_blend_shape_by_name(StringName(name))
        if name.is_empty() or _indices.has(name) or idx < 0:
            push_error("M4E-C: duplicate or missing mesh target: " + name)
            return false
        _indices[name] = idx
        _channels.append(name)
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
        for channel_name in _channels:
            if not weights.has(channel_name):
                push_error("M4E-C: missing " + channel_name + " for " + pose_name)
                return false
            var w: float = float(weights[channel_name])
            if is_nan(w) or w < 0.0 or w > 1.0:
                push_error("M4E-C: invalid weight for " + pose_name)
                return false
        _presets[pose_name] = weights
    _ready_for_render = true
    return true


func evaluate_cue(from_pose: String, to_pose: String, local_frame: int, start_frame: int, end_exclusive: int) -> bool:
    if not _ready_for_render or not _presets.has(from_pose) or not _presets.has(to_pose):
        return false
    if start_frame < 0 or end_exclusive <= start_frame:
        return false
    # Pure sampling: any frame can be evaluated independently, including out of order.
    var u: float = clampf(float(local_frame - start_frame) / float(end_exclusive - start_frame), 0.0, 1.0)
    var eased: float = u * u * (3.0 - 2.0 * u)
    var before: Dictionary = _presets[from_pose]
    var after: Dictionary = _presets[to_pose]
    for channel_name in _channels:
        var a: float = float(before[channel_name])
        var b: float = float(after[channel_name])
        _face.set_blend_shape_value(int(_indices[channel_name]), clampf(lerpf(a, b, eased), 0.0, 1.0))
    return true
