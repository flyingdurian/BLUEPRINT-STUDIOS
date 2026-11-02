"""API contracts: camelCase keys match BS-M1's TypeScript ProductionData."""
from __future__ import annotations

from typing import Annotated, Literal, Union
from pathlib import PurePosixPath
from pydantic import BaseModel, ConfigDict, Field, field_validator


def camel(string: str) -> str:
    head, *tail = string.split("_")
    return head + "".join(part.capitalize() for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=camel, populate_by_name=True, extra="forbid")


AssetCategory = Literal["rig", "environment", "prop", "graphic", "audio"]
AssetStatus = Literal["Concept", "3D Modeling", "Rigging", "Tested & Ready"]
CropMode = Literal["9:16", "16:9", "both"]


class ProjectCreate(CamelModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    fps: int = Field(default=30, ge=1, le=120)


class ProjectOut(CamelModel):
    id: str
    name: str
    fps: int
    revision: int
    next_shot_number: int


class ShotPayload(CamelModel):
    id: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50)
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(ge=1)
    visual: str = ""
    narration: str = ""
    notes: str = ""
    art_key: str = ""
    mood: str = ""


class ShotPatch(CamelModel):
    expected_revision: int | None = Field(default=None, ge=0)
    start_frame: int | None = Field(default=None, ge=0)
    duration_frames: int | None = Field(default=None, ge=1)
    visual: str | None = None
    narration: str | None = None
    notes: str | None = None
    art_key: str | None = None
    mood: str | None = None


class ShotSync(CamelModel):
    expected_revision: int = Field(ge=0)
    shots: dict[str, ShotPayload]
    shot_order: list[str]
    next_shot_number: int = Field(ge=1)


class AssetPayload(CamelModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    category: AssetCategory
    status: AssetStatus
    current_version: int = Field(ge=1)
    color: str = Field(default="#888888", max_length=32)
    shorthand: str = Field(default="AST", max_length=30)


class AssetCreate(CamelModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    category: AssetCategory
    status: AssetStatus = "Concept"
    color: str = "#888888"
    shorthand: str = "AST"


class AssetPatch(CamelModel):
    expected_revision: int | None = Field(default=None, ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: AssetStatus | None = None
    color: str | None = None
    shorthand: str | None = None


def safe_relative_path(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (not normalized or normalized == "." or path.is_absolute()
            or ".." in path.parts or ":" in path.parts[0]):
        raise ValueError("media paths must be nonempty, safe relative paths")
    return normalized


class VersionCreate(CamelModel):
    expected_revision: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    relative_path: str | None = None
    description: str = ""

    @field_validator("sha256")
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value)):
            raise ValueError("sha256 must contain 64 hexadecimal digits")
        return value.lower() if value else None

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str | None) -> str | None:
        return safe_relative_path(value)


class VersionOut(CamelModel):
    asset_id: str
    version: int
    sha256: str | None
    relative_path: str | None
    description: str
    source: str


class VersionUploadOut(VersionOut):
    sha256: str
    relative_path: str
    byte_size: int = Field(ge=1)
    media_type: str
    revision: int = Field(ge=0)


class AssetLinkPayload(CamelModel):
    shot_id: str
    asset_id: str
    pinned_version: int = Field(ge=1)


class LinkUpsert(CamelModel):
    pinned_version: int | None = Field(default=None, ge=1)
    expected_revision: int | None = Field(default=None, ge=0)


class BootstrapData(CamelModel):
    shots: dict[str, ShotPayload]
    shot_order: list[str]
    assets: dict[str, AssetPayload]
    links: list[AssetLinkPayload]
    next_shot_number: int = Field(ge=1)


class SnapshotOut(CamelModel):
    project: ProjectOut
    revision: int
    shots: dict[str, ShotPayload]
    shot_order: list[str]
    assets: dict[str, AssetPayload]
    links: list[AssetLinkPayload]
    next_shot_number: int


class StoryboardCreate(CamelModel):
    id: str | None = None
    shot_id: str
    crop_mode: CropMode = "9:16"
    media_path: str | None = None
    asset_id: str | None = None
    asset_version: int | None = Field(default=None, ge=1)
    sort_index: int = Field(default=0, ge=0)
    notes: str = ""

    @field_validator("media_path")
    @classmethod
    def validate_media_path(cls, value: str | None) -> str | None:
        return safe_relative_path(value)


class StoryboardOut(CamelModel):
    id: str
    project_id: str
    shot_id: str
    crop_mode: CropMode
    media_path: str | None
    asset_id: str | None
    asset_version: int | None
    sort_index: int
    notes: str


class StoryboardWrite(CamelModel):
    shot_id: str
    crop_mode: CropMode = "9:16"
    media_path: str | None = None
    asset_id: str | None = None
    asset_version: int | None = Field(default=None, ge=1)
    sort_index: int = Field(default=0, ge=0)
    notes: str = ""

    @field_validator("media_path")
    @classmethod
    def validate_media_path(cls, value: str | None) -> str | None:
        return safe_relative_path(value)


class StoryboardUpdate(StoryboardWrite):
    expected_revision: int | None = Field(default=None, ge=0)


class BatchCreateAsset(CamelModel):
    op: Literal["create_asset"]
    asset: AssetCreate


class BatchUpdateAsset(CamelModel):
    op: Literal["update_asset"]
    asset_id: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: AssetStatus | None = None
    color: str | None = None
    shorthand: str | None = None


class BatchPublishVersion(CamelModel):
    op: Literal["publish_version"]
    asset_id: str = Field(min_length=1, max_length=100)
    sha256: str | None = None
    relative_path: str | None = None
    description: str = ""

    @field_validator("sha256")
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value)):
            raise ValueError("sha256 must contain 64 hexadecimal digits")
        return value.lower() if value else None

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str | None) -> str | None:
        return safe_relative_path(value)


class BatchSyncShots(CamelModel):
    op: Literal["sync_shots"]
    shots: dict[str, ShotPayload]
    shot_order: list[str]
    next_shot_number: int = Field(ge=1)


class BatchUpsertLink(CamelModel):
    op: Literal["upsert_link"]
    shot_id: str
    asset_id: str
    pinned_version: int | None = Field(default=None, ge=1)


class BatchDeleteLink(CamelModel):
    op: Literal["delete_link"]
    shot_id: str
    asset_id: str


class BatchCreateStoryboard(CamelModel):
    op: Literal["create_storyboard"]
    storyboard: StoryboardCreate


class BatchUpdateStoryboard(CamelModel):
    op: Literal["update_storyboard"]
    storyboard_id: str = Field(min_length=1, max_length=100)
    storyboard: StoryboardWrite


class BatchDeleteStoryboard(CamelModel):
    op: Literal["delete_storyboard"]
    storyboard_id: str = Field(min_length=1, max_length=100)


BatchMutation = Annotated[Union[
    BatchCreateAsset, BatchUpdateAsset, BatchPublishVersion, BatchSyncShots,
    BatchUpsertLink, BatchDeleteLink, BatchCreateStoryboard, BatchUpdateStoryboard,
    BatchDeleteStoryboard,
], Field(discriminator="op")]


class SyncBatch(CamelModel):
    expected_revision: int = Field(ge=0)
    mutations: list[BatchMutation] = Field(min_length=1)


class SyncBatchOut(CamelModel):
    snapshot: SnapshotOut
    storyboards: list[StoryboardOut]
