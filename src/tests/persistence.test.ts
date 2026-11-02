import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPilot } from '../data/pilot'
import { fingerprint, productionGraph } from '../sync/graph'
import { ApiClient, ApiError, type ProjectSnapshot } from '../services/apiClient'
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
    const api = { getProjectSnapshot: vi.fn(async () => remote) } as unknown as ApiClient
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
    const api = { getProjectSnapshot: vi.fn(async () => remote) } as unknown as ApiClient
    await new PersistenceBridge(api).connect()
    expect(useStudioStore.getState().syncStatus).toBe('conflict')
    expect(useStudioStore.getState().shots['shot-001'].narration).toBe('Local legacy work')
  })

  it('writes a changed screenplay to SQLite with expected project revision', async () => {
    let remote = snapshot(1)
    const api = {
      getProjectSnapshot: vi.fn(async () => remote),
      syncShots: vi.fn(async (value: ReturnType<typeof createPilot>, expected: number) => {
        expect(expected).toBe(1)
        remote = { ...remote, ...value, revision: 2, project: { ...remote.project, revision: 2 } }
        return remote
      }),
    } as unknown as ApiClient
    const bridge = new PersistenceBridge(api)
    await bridge.connect()
    useStudioStore.getState().updateShot('shot-001', 'narration', 'A fresh edit')
    await bridge.connect()
    expect(api.syncShots).toHaveBeenCalledOnce()
    expect(remote.shots['shot-001'].narration).toBe('A fresh edit')
    expect(useStudioStore.getState().syncStatus).toBe('synced')
  })

  it('blocks stale changes rather than overwriting a newer server revision', async () => {
    let remote = snapshot(1)
    const api = { getProjectSnapshot: vi.fn(async () => remote), syncShots: vi.fn() } as unknown as ApiClient
    const bridge = new PersistenceBridge(api)
    await bridge.connect()
    useStudioStore.getState().updateShot('shot-001', 'narration', 'Unsynced local changes')
    remote = { ...remote, revision: 2, project: { ...remote.project, revision: 2 },
      shots: { ...remote.shots, 'shot-001': { ...remote.shots['shot-001'], narration: 'Concurrent edit' } } }
    await bridge.connect()
    expect(useStudioStore.getState().syncStatus).toBe('conflict')
    expect(api.syncShots).not.toHaveBeenCalled()
    expect(useStudioStore.getState().shots['shot-001'].narration).toBe('Unsynced local changes')
  })
})
