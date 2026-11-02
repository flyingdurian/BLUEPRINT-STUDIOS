extends RefCounted
## BS-M4-B asset gate: verify the physical bytes before loading a PNG into Godot.
## Production M4 will stage M3 blobs into a render-job directory first.

const MAX_PROOF_FILE_BYTES: int = 8 * 1024 * 1024
const CHUNK_BYTES: int = 1024 * 1024

static func load_verified_png(asset: Dictionary) -> Dictionary:
    var id: String = str(asset.get("assetId", ""))
    var version: int = int(asset.get("pinnedVersion", 0))
    var expected_hash: String = str(asset.get("sha256", "")).to_lower()
    var path: String = str(asset.get("path", ""))

    if id.is_empty() or version < 1:
        return {"ok": false, "error": "Missing stable asset ID or pinned version"}
    if expected_hash.length() != 64 or not expected_hash.is_valid_hex_number():
        return {"ok": false, "error": "Missing or invalid SHA-256"}
    # This proof deliberately allows only known project-internal file locations.
    if not (path.begins_with("res://proof/") or path.begins_with("res://staged/")) or ".." in path or "\\" in path:
        return {"ok": false, "error": "Asset path escapes approved render staging roots"}
    if not path.ends_with(".png") or not FileAccess.file_exists(path):
        return {"ok": false, "error": "Pinned PNG asset is missing"}

    var handle: FileAccess = FileAccess.open(path, FileAccess.READ)
    if handle == null:
        return {"ok": false, "error": "Cannot open pinned asset"}
    var file_size: int = handle.get_length()
    if file_size <= 0 or file_size > MAX_PROOF_FILE_BYTES:
        return {"ok": false, "error": "Pinned PNG size outside proof limits"}

    var hasher: HashingContext = HashingContext.new()
    if hasher.start(HashingContext.HASH_SHA256) != OK:
        return {"ok": false, "error": "SHA-256 context failed to initialize"}
    while handle.get_position() < file_size:
        var remaining: int = file_size - handle.get_position()
        var chunk: PackedByteArray = handle.get_buffer(min(remaining, CHUNK_BYTES))
        if chunk.is_empty() or hasher.update(chunk) != OK:
            return {"ok": false, "error": "Could not read/hash pinned asset"}
    handle.close()

    var actual_hash: String = hasher.finish().hex_encode()
    if actual_hash != expected_hash:
        return {"ok": false, "error": "Pinned asset SHA-256 mismatch: %s != %s" % [actual_hash, expected_hash]}

    # PNG only for this smoke test. GLB/rig support belongs in M4 asset adapters.
    var image_bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
    var image: Image = Image.new()
    if image.load_png_from_buffer(image_bytes) != OK:
        return {"ok": false, "error": "Verified file was not a decodable PNG"}
    var texture: ImageTexture = ImageTexture.create_from_image(image)
    return {"ok": true, "assetId": id, "version": version, "sha256": actual_hash, "texture": texture}
