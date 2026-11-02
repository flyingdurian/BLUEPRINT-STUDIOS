"""Normalized, project-scoped production graph (SQLAlchemy 2.0 ORM)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    fps: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_shot_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (CheckConstraint("fps >= 1 AND fps <= 120"),)


class Shot(Base):
    __tablename__ = "shots"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_frames: Mapped[int] = mapped_column(Integer, nullable=False)
    visual: Mapped[str] = mapped_column(Text, nullable=False, default="")
    narration: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    art_key: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    mood: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_shot_project_code"),
        CheckConstraint("start_frame >= 0"),
        CheckConstraint("duration_frames > 0"),
        Index("ix_shots_project_timing", "project_id", "start_frame"),
    )


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="#888888")
    shorthand: Mapped[str] = mapped_column(String(30), nullable=False, default="AST")
    __table_args__ = (
        CheckConstraint("current_version >= 1"),
        Index("ix_assets_project_category", "project_id", "category"),
    )


class AssetVersion(Base):
    __tablename__ = "asset_versions"
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str | None] = mapped_column(String(64))
    relative_path: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (CheckConstraint("version >= 1"),)


class ShotAssetLink(Base):
    __tablename__ = "shot_asset_links"
    shot_id: Mapped[str] = mapped_column(ForeignKey("shots.id", ondelete="CASCADE"), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    pinned_version: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_id", "pinned_version"],
            ["asset_versions.asset_id", "asset_versions.version"],
            name="fk_link_pinned_version",
        ),
    )


class Storyboard(Base):
    __tablename__ = "storyboards"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    shot_id: Mapped[str] = mapped_column(ForeignKey("shots.id", ondelete="CASCADE"), nullable=False)
    crop_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="9:16")
    media_path: Mapped[str | None] = mapped_column(Text)
    asset_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    __table_args__ = (
        ForeignKeyConstraint(["asset_id", "asset_version"], ["asset_versions.asset_id", "asset_versions.version"]),
        CheckConstraint("(asset_id IS NULL AND asset_version IS NULL) OR (asset_id IS NOT NULL AND asset_version IS NOT NULL)"),
        Index("ix_storyboards_shot", "shot_id", "sort_index"),
    )
