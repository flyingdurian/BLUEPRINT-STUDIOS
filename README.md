# Blueprint Studios — Director OS

**Milestone:** BS-M1 · Tri-Link Synchronization Foundation (source-code handoff)

A local-first React + TypeScript creative production workspace, built with Vite, Tailwind CSS v4 and Zustand. This is a front-end foundation, not a backend-backed, deployed multi-agent studio.

## Start on your computer

Install Node.js **22.12+** (or Node 20.19+), then from the extracted folder:

```bash
npm install
npm run dev
```

Open the address printed by Vite, normally `http://127.0.0.1:5173`.

To check code/tests after dependencies have installed:

```bash
npm run build
npm test
node tools/validate-seed.mjs
```

**Current handoff validation:** The TypeScript/TSX source was syntactically transpiled with the installed global TypeScript compiler, and the seed schema/timing was checked separately. **Full npm dependency installation, Vite build and interactive browser tests were not possible in the creation environment because it couldn't resolve `registry.npmjs.org`**. Do not treat this as a CI-passing build until those commands complete on your machine.

## What is implemented

- Native three-pane cinema-style workstation, responsive narrow-screen stacked layout
- Left screenplay: independently editable **Visual / Action** and **Narration / Dialogue** fields per shot
- Inline `@` asset completion in either screenplay field, inserting a tag and a real shot→asset relationship
- Stable internal shot identities plus immutable production labels (`SH_001`, ...), stored in integer frames
- Cross-pane selection: clicking screenplay shot, storyboard thumbnail, timeline shot, or an asset's linked shot navigates to the same shot
- Shared source of truth: **Zustand** store, no per-pane copy of shot selection or linkage
- Right panel: storyboard gallery with local original SVG concept thumbnails, 16:9 & 9:16 safe frame overlays, asset chips
- Asset Matrix Kanban with drag/drop workflow status, version bumping and orange outdated pinned-link warnings
- Bottom timeline: script cues, storyboard shots and **illustrative audio scratch placeholder** with frame ruler, playhead, zoom, previous/next
- Browser-local persistence via Zustand `persist` + `localStorage` (no SQLite yet)
- 14-shot complete narration for Pilot 1, **83 seconds at 30 FPS = 2,490 frames**; initial 10 production assets

## Project structure

```
blueprint-studios-bs-m1/
├── src/
│   ├── components/
│   │   ├── Screenplay.tsx       # shot blocks, selection and editable fields
│   │   ├── TagEditor.tsx        # @ typeahead / asset link
│   │   ├── VisualStage.tsx      # spatial gallery, safe frames and tabs
│   │   ├── StoryboardArt.tsx    # in-project SVG placeholder illustration
│   │   ├── AssetMatrix.tsx      # versioned asset Kanban
│   │   └── Timeline.tsx         # synchronized frame timeline
│   ├── data/pilot.ts           # authoritative 14-shot seed and relationships
│   ├── store/useStudioStore.ts # normalized Zustand state and actions
│   ├── types/studio.ts         # production/selection contracts
│   ├── utils/time.ts           # exact frame/time conversions
│   ├── tests/studio.test.ts    # store and seed tests (Vitest)
│   ├── App.tsx                 # editor shell and navigation
│   ├── styles.css              # Tailwind v4 import and workstation design tokens
│   └── main.tsx
├── tools/validate-seed.mjs
├── vite.config.ts
├── package.json
└── README.md
```

## Tri-Link contract

1. Only `selectedShotId` and `playheadFrame` live in the shared store. Screenplay scrolls (does not `.focus()`) to a newly selected shot; storyboard scrolls its gallery; timeline scrolls its viewport and updates its playhead.
2. `Shot` contains `id`, `code`, `startFrame`, `durationFrames`, `visual`, `narration`, `notes`, `mood`, `artKey`.
3. `ShotAssetLink` is normalized and stores `shotId`, `assetId`, `pinnedVersion`. An asset can have multiple linked shots, and every shot can link multiple assets.
4. `Asset.currentVersion` increments without changing pinned shot versions. Outdated links warn until the user deliberately adopts the new version.
5. The screenplay editor is not remounted during selection, preventing focus loss while typing.
6. Selection and text/link edits are saved to this browser's localStorage. This is **Milestone-1 prototype persistence**, not durable project file/database storage; clearing browser storage will erase local changes. Use the reset action to restore the seed.

## Explicitly *not yet implemented*

Real image/audio import, waveform generation, final video playback or export, drag/drop media ingest, undo/redo history, project JSON export, SQLite/FastAPI, live AI roles, publication/scheduling, comments, multi-project switching, and native Tauri/Electron wrapper. The sidebar's Agent and Calendar buttons are deliberately disabled rather than pretending those systems exist.

The timeline's violet waveform is a **static visual guide**, not calculated from an audio file. The storyboard images are original programmatically drawn **concept placeholders**, not fully rendered production frames. These will be replaced by actual media ingest and visualization in BS-M3.

## Recommended next test in a browser

1. Click `SH_009` in the screenplay and confirm the visual preview and timeline clip follow it.
2. Click `SH_004` in the storyboard gallery; confirm the screenplay scrolls to it without input focus being moved.
3. Type `@Phone` in the visual direction for `SH_004`; choose **Smartphone** and check a linked asset chip appears.
4. Open Asset Matrix; select **Smartphone**, press **Publish next version**, and return to the screenplay. Verify orange **UPDATE AVAILABLE** indicator on linked shots and test adoption.
5. Drag the **Ceramic Tea Mug** from **3D Modeling** to **Tested & Ready**, reload the page and verify status persists.
6. Add `SH_015`, verify its timeline placeholder; reset to original pilot when finished.

## Libraries and implementation references

Tailwind v4 via official Vite plugin: https://tailwindcss.com/docs/installation/using-vite
Zustand persist: https://zustand.docs.pmnd.rs/reference/middlewares/persist
Vite: https://vite.dev/
