import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPilot } from '../data/pilot'
import { fingerprint, productionGraph } from '../sync/graph'
import { JOURNAL_KEY } from '../sync/journal'
import { buildMutations, type GraphMutation } from '../sync/mutations'
import { ApiClient, ApiError, type ProjectSnapshot, type StoryboardRecord } from '../services/apiClient'
import { useStudioStore } from '../store/useStudioStore'
import { PersistenceBridge } from '../sync/bridge'

const data = new Map<string, string>()
Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
  getItem: (key: string) => data.get(key) ?? null,
  setItem: (key: string, value: string) => { data.set(key, value) },
  removeItem: (key: string) => { data.delete(key) },
  clear: () => data.clear(),
}})

function snapshot(revision = 1): ProjectSnapshot {
  return {
    ...createPilot(),
    project: { id: 'blueprint-pilot-01', name: 'Test pilot', fps: 30, revision, nextShotNumber: 15 },
    revision,
  }
}

beforeEach(() => {
  data.clear()
  useStudioStore.getState().resetPilot()
})

describe('normalized production graph', () => {
  it('compares logically equal shot payloads regardless of key ordering', () => {
    const original = createPilot()
    const same = productionGraph(original)
    const shot = original.shots['shot-001']
    same.shots['shot-001'] = {
      mood: shot.mood, artKey: shot.artKey, notes: shot.notes,
      narration: shot.narration, visual: shot.visual,
      durationFrames: shot.durationFrames, startFrame: shot.startFrame,
      code: shot.code, id: shot.id,
    }
    same.links.reverse()
    expect(fingerprint(original)).toBe(fingerprint(same))
  })
})

