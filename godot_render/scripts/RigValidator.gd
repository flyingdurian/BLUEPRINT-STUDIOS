extends RefCounted
## Inspects a lead actor scene against the 40-bone M4-E contract.
## A passing structure check is not owner art approval.

const REQUIRED_BONES: PackedStringArray = [
	"Root", "Hips", "Spine_01", "Spine_02", "Chest", "Neck", "Head", "Jaw",
	"Clavicle_L", "Clavicle_R", "UpperArm_L", "UpperArm_R", "LowerArm_L", "LowerArm_R", "Hand_L", "Hand_R",
	"UpperLeg_L", "UpperLeg_R", "LowerLeg_L", "LowerLeg_R", "Foot_L", "Foot_R", "Toe_L", "Toe_R",
	"Thumb_01_L", "Thumb_02_L", "Index_01_L", "Index_02_L", "Middle_01_L", "Middle_02_L", "RingPinky_01_L",
	"Thumb_01_R", "Thumb_02_R", "Index_01_R", "Index_02_R", "Middle_01_R", "Middle_02_R", "RingPinky_01_R",
	"Eye_L", "Eye_R",
]
const SOCKET_BONES: Dictionary = {
	"phone_grip_r": "Hand_R",
	"phone_grip_l": "Hand_L",
	"mug_grip_r": "Hand_R",
}


static func validate_actor(root: Node) -> Dictionary:
	var errors: PackedStringArray = []
	var blockers: PackedStringArray = []
	var skeleton := _find_type(root, "Skeleton3D") as Skeleton3D
	if skeleton == null:
		errors.append("Skeleton3D is missing")
	else:
		_check_bones(skeleton, errors)
		_check_sockets(skeleton, errors)
	if _find_named(root, "CharacterRoot") == null:
		errors.append("CharacterRoot is missing")
	if _find_type(root, "AnimationPlayer") == null:
		errors.append("AnimationPlayer is missing")
	else:
		var player := _find_type(root, "AnimationPlayer") as AnimationPlayer
		if player.get_animation_list().is_empty():
			blockers.append("AnimationPlayer has no authored action clips. The 34 action IDs are not playable yet.")
	_check_mesh(root, "BodyMesh", errors)
	_check_mesh(root, "FaceMesh", errors)
	var face := _find_named(root, "FaceMesh") as MeshInstance3D
	if face != null and face.mesh != null and not _has_required_blend_shapes(face.mesh):
		blockers.append("FaceMesh does not yet have the 22 named blend shapes")
	var status := str(root.get_meta("rig_status", ""))
	var approved := status == "OWNER_APPROVED"
	if not approved:
		blockers.append("Owner-approved identity master is absent. This scene is a rig validation dummy.")
	return {
		"ok": errors.is_empty(),
		"production_approved": approved and errors.is_empty() and blockers.is_empty(),
		"bone_count": REQUIRED_BONES.size(),
		"errors": errors,
		"blockers": blockers,
		"rig_status": status,
	}


static func _has_required_blend_shapes(mesh: Mesh) -> bool:
	if not mesh.has_method("get_blend_shape_count"):
		return false
	return int(mesh.call("get_blend_shape_count")) >= 22


static func _check_bones(skeleton: Skeleton3D, errors: PackedStringArray) -> void:
	var present: Dictionary = {}
	for index in skeleton.get_bone_count():
		var bone_name := skeleton.get_bone_name(index)
		present[bone_name] = true
		var rest := skeleton.get_bone_rest(index)
		var basis := rest.basis
		var scale_x := basis.x.length()
		var scale_y := basis.y.length()
		var scale_z := basis.z.length()
		if scale_x <= 0.0 or scale_y <= 0.0 or scale_z <= 0.0 or basis.determinant() <= 0.0:
			errors.append("Bone %s has a negative or zero rest scale" % bone_name)
		elif absf(scale_x - scale_y) > 0.001 or absf(scale_y - scale_z) > 0.001:
			errors.append("Bone %s has a nonuniform rest scale" % bone_name)
	for bone_name in REQUIRED_BONES:
		if not present.has(bone_name):
			errors.append("Canonical bone missing: %s" % bone_name)


static func _check_sockets(skeleton: Skeleton3D, errors: PackedStringArray) -> void:
	for socket_name in SOCKET_BONES.keys():
		var expected_bone := str(SOCKET_BONES[socket_name])
		var socket := skeleton.get_node_or_null(socket_name) as BoneAttachment3D
		if socket == null:
			errors.append("BoneAttachment3D socket missing: %s" % socket_name)
			continue
		if socket.bone_name != expected_bone:
			errors.append("Socket %s must bind to %s, found %s" % [socket_name, expected_bone, socket.bone_name])
		_check_node_scale(socket, socket_name, errors)
	var grip_r := skeleton.get_node_or_null("Grip_R") as BoneAttachment3D
	var grip_l := skeleton.get_node_or_null("Grip_L") as BoneAttachment3D
	if grip_r == null or grip_r.bone_name != "Hand_R":
		errors.append("Grip_R must be a BoneAttachment3D on Hand_R")
	elif grip_r.get_node_or_null("PhoneSocket") == null or grip_r.get_node_or_null("MugSocket") == null:
		errors.append("Grip_R is missing PhoneSocket or MugSocket")
	if grip_l == null or grip_l.bone_name != "Hand_L":
		errors.append("Grip_L must be a BoneAttachment3D on Hand_L")
	elif grip_l.get_node_or_null("PhoneSocket") == null:
		errors.append("Grip_L is missing PhoneSocket")


static func _check_node_scale(node: Node3D, label: String, errors: PackedStringArray) -> void:
	var scale := node.scale
	if scale.x <= 0.0 or scale.y <= 0.0 or scale.z <= 0.0:
		errors.append("Socket %s has a negative or zero scale" % label)
	elif absf(scale.x - scale.y) > 0.001 or absf(scale.y - scale.z) > 0.001:
		errors.append("Socket %s has a nonuniform scale" % label)


static func _check_mesh(root: Node, mesh_name: String, errors: PackedStringArray) -> void:
	var mesh_node := _find_named(root, mesh_name) as MeshInstance3D
	if mesh_node == null or mesh_node.mesh == null:
		errors.append("%s is missing or has no mesh" % mesh_name)
	elif mesh_node.skeleton.is_empty():
		errors.append("%s is not bound to Skeleton3D" % mesh_name)


static func _find_named(root: Node, node_name: String) -> Node:
	if root.name == node_name:
		return root
	return root.find_child(node_name, true, false)


static func _find_type(root: Node, type_name: String) -> Node:
	if root.is_class(type_name):
		return root
	for child in root.find_children("*", type_name, true, false):
		return child
	return null
