import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError, PROJECT_ID } from '../services/apiClient'
import { createPilot } from '../data/pilot'

afterEach(() => vi.unstubAllGlobals())

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
})

describe('BS-M2.1 API client request contract', () => {
  it('reads project snapshots with the existing BS-M2 endpoint', async () => {
    const fetcher = vi.fn(async (_url: string, _init?: RequestInit) => json({ revision: 1, ...createPilot() }))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient('http://127.0.0.1:8000')
    const snap = await client.getProjectSnapshot()
    expect(snap.shotOrder).toHaveLength(14)
    expect(fetcher.mock.calls[0][0]).toBe(`http://127.0.0.1:8000/api/projects/${PROJECT_ID}/snapshot`)
  })

  it('includes expectedRevision when patching a shot', async () => {
    const fetcher = vi.fn(async (_url: string, _init?: RequestInit) => json({ id: 'shot-001' }))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient('http://127.0.0.1:8000')
    await client.updateShot('shot-001', { narration: 'Changed!' }, 7)
    const [, request] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(request.method).toBe('PATCH')
    expect(JSON.parse(request.body as string)).toEqual({ expectedRevision: 7, narration: 'Changed!' })
  })

  it('preserves the 409 conflict response instead of retrying destructively', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ detail: 'Stale revision' }, 409)))
    const client = new ApiClient('http://127.0.0.1:8000')
    await expect(client.getProjectSnapshot()).rejects.toMatchObject({ status: 409, name: 'ApiError' } satisfies Partial<ApiError>)
  })

  it('syncs only the keys accepted by the FastAPI ShotSync schema', async () => {
    const fetcher = vi.fn(async (_url: string, _init?: RequestInit) => json({ revision: 4 }))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient('http://127.0.0.1:8000')
    const graph = createPilot()
    await client.syncShots({ shots: graph.shots, shotOrder: graph.shotOrder, nextShotNumber: graph.nextShotNumber }, 3)
    const [, request] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    const body = JSON.parse(request.body as string)
    expect(Object.keys(body).sort()).toEqual(['expectedRevision', 'nextShotNumber', 'shotOrder', 'shots'])
  })

  it('omits currentVersion when creating an asset (FastAPI extra=forbid)', async () => {
    const fetcher = vi.fn(async (_url: string, _init?: RequestInit) => json({ id: 'ast-mug' }, 201))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient('http://127.0.0.1:8000')
    await client.createAsset(createPilot().assets['ast-mug'])
    const [, request] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(JSON.parse(request.body as string)).not.toHaveProperty('currentVersion')
  })

  it('posts one revision-checked sync batch', async () => {
    const fetcher = vi.fn(async () => json({ snapshot: { revision: 5 }, storyboards: [] }))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient('http://127.0.0.1:8000')
    await client.syncBatch([{ op: 'delete_storyboard', storyboardId: 'board-1' }], 4)
    const [url, request] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`http://127.0.0.1:8000/api/projects/${PROJECT_ID}/sync-batch`)
    expect(request.method).toBe('POST')
    expect(JSON.parse(request.body as string)).toEqual({ expectedRevision: 4, mutations: [{ op: 'delete_storyboard', storyboardId: 'board-1' }] })
  })

  it('can fetch storyboard records and add only missing IDs', async () => {
    const fetcher = vi.fn(async (_: string, request: RequestInit) =>
      request.method === 'POST' ? json({ id: 'board-new', shotId: 'shot-004' }, 201) : json([{ id: 'board-old', shotId: 'shot-001' }]))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient('http://127.0.0.1:8000')
    const all = await client.syncStoryboards([{ id: 'board-old', shotId: 'shot-001' }, { id: 'board-new', shotId: 'shot-004' }])
    expect(all).toHaveLength(2)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('updates a changed storyboard and deletes records missing from the draft', async () => {
    const fetcher = vi.fn(async (_url: string, request: RequestInit = {}) => {
      if (request.method === 'DELETE') return new Response(null, { status: 204 })
      if (request.method === 'PUT') return json({ id: 'board-old', shotId: 'shot-001', notes: 'Changed' })
      return json([
        { id: 'board-old', shotId: 'shot-001', notes: 'Old' },
        { id: 'board-gone', shotId: 'shot-002', notes: '' },
      ])
    })
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient('http://127.0.0.1:8000')
    await client.syncStoryboards([{ id: 'board-old', shotId: 'shot-001', notes: 'Changed' }], 4)
    const [deleteUrl, deleteRequest] = fetcher.mock.calls[1] as unknown as [string, RequestInit]
    const [putUrl, putRequest] = fetcher.mock.calls[2] as unknown as [string, RequestInit]
    expect(deleteRequest.method).toBe('DELETE')
    expect(deleteUrl).toContain('/storyboards/board-gone?expectedRevision=4')
    expect(putRequest.method).toBe('PUT')
    expect(putUrl).toContain('/storyboards/board-old')
    expect(JSON.parse(putRequest.body as string).expectedRevision).toBe(5)
    expect(JSON.parse(putRequest.body as string).notes).toBe('Changed')
  })
})