describe('BS-M2.1 persistence bridge', () => {
  it('hydrates an existing SQLite project without changing selected editor focus', async () => {
    const remote = snapshot(3)
    remote.shots['shot-001'] = { ...remote.shots['shot-001'], narration: 'Saved in SQLite' }
    useStudioStore.getState().selectShot('shot-009')
    const api = { getProjectSnapshot: vi.fn(async () => remote), listStoryboards: vi.fn(async () => []) } as unknown as ApiClient
    const bridge = new PersistenceBridge(api)
    await bridge.connect()
    expect(useStudioStore.getState().shots['shot-001'].narration).toBe('Saved in SQLite')
    expect(useStudioStore.getState().selectedShotId).toBe('shot-009')
    expect(useStudioStore.getState().syncStatus).toBe('synced')
  })

  it('creates and bootstraps a previously absent project', async () => {
    const bootstrap = snapshot()
    const api = {
      getProjectSnapshot: vi.fn(async () => { throw new ApiError(404, 'Not found', 'missing project') }),
      createProject: vi.fn(async () => bootstrap.project),
      bootstrapProject: vi.fn(async () => bootstrap),
      listStoryboards: vi.fn(async () => []),
    } as unknown as ApiClient
    await new PersistenceBridge(api).connect()
    expect(api.createProject).toHaveBeenCalledOnce()
    expect(api.bootstrapProject).toHaveBeenCalledWith(expect.objectContaining({ shotOrder: expect.arrayContaining(['shot-001']) }), 'blueprint-pilot-01')
    expect(useStudioStore.getState().syncStatus).toBe('synced')
  })

  it('preserves a local draft when the backend cannot be reached', async () => {
    useStudioStore.getState().updateShot('shot-001', 'narration', 'My offline version')
    const api = { getProjectSnapshot: vi.fn(async () => { throw new TypeError('Failed to fetch') }) } as unknown as ApiClient
    await new PersistenceBridge(api).connect()
    expect(useStudioStore.getState().shots['shot-001'].narration).toBe('My offline version')
    expect(useStudioStore.getState().syncStatus).toBe('offline')
  })

  it('does not overwrite conflicting legacy browser edits', async () => {
    useStudioStore.getState().updateShot('shot-001', 'narration', 'Local legacy work')
    const remote = snapshot(10)
    remote.shots['shot-001'] = { ...remote.shots['shot-001'], narration: 'Different server work' }
    const api = { getProjectSnapshot: vi.fn(async () => remote), listStoryboards: vi.fn(async () => []) } as unknown as ApiClient
    await new PersistenceBridge(api).connect()
    expect(useStudioStore.getState().syncStatus).toBe('conflict')
    expect(useStudioStore.getState().shots['shot-001'].narration).toBe('Local legacy work')
  })

  it('writes a changed screenplay to SQLite with expected project revision', async () => {
    let remote = snapshot(1)
    const api = {
      getProjectSnapshot: vi.fn(async () => remote),
      listStoryboards: vi.fn(async () => []),
      syncBatch: vi.fn(async (mutations: GraphMutation[], expected: number) => {
        expect(expected).toBe(1)
        const shotSync = mutations.find(item => item.op === 'sync_shots')
        expect(shotSync?.op).toBe('sync_shots')
        if (shotSync?.op === 'sync_shots') remote = { ...remote, shots: shotSync.shots, shotOrder: shotSync.shotOrder, nextShotNumber: shotSync.nextShotNumber, revision: 2, project: { ...remote.project, revision: 2 } }
        return { snapshot: remote, storyboards: [] }
      }),
    } as unknown as ApiClient
    const bridge = new PersistenceBridge(api)
    await bridge.connect()
    useStudioStore.getState().updateShot('shot-001', 'narration', 'A fresh edit')
    await bridge.connect()
    expect(api.syncBatch).toHaveBeenCalledOnce()
    expect(remote.shots['shot-001'].narration).toBe('A fresh edit')
    expect(useStudioStore.getState().syncStatus).toBe('synced')
  })

  it('blocks stale changes rather than overwriting a newer server revision', async () => {
    let remote = snapshot(1)
    const api = { getProjectSnapshot: vi.fn(async () => remote), listStoryboards: vi.fn(async () => []), syncBatch: vi.fn() } as unknown as ApiClient
    const bridge = new PersistenceBridge(api)
    await bridge.connect()
    useStudioStore.getState().updateShot('shot-001', 'narration', 'Unsynced local changes')
    remote = { ...remote, revision: 2, project: { ...remote.project, revision: 2 },
      shots: { ...remote.shots, 'shot-001': { ...remote.shots['shot-001'], narration: 'Concurrent edit' } } }
    await bridge.connect()
    expect(useStudioStore.getState().syncStatus).toBe('conflict')
    expect(api.syncBatch).not.toHaveBeenCalled()
    expect(useStudioStore.getState().shots['shot-001'].narration).toBe('Unsynced local changes')
  })

  it('queues an offline edit and replays that batch when the revision is unchanged', async () => {
    let remote = snapshot(1)
    let attempts = 0
    const api = {
      getProjectSnapshot: vi.fn(async () => {
        attempts++
        if (attempts === 2) throw new TypeError('Failed to fetch')
        return remote
      }),
      listStoryboards: vi.fn(async () => []),
      syncBatch: vi.fn(async (mutations: GraphMutation[], expected: number) => {
        expect(expected).toBe(1)
        expect(mutations.map(item => item.op)).toEqual(['sync_shots'])
        const shotSync = mutations[0]
        if (shotSync.op === 'sync_shots') remote = { ...remote, shots: shotSync.shots, shotOrder: shotSync.shotOrder, nextShotNumber: shotSync.nextShotNumber, revision: 2, project: { ...remote.project, revision: 2 } }
        return { snapshot: remote, storyboards: [] }
      }),
    } as unknown as ApiClient
    const bridge = new PersistenceBridge(api)
    await bridge.connect()
    useStudioStore.getState().updateShot('shot-001', 'narration', 'Offline line')
    await bridge.connect()
    expect(useStudioStore.getState().syncStatus).toBe('offline')
    const queued = JSON.parse(localStorage.getItem(JOURNAL_KEY) ?? '{}') as { entries: { baseRevision: number, mutations: GraphMutation[] }[] }
    expect(queued.entries[0].baseRevision).toBe(1)
    expect(queued.entries[0].mutations[0]).toMatchObject({ op: 'sync_shots' })
    await bridge.connect()
    expect(api.syncBatch).toHaveBeenCalledOnce()
    expect(localStorage.getItem(JOURNAL_KEY)).toBeNull()
    expect(useStudioStore.getState().syncStatus).toBe('synced')
    expect(remote.shots['shot-001'].narration).toBe('Offline line')
  })

  it('sends storyboard creates and updates in the atomic batch', async () => {
    let remote = snapshot(1)
    let boards: StoryboardRecord[] = []
    const api = {
      getProjectSnapshot: vi.fn(async () => remote),
      listStoryboards: vi.fn(async () => boards),
      syncBatch: vi.fn(async (mutations: GraphMutation[], expected: number) => {
        const created = mutations.find(item => item.op === 'create_storyboard')
        const updated = mutations.find(item => item.op === 'update_storyboard')
        if (created?.op === 'create_storyboard') {
          expect(expected).toBe(1)
          boards = [{ id: 'board-1', projectId: 'blueprint-pilot-01', shotId: 'shot-001', cropMode: '9:16', mediaPath: null, assetId: null, assetVersion: null, sortIndex: 0, notes: created.storyboard.notes }]
          remote = { ...remote, revision: 2, project: { ...remote.project, revision: 2 } }
        }
        if (updated?.op === 'update_storyboard') {
          expect(expected).toBe(2)
          boards = boards.map(board => board.id === updated.storyboardId ? { ...board, notes: updated.storyboard.notes } : board)
          remote = { ...remote, revision: 3, project: { ...remote.project, revision: 3 } }
        }
        return { snapshot: remote, storyboards: boards }
      }),
    } as unknown as ApiClient
    const bridge = new PersistenceBridge(api)
    await bridge.connect()
    useStudioStore.getState().upsertStoryboard({ id: 'board-1', shotId: 'shot-001', notes: 'Opening still' })
    await bridge.connect()
    useStudioStore.getState().upsertStoryboard({ id: 'board-1', shotId: 'shot-001', notes: 'Revised still' })
    await bridge.connect()
    expect(api.syncBatch).toHaveBeenCalledTimes(2)
    expect(boards[0].notes).toBe('Revised still')
    expect(useStudioStore.getState().syncStatus).toBe('synced')
  })
})

