extends RefCounted
## Installs the 22 contract names on a triangle mesh with zero sculpt offsets.
## This lets the morph evaluator bind and seek. It is not an approved face.


static func install(face: MeshInstance3D, contract_path: String) -> bool:
	if face == null or not FileAccess.file_exists(contract_path):
		return false
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(contract_path))
	if typeof(parsed) != TYPE_DICTIONARY:
		return false
	var contract: Dictionary = parsed
	var channels_variant: Variant = contract.get("channels", [])
	if typeof(channels_variant) != TYPE_ARRAY:
		return false
	var channels: Array = channels_variant
	if channels.size() != 22:
		return false
	var vertices: PackedVector3Array = PackedVector3Array([
		Vector3(-0.08, 1.55, 0.08),
		Vector3(0.08, 1.55, 0.08),
		Vector3(0.0, 1.72, 0.1),
	])
	var normals: PackedVector3Array = PackedVector3Array([Vector3(0, 0, 1), Vector3(0, 0, 1), Vector3(0, 0, 1)])
	var indices: PackedInt32Array = PackedInt32Array([0, 1, 2])
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh: ArrayMesh = ArrayMesh.new()
	mesh.blend_shape_mode = Mesh.BLEND_SHAPE_MODE_NORMALIZED
	var shape_offsets: Array = []
	for entry_variant in channels:
		if typeof(entry_variant) != TYPE_DICTIONARY:
			return false
		var entry: Dictionary = entry_variant
		var channel_name: String = str(entry.get("name", ""))
		if channel_name.is_empty():
			return false
		mesh.add_blend_shape(channel_name)
		var shape_arrays: Array = []
		shape_arrays.resize(Mesh.ARRAY_MAX)
		shape_arrays[Mesh.ARRAY_VERTEX] = vertices
		shape_arrays[Mesh.ARRAY_NORMAL] = normals
		shape_offsets.append(shape_arrays)
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays, shape_offsets)
	if mesh.get_surface_count() != 1 or mesh.get_blend_shape_count() != 22:
		return false
	face.mesh = mesh
	face.set_meta("face_status", "NAMED_HARNESS_NOT_SCULPTED")
	return true
