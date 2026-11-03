extends RefCounted
## Shot-and-frame prop ownership. The same inputs always return the same anchor.
## Handoffs are recomputed from the cue window. They do not depend on playback order.

const TRANSITIONS: Dictionary = {
	"phone_grip_r_to_table": {"from": "phone_grip_r", "to": "table_phone_rest", "action": "put_down_phone"},
	"phone_grip_r_to_drawer": {"from": "phone_grip_r", "to": "drawer_phone_rest", "action": "put_phone_in_drawer"},
}
const ALIASES: Dictionary = {
	"mug_grip_r_or_two_handed_gag": "mug_grip_r",
}
const PLACEMENTS: PackedStringArray = [
	"phone_grip_r", "phone_grip_l", "mug_grip_r",
	"table_phone_rest", "drawer_phone_rest", "mug_rest",
	"cutaway_cloned_phones", "not_visible",
]


static func load_bindings(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {"ok": false, "error": "Action bindings were not found: " + path}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		return {"ok": false, "error": "Action bindings are not a JSON object"}
	return {"ok": true, "bindings": parsed}


static func shot_for_frame(bindings: Dictionary, global_frame: int) -> Dictionary:
	var shots: Variant = bindings.get("shots", [])
	if typeof(shots) != TYPE_ARRAY:
		return {"ok": false, "error": "Action bindings have no shots"}
	for entry in shots:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var shot: Dictionary = entry
		var start := int(shot.get("startFrame", -1))
		var duration := int(shot.get("durationFrames", 0))
		if global_frame >= start and global_frame < start + duration:
			return {"ok": true, "code": str(shot.get("code", "")), "local_frame": global_frame - start, "shot": shot}
	return {"ok": false, "error": "No shot covers frame %d" % global_frame}


static func resolve(bindings: Dictionary, shot_code: String, local_frame: int, prop: String) -> Dictionary:
	var shot := _shot_by_code(bindings, shot_code)
	if shot.is_empty():
		return {"ok": false, "error": "Shot %s is not in the action bindings" % shot_code}
	var anchors: Variant = shot.get("propAnchors", {})
	if typeof(anchors) != TYPE_DICTIONARY or not (anchors as Dictionary).has(prop):
		return {"ok": false, "error": "Shot %s has no %s anchor" % [shot_code, prop]}
	var anchor := str((anchors as Dictionary)[prop])
	if ALIASES.has(anchor):
		anchor = str(ALIASES[anchor])
	if TRANSITIONS.has(anchor):
		return _transition(shot, anchor, local_frame)
	if not PLACEMENTS.has(anchor):
		return {"ok": false, "error": "Unknown prop anchor %s" % anchor}
	return {
		"ok": true,
		"anchor": anchor,
		"visible": anchor != "not_visible",
		"blend": 0.0,
		"from_anchor": anchor,
		"to_anchor": anchor,
	}


static func _transition(shot: Dictionary, anchor: String, local_frame: int) -> Dictionary:
	var spec: Dictionary = TRANSITIONS[anchor]
	var cue := _cue(shot, str(spec["action"]))
	if cue.is_empty():
		return {"ok": false, "error": "Handoff %s is missing its action cue" % anchor}
	var start := int(cue.get("startLocalFrame", 0))
	var end := int(cue.get("endLocalFrameExclusive", start))
	var span := end - start
	var blend := 1.0
	if span > 0:
		blend = clampf(float(local_frame - start) / float(span), 0.0, 1.0)
	return {
		"ok": true,
		"anchor": anchor,
		"visible": true,
		"blend": blend,
		"from_anchor": str(spec["from"]),
		"to_anchor": str(spec["to"]),
	}


static func _shot_by_code(bindings: Dictionary, shot_code: String) -> Dictionary:
	var shots: Variant = bindings.get("shots", [])
	if typeof(shots) != TYPE_ARRAY:
		return {}
	for entry in shots:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var shot: Dictionary = entry
		if str(shot.get("code", "")) == shot_code:
			return shot
	return {}


static func _cue(shot: Dictionary, action_id: String) -> Dictionary:
	var cues: Variant = shot.get("actionCues", [])
	if typeof(cues) != TYPE_ARRAY:
		return {}
	for entry in cues:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var cue: Dictionary = entry
		if str(cue.get("actionId", "")) == action_id:
			return cue
	return {}
