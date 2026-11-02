# BS-M2 repository handoff / commit instructions

**Authoritative repo:** https://github.com/flyingdurian/BLUEPRINT-STUDIOS

**Baseline verified from GitHub:** `main` includes React/Vite/Zustand in `src/`, with production contracts in `src/types/studio.ts`, a stable localStorage store in `src/store/useStudioStore.ts`, and Pilot 1 in `src/data/pilot.ts`.

This handoff is **additive**:
- `backend/` NEW: FastAPI, SQLAlchemy models, APIs, tests, metadata, sample BS-M1 import helper
- `docs/BS-M2-COMMIT.md` NEW: instructions
- **No changes** to the frontend source, package.json or Vite configuration
- The nested `backend/.gitignore` excludes generated DB files without overwriting your root `.gitignore`

## Commit on your computer

1. In a clean repository checkout:

```bash
git checkout main
git pull --ff-only
git switch -c feature/bs-m2-persistent-asset-graph
```

2. Extract the ZIP and copy its **`backend/` directory and `docs/` directory** into the repository root. Do not nest another copy of `BLUEPRINT-STUDIOS/`.

3. Install and validate the backend per `backend/README.md`:

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q -c backend/pyproject.toml
python -m compileall -q backend/app
```

4. Optionally start the server:

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

5. Verify the existing frontend tests still pass (nothing in `src/` has been changed):

```bash
npm run build
npm test
```

6. Commit:

```bash
git status --short
git add backend docs/BS-M2-COMMIT.md
git commit -m "feat(bs-m2): add FastAPI SQLite asset graph and versioned shot APIs"
git push -u origin feature/bs-m2-persistent-asset-graph
```

7. Open a pull request to `main`, check GitHub Actions results, and merge only after tests/acceptance review.

## Acceptance check

- [ ] Backend starts bound to loopback `127.0.0.1`.
- [ ] `GET /api/health` returns `ok`.
- [ ] SQLite reports `journal_mode=wal` and `foreign_keys=ON` on service connections.
- [ ] At least eleven backend integration tests pass.
- [ ] `POST /api/projects` and `POST /api/projects/{id}/bootstrap` import the BS-M1 graph.
- [ ] `GET .../snapshot` roundtrips its shot IDs, order and pinned links.
- [ ] Asset version bump creates history without changing pinned versions.
- [ ] Stale shot sync returns HTTP 409 without partial writes.
- [ ] Existing BS-M1 `npm run build` / `npm test` still pass.

## CI note

The previously inspected `main` branch did not expose `.github/workflows/` to the GitHub connection. We did not change or create a workflow in this patch to avoid overwriting your CI/CD setup. Add a Python test job when ready; until then treat backend tests as local verification only.
