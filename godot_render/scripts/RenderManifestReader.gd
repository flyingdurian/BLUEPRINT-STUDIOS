extends RefCounted
## Validates a frozen M4-C job before any frame is drawn.
## Action ids are data. This reader never executes them.

const SCHEMA := "blueprint.render-manifest.v1"
const TOTAL_FRAMES := 2490
const CHUNK_BYTES := 1024 * 1024

static func load_job(manifest_path: String) -> Dictionary:
	if manifest_path.is_empty() or not FileAccess.file_exists(manifest_path):
		return {"ok": false, "error": "Render manifest path is missing"}
	var sidecar := manifest_path.substr(0, manifest_path.length() - 5) + ".sha256" if manifest_path.ends_with(".json") else manifest_path + ".sha256"
	var bytes := FileAccess.get_file_as_bytes(manifest_path)
	var actual := _sha256(bytes)
	var expected := FileAccess.get_file_as_string(sidecar).strip_edges()
	if actual.is_empty() or actual != expected:
		return {"ok": false, "error": "render_manifest.sha256 does not match the manifest bytes"}
	var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		return {"ok": false, "error": "Render manifest is not a JSON object"}
	var manifest: Dictionary = parsed
	if str(manifest.get("schemaVersion", "")) != SCHEMA:
		return {"ok": false, "error": "Unsupported render manifest schema"}
	if str(manifest.get("quality", "")) != "previs":
		return {"ok": false, "error": "Pilot runner only executes previs manifests"}
	if int(manifest.get("fps", 0)) != 30 or int(manifest.get("totalFrames", 0)) != TOTAL_FRAMES:
		return {"ok": false, "error": "Manifest must be 30 fps and 2490 frames"}
	if int(manifest.get("width", 0)) != 540 or int(manifest.get("height", 0)) != 960:
		return {"ok": false, "error": "Manifest viewport must stay 540x960"}
	var shots: Variant = manifest.get("shots", [])
	if typeof(shots) != TYPE_ARRAY or shots.size() != 14:
		return {"ok": false, "error": "Manifest must contain the 14 Pilot 1 shots"}
	var cursor := 0
	for entry in shots:
		if typeof(entry) != TYPE_DICTIONARY:
			return {"ok": false, "error": "Shot entry is not an object"}
		var shot: Dictionary = entry
		if int(shot.get("startFrame", -1)) != cursor or int(shot.get("endFrameExclusive", -1)) != cursor + int(shot.get("durationFrames", 0)):
			return {"ok": false, "error": "Manifest shots overlap or leave a gap"}
		if bool((shot.get("performance", {}) as Dictionary).get("execute", true)):
			return {"ok": false, "error": "Manifest requested execution of unmapped stage actions"}
		cursor = int(shot.get("endFrameExclusive", -1))
	if cursor != TOTAL_FRAMES:
		return {"ok": false, "error": "Manifest does not end at frame 2490"}
	var job_dir := manifest_path.get_base_dir()
	var textures := {}
	for entry in shots:
		var shot: Dictionary = entry
		for asset_entry in shot.get("assets", []):
			var checked: Dictionary = _check_dependency(job_dir, asset_entry, textures)
			if not bool(checked.get("ok", false)):
				return checked
	var stand_in: Variant = manifest.get("standIn", null)
	var stand_texture: ImageTexture = null
	if stand_in != null:
		if typeof(stand_in) != TYPE_DICTIONARY or not bool((stand_in as Dictionary).get("verified", false)):
			return {"ok": false, "error": "Stand-in must be a verified fixture"}
		var loaded: Dictionary = _load_verified_png(job_dir, stand_in)
		if not bool(loaded.get("ok", false)):
			return loaded
		stand_texture = loaded["texture"]
	return {"ok": true, "manifest": manifest, "job_dir": job_dir, "stand_in": stand_texture, "textures": textures}


static func _check_dependency(job_dir: String, asset_entry: Variant, textures: Dictionary) -> Dictionary:
	if typeof(asset_entry) != TYPE_DICTIONARY:
		return {"ok": false, "error": "Asset dependency is not an object"}
	var asset: Dictionary = asset_entry
	if bool(asset.get("verified", false)):
		var loaded: Dictionary = _hash_staged(job_dir, str(asset.get("relativePath", "")), str(asset.get("sha256", "")))
		if not bool(loaded.get("ok", false)):
			return loaded
		if str(asset.get("mediaType", "")) == "image/png":
			var image := Image.new()
			if image.load_png_from_buffer(FileAccess.get_file_as_bytes(loaded["path"])) != OK:
				return {"ok": false, "error": "Verified PNG dependency could not be decoded"}
			textures[str(asset.get("sha256", ""))] = ImageTexture.create_from_image(image)
		return {"ok": true}
	if asset.get("sha256", "") != null or str(asset.get("resolution", "")) != "UNRESOLVED_PROXY":
		return {"ok": false, "error": "Unresolved dependency claimed a file hash"}
	return {"ok": true}


static func _load_verified_png(job_dir: String, descriptor: Dictionary) -> Dictionary:
	var hashed: Dictionary = _hash_staged(job_dir, str(descriptor.get("relativePath", "")), str(descriptor.get("sha256", "")))
	if not bool(hashed.get("ok", false)):
		return hashed
	var image := Image.new()
	if image.load_png_from_buffer(FileAccess.get_file_as_bytes(hashed["path"])) != OK:
		return {"ok": false, "error": "Stand-in PNG could not be decoded"}
	return {"ok": true, "texture": ImageTexture.create_from_image(image)}


static func _hash_staged(job_dir: String, relative: String, expected: String) -> Dictionary:
	var clean := relative.replace("\\", "/")
	if clean.is_empty() or clean.begins_with("/") or clean.contains("..") or clean.contains(":"):
		return {"ok": false, "error": "Staged media path escapes the job directory"}
	if expected.length() != 64 or not expected.is_valid_hex_number():
		return {"ok": false, "error": "Staged media hash is invalid"}
	var path := job_dir.simplify_path().trim_suffix("/") + "/" + clean
	if not FileAccess.file_exists(path):
		return {"ok": false, "error": "Staged media file is missing"}
	var actual := _sha256(FileAccess.get_file_as_bytes(path))
	if actual != expected.to_lower():
		return {"ok": false, "error": "Staged media SHA-256 mismatch"}
	return {"ok": true, "path": path}


static func _sha256(bytes: PackedByteArray) -> String:
	var hasher := HashingContext.new()
	if hasher.start(HashingContext.HASH_SHA256) != OK:
		return ""
	var offset := 0
	while offset < bytes.size():
		var count: int = mini(CHUNK_BYTES, bytes.size() - offset)
		if hasher.update(bytes.slice(offset, offset + count)) != OK:
			return ""
		offset += count
	return hasher.finish().hex_encode()
