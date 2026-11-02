# BS-M2.1 — Frontend to SQLite persistence bridge

**Scope:** additive React/TypeScript bridge to the actual BS-M2 FastAPI contract. Existing screenplay, storyboard and timeline remain interactive and client-side; server sync is asynchronous. No changes to backend schema or routing are needed.

## Changed files
- `src/services/apiClient.ts` — typed fetch client for projects, bootstrap, shots, assets, versions, links and storyboard GET/POST.
- `src/sync/graph.ts` — canonical shot/asset/link equality and immutable snapshot helpers.
- `src/sync/bridge.ts` — debounced, serialized API persistence, offline retries, revision safety, first-start import.
- `src/types/studio.ts` — sync status types; existing data contract unchanged.
- `src/store/useStudioStore.ts` — status actions without changing existing shot/asset mutations.
- `src/main.tsx` — initializes the bridge once outside React StrictMode (and cleans up on HMR).
- `src/App.tsx` — SQLite/offline/conflict indicator, retry, explicit server-copy action.
- `src/styles.css` — indicator styles.
- `src/vite-env.d.ts` — Vite environment type declaration.
- `src/tests/persistence.test.ts` — regression tests for hydration, offline, bootstrap, revision and no silent overwrites.

## Run

From the **repository root**, launch the existing backend:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In another terminal, launch the frontend:

```powershell
npm install
npm run dev
```

Expected API health URL: `http://127.0.0.1:8000/api/health`. Frontend Vite default: `http://127.0.0.1:5173`.

Optional frontend `.env.local` (only when changing endpoint):

```dotenv
VITE_STUDIO_API_BASE_URL=http://127.0.0.1:8000
```

BS-M2's CORS allowlist already permits the local Vite origins. Do not expose this unauthenticated single-user backend on a public network.

## First-launch behavior and conflict protection

- When FastAPI is unavailable, editing continues and Zustand's **existing BS-M1 localStorage key** remains intact: `blueprint-studios-bs-m1-v1`.
- If the project doesn't exist, the bridge creates `blueprint-pilot-01` and imports the current browser graph via the BS-M2 bootstrap endpoint; it does not overwrite existing server production data.
- If the project already exists and the current browser state is unchanged/default, SQLite wins and the selected shot remains selected where possible.
- If pre-existing local edits differ from nonempty SQLite with no trusted revision baseline, **sync is blocked** and both copies are retained. Use the explicit **Use server copy** action only after reviewing the change; it deliberately discards the browser draft.
- After a successful sync, the client stores a last-confirmed graph and SQLite revision in the separate localStorage key `blueprint-studios-bs-m2.1-checkpoint`.
- Offline changes after a confirmed checkpoint are compared to that baseline and replayed on reconnect **only if the server revision is unchanged**. Otherwise the UI reports a conflict, preserving the local draft.
- A change made during an API request remains in the browser state and is scheduled for the next sync attempt. UI-only shot selection does not generate writes.
- Shot, asset, link, and storyboard edits are sent together to `POST /api/projects/{id}/sync-batch`. The server checks `expectedRevision` once and commits the whole batch, or nothing.
- Offline edits are stored in the local mutation journal `blueprint-studios-bs-m2.2-journal` and replayed on reconnect only when the server revision still matches that queue. A newer server revision stays a conflict; the local draft is not overwritten.

## Storyboard API boundary

Storyboard records live on the studio store and sync through create, replace, and delete. `apiClient.syncStoryboards` adds missing ids, replaces changed records, and deletes records that are no longer in the draft. The bridge sends those same changes inside the atomic batch.

## Verify

```powershell
npm run build
npm test
python -m pytest backend/tests -q -c backend/pyproject.toml
```

Manual acceptance:
1. Start both apps, edit one narration field, wait until the header says **SQLITE SAVED**. Reload and confirm it is still saved.
2. Stop FastAPI. Make another edit: the interface must remain writable and report offline or pending. Restart FastAPI, select **Retry sync**, then reload and confirm both edits persist.
3. Restart the frontend while connected: it must hydrate from SQLite without stealing focus from the screenplay editor.
4. Open a second tab and change project data; on return, stale changes must show **SYNC NEEDS REVIEW**, not silently overwrite the newer revision.
5. Add a new shot, link an asset, publish a new asset version, adopt it in a shot, then verify the link and history using `/docs`.

**Important:** This release contains no automatic merging of divergent local and server graphs, no silent destructive replacement, and no direct physical media upload.

## Commit

```bash
git switch main
git pull --ff-only
git switch -c feature/bs-m2-1-persistence-bridge
# Apply this patch, then run tests
git add src/services src/sync src/types/studio.ts src/store/useStudioStore.ts src/main.tsx src/App.tsx src/styles.css src/vite-env.d.ts src/tests/persistence.test.ts docs/BS-M2.1-FRONTEND-BRIDGE.md
git commit -m "feat(bs-m2.1): bridge Zustand state to FastAPI with offline-safe sync"
git push -u origin feature/bs-m2-1-persistence-bridge
```
