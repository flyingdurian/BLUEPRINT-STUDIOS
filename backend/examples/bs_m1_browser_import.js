/*
 * ONE-TIME migration helper for BS-M1 -> BS-M2.
 * Paste into the browser DevTools console while the BS-M1 Vite app is running
 * at http://127.0.0.1:5173 (or http://localhost:5173).
 * The Python backend must already be listening at http://127.0.0.1:8000.
 *
 * This READS browser localStorage, creates a new backend project and imports
 * exactly the normalized ProductionData keys. It does NOT mutate localStorage.
 * Save the returned project ID for future frontend integration.
 */
(async () => {
  const key = 'blueprint-studios-bs-m1-v1';
  const item = localStorage.getItem(key);
  if (!item) throw new Error(`Cannot find saved Zustand state: ${key}`);
  const state = JSON.parse(item).state;
  const keys = ['shots', 'shotOrder', 'assets', 'links', 'nextShotNumber'];
  const productionData = Object.fromEntries(keys.map(k => [k, state[k]]));
  if (!productionData.shots || !productionData.assets) {
    throw new Error('The selected localStorage entry is not a BS-M1 ProductionData graph');
  }
  const base = 'http://127.0.0.1:8000/api/projects';
  const created = await fetch(base, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: "Congratulations, You're the Organizer", fps: 30 }),
  });
  if (!created.ok) throw new Error(`Project creation failed: ${await created.text()}`);
  const project = await created.json();
  const imported = await fetch(`${base}/${project.id}/bootstrap`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(productionData),
  });
  if (!imported.ok) {
    console.error('Project created but bootstrap failed; inspect and reuse project ID:', project.id);
    throw new Error(`Bootstrap failed: ${await imported.text()}`);
  }
  const snapshot = await imported.json();
  console.log('BS-M2 import complete. SAVE PROJECT ID:', project.id, {
    revision: snapshot.revision,
    shots: Object.keys(snapshot.shots).length,
    assets: Object.keys(snapshot.assets).length,
    links: snapshot.links.length,
    frames: Math.max(0, ...Object.values(snapshot.shots).map(s => s.startFrame + s.durationFrames)),
  });
})();
