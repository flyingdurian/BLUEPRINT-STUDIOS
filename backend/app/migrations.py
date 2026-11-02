"""Additive schema updates for databases that already exist.

`create_all` creates missing tables only. It does not add columns to
`asset_versions`, so an existing studio database needs this explicit step.
"""
from __future__ import annotations

from sqlalchemy import Engine, text

M3A_VERSION = "m3a-media-blobs"


def apply_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        applied = {row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))}
        if M3A_VERSION in applied:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(asset_versions)"))}
        if "blob_sha256" not in columns:
            connection.execute(text(
                "ALTER TABLE asset_versions ADD COLUMN blob_sha256 VARCHAR(64) REFERENCES media_blobs(sha256)"
            ))
        connection.execute(text("INSERT INTO schema_migrations (version) VALUES (:version)"), {"version": M3A_VERSION})
