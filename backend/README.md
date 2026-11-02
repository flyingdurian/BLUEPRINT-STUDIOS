# BLUEPRINT STUDIOS · BS-M2 FastAPI / Persistent Asset Graph

This folder is an **additive backend** for the existing React/Vite/Zustand BS-M1 application. Do not replace `src/` or change the existing frontend persistence schema in this checkpoint.

## Prerequisites

- Python 3.11+ (tested locally with Python 3.13.5)
- The already passing BS-M1 checkout

## Install and run from repository root

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Open [Swagger docs](http://127.0.0.1:8000/docs) or request `http://127.0.0.1:8000/api/health`.

Run tests from repository root:

```bash
python -m pytest backend/tests -q -c backend/pyproject.toml
```

Or from `backend/`:

```bash
python -m pytest -q
```

BS-M2 uses `backend/data/blueprint.sqlite3` by default. The directory and database are created on first startup, and ignored by Git. Override the URL with `BLUEPRINT_DATABASE_URL=sqlite:////path/to/another/database.sqlite3` if needed.

**Security boundary:** this service has no user authentication because it is intended for one user's workstation. Keep Uvicorn bound to `127.0.0.1`; do not expose port 8000 to the public internet or other devices.

## Routes

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/projects` | Create project: `{ "name": "Organizer", "fps": 30 }` |
| GET | `/api/projects` | List projects |
| GET | `/api/projects/{project_id}/snapshot` | Complete normalized BS-M1-shaped state + revision |
| POST | `/api/projects/{project_id}/bootstrap` | First-time transactional import of a BS-M1 ProductionData graph |
| PUT | `/api/projects/{project_id}/shots/sync` | Atomic shot list sync with `expectedRevision` |
| PATCH | `/api/projects/{project_id}/shots/{shot_id}` | Edit one shot's text/timing, preserving stable code |
| GET | `/api/projects/{project_id}/assets` | List assets |
| POST | `/api/projects/{project_id}/assets` | Create persistent asset ID plus version 1 record |
| PATCH | `/api/projects/{project_id}/assets/{asset_id}` | Update asset metadata / Kanban status |
| GET | `/api/projects/{project_id}/assets/{asset_id}/versions` | Retrieve complete asset-version history |
| POST | `/api/projects/{project_id}/assets/{asset_id}/versions` | Append next immutable asset version and increment currentVersion |
| PUT | `/api/projects/{project_id}/shots/{shot_id}/assets/{asset_id}` | Add, pin or adopt a specific version |
| DELETE | `/api/projects/{project_id}/shots/{shot_id}/assets/{asset_id}` | Unlink asset from shot |
| GET | `/api/projects/{project_id}/storyboards` | List storyboard records |
| POST | `/api/projects/{project_id}/storyboards` | Create storyboard record linked to a shot (optional asset version) |
| PUT | `/api/projects/{project_id}/storyboards/{storyboard_id}` | Replace a storyboard record. Optional `expectedRevision` returns 409 when stale |
| DELETE | `/api/projects/{project_id}/storyboards/{storyboard_id}` | Remove a storyboard record. Optional `expectedRevision` query returns 409 when stale |
| POST | `/api/projects/{project_id}/sync-batch` | Apply an ordered list of shot, asset, link, and storyboard mutations in one transaction. `expectedRevision` is checked once; revision increments once |

API uses camelCase JSON keys matching `src/types/studio.ts`, e.g. `startFrame`, `durationFrames`, `artKey`, `currentVersion`, `pinnedVersion`. Database columns use conventional snake_case. `shots` and `assets` are dictionaries keyed by the immutable BS-M1 IDs; `shotOrder` is an ordered list of those IDs. All timing is integer frames, **not floating-point seconds**.

## Data integrity rules

- SQLite WAL mode enabled at startup, foreign keys enabled on **every connection**, busy timeout 5 seconds.
- All six tables created at startup for a new empty database.
- Shot IDs, asset IDs, and readable shot codes are immutable after creation. `SH_001` and similar codes remain stable across reordering.
- A pinned `ShotAssetLink` references a real `(assetId, version)` row. Publishing an asset version **does not repin existing shots**.
- `bootstrap` can only run once for an empty project. Imported BS-M1 asset counters become **explicit provenance-unknown placeholder version rows**, not falsified file history.
- Shot bulk sync has an `expectedRevision`: stale edits return `409 Conflict`, and nothing is committed. Non-overlapping shot intervals are validated.
- Metadata writes are transactional. Database restarts do not lose work.
- Storyboard media paths and asset version media paths are **metadata references only**. This milestone does **not** upload, copy, hash or serve the underlying media files. A supplied hash is caller-asserted, not file-verified; file ingestion comes in a later checkpoint.
- Project IDs are independent, but BS-M1's fixed demo shot/asset IDs are globally unique. To seed an additional project, generate new stable UUIDs for its shot/asset IDs and rewrite its links.

## Migration boundary with BS-M1

BS-M1 still saves its state to browser localStorage. This backend deliberately does not automatically overwrite it. A one-time, deliberate import is documented in `examples/bs_m1_browser_import.js`. Do this once after the backend starts; avoid creating a duplicate project every page refresh.

At the **next frontend integration checkpoint**, add an API adapter and hydration path. Then make the FastAPI snapshot authoritative, updating Zustand optimistically for responsiveness, with `revision`-aware writes and retry/conflict UI. Do not run two independent autosave mechanisms that overwrite one another.

## Migrations

`Base.metadata.create_all()` creates an initial schema; it **does not migrate existing schemas**. Do not change existing tables without an explicit migration plan. Alembic revision scripts should be added before the first deployed schema change in BS-M2.1.

## Current scope exclusions

No file upload pipeline; no authentication; no background scheduler; no social media platform connectivity; no automatic backend/frontend binding; no claim that user's GitHub CI runs backend tests until its workflow is updated explicitly.

## Verification performed during handoff preparation

- Python 3.13.5, FastAPI 0.128.2, SQLAlchemy 2.0.50, Pydantic 2.13.5 and pytest 9.0.2: **11 integration tests passing**.
- Compiled Python modules with `compileall`.
- Independently transpiled the actual existing `src/data/pilot.ts` seed and used the resulting graph in the API: **14 shots, 10 assets, 49 links, 2,490 total frames, nextShotNumber 15**, imported successfully and read back from SQLite.
- No remote GitHub commits, CI jobs or production deployment were performed as part of this handoff.