describe('atomic mutation order', () => {
  it('deletes storyboards and links before replacing shots, then writes new boards', () => {
    const before = createPilot()
    const desired = productionGraph(before)
    delete desired.shots['shot-014']
    desired.shotOrder = desired.shotOrder.filter(id => id !== 'shot-014')
    desired.links = desired.links.filter(link => link.shotId !== 'shot-014')
    desired.assets = { ...desired.assets, 'ast-mug': { ...desired.assets['ast-mug'], status: 'Rigging', currentVersion: before.assets['ast-mug'].currentVersion + 1 } }
    const prior: StoryboardRecord[] = [
      { id: 'board-cut', projectId: 'blueprint-pilot-01', shotId: 'shot-014', cropMode: '9:16', mediaPath: null, assetId: null, assetVersion: null, sortIndex: 0, notes: 'Goes away' },
      { id: 'board-keep', projectId: 'blueprint-pilot-01', shotId: 'shot-001', cropMode: '9:16', mediaPath: null, assetId: null, assetVersion: null, sortIndex: 1, notes: 'Old' },
    ]
    const next: StoryboardRecord[] = [
      { ...prior[1], notes: 'New' },
      { id: 'board-new', projectId: 'blueprint-pilot-01', shotId: 'shot-001', cropMode: '16:9', mediaPath: null, assetId: null, assetVersion: null, sortIndex: 2, notes: 'Added' },
    ]
    const ops = buildMutations(before, desired, prior, next).map(item => item.op)
    expect(ops.indexOf('update_asset')).toBeGreaterThanOrEqual(0)
    expect(ops.indexOf('update_asset')).toBeLessThan(ops.indexOf('publish_version'))
    expect(ops.indexOf('publish_version')).toBeLessThan(ops.indexOf('delete_storyboard'))
    expect(ops.indexOf('delete_storyboard')).toBeLessThan(ops.indexOf('delete_link'))
    expect(ops.indexOf('delete_link')).toBeLessThan(ops.indexOf('sync_shots'))
    expect(ops.indexOf('sync_shots')).toBeLessThan(ops.indexOf('update_storyboard'))
    expect(ops.indexOf('update_storyboard')).toBeLessThan(ops.indexOf('create_storyboard'))
  })
})
