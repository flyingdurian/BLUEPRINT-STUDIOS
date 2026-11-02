import type { GraphMutation } from '../sync/mutations'
import type { Asset, AssetLink, ProductionData, Shot, StoryboardDraft, StoryboardRecord } from '../types/studio'

export type { StoryboardDraft, StoryboardRecord }

// The existing BS-M2 routes use camelCase JSON, matching BS-M1's store.
export interface ProjectRecord {
  id: string
  name: string
  fps: number
  revision: number
  nextShotNumber: number
}
export interface ProjectSnapshot extends ProductionData {
  project: ProjectRecord
  revision: number
}
export interface AssetVersion {
  assetId: string
  version: number
  sha256: string | null
  relativePath: string | null
  description: string
  source: string
}
export interface SyncBatchResult {
  snapshot: ProjectSnapshot
  storyboards: StoryboardRecord[]
}

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly detail: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

export function isOfflineError(error: unknown): boolean {
  // Fetch network failure, refused connection or abort/timeout.
  return error instanceof TypeError || (error instanceof DOMException && error.name === 'AbortError')
}

const defaultApiBase = 'http://127.0.0.1:8000'
export const PROJECT_ID = 'blueprint-pilot-01'

export class ApiClient {
  constructor(readonly baseUrl = import.meta.env.VITE_STUDIO_API_BASE_URL || defaultApiBase,
              private readonly timeoutMs = 3500) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeoutMs)
    try {
      const response = await fetch(`${this.baseUrl.replace(/\/$/, '')}${path}`, {
        ...init, signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...init.headers },
      })
      if (!response.ok) {
        const detail: unknown = await response.json().catch(() => response.statusText)
        throw new ApiError(response.status, detail, `API ${response.status}: ${path}`)
      }
      return (response.status === 204 ? undefined : await response.json()) as T
    } finally { clearTimeout(timer) }
  }

  private projectPath(projectId: string): string {
    return `/api/projects/${encodeURIComponent(projectId)}`
  }
  health(): Promise<{ status: string }> { return this.request('/api/health') }
  createProject(id = PROJECT_ID, name = "Congratulations, You're the Organizer", fps = 30): Promise<ProjectRecord> {
    return this.request('/api/projects', { method: 'POST', body: JSON.stringify({ id, name, fps }) })
  }
  getProjectSnapshot(id = PROJECT_ID): Promise<ProjectSnapshot> {
    return this.request(`${this.projectPath(id)}/snapshot`)
  }
  bootstrapProject(graph: ProductionData, id = PROJECT_ID): Promise<ProjectSnapshot> {
    return this.request(`${this.projectPath(id)}/bootstrap`, { method: 'POST', body: JSON.stringify(graph) })
  }
  syncShots(graph: Pick<ProductionData, 'shots' | 'shotOrder' | 'nextShotNumber'>, revision: number, id = PROJECT_ID): Promise<ProjectSnapshot> {
    return this.request(`${this.projectPath(id)}/shots/sync`, { method: 'PUT', body: JSON.stringify({ ...graph, expectedRevision: revision }) })
  }
  updateShot(shotId: string, patch: Partial<Pick<Shot, 'visual' | 'narration' | 'notes' | 'startFrame' | 'durationFrames' | 'artKey' | 'mood'>>, revision: number, id = PROJECT_ID): Promise<Shot> {
    return this.request(`${this.projectPath(id)}/shots/${encodeURIComponent(shotId)}`, { method: 'PATCH', body: JSON.stringify({ ...patch, expectedRevision: revision }) })
  }
  createAsset(asset: Asset, id = PROJECT_ID): Promise<Asset> {
    const { id: assetId, name, category, status, color, shorthand } = asset
    return this.request(`${this.projectPath(id)}/assets`, { method: 'POST',
      body: JSON.stringify({ id: assetId, name, category, status, color, shorthand }) })
  }
  updateAsset(assetId: string, patch: Partial<Pick<Asset, 'name' | 'status' | 'color' | 'shorthand'>>, revision: number, id = PROJECT_ID): Promise<Asset> {
    return this.request(`${this.projectPath(id)}/assets/${encodeURIComponent(assetId)}`, { method: 'PATCH', body: JSON.stringify({ ...patch, expectedRevision: revision }) })
  }
  listAssetVersions(assetId: string, id = PROJECT_ID): Promise<AssetVersion[]> {
    return this.request(`${this.projectPath(id)}/assets/${encodeURIComponent(assetId)}/versions`)
  }
  publishAssetVersion(assetId: string, revision: number, description = 'Director OS version update', id = PROJECT_ID): Promise<AssetVersion> {
    return this.request(`${this.projectPath(id)}/assets/${encodeURIComponent(assetId)}/versions`, {
      method: 'POST', body: JSON.stringify({ expectedRevision: revision, description }),
    })
  }
  linkAsset(shotId: string, assetId: string, pinnedVersion: number, revision: number, id = PROJECT_ID): Promise<AssetLink> {
    return this.request(`${this.projectPath(id)}/shots/${encodeURIComponent(shotId)}/assets/${encodeURIComponent(assetId)}`, {
      method: 'PUT', body: JSON.stringify({ pinnedVersion, expectedRevision: revision }),
    })
  }
  unlinkAsset(shotId: string, assetId: string, id = PROJECT_ID): Promise<void> {
    return this.request(`${this.projectPath(id)}/shots/${encodeURIComponent(shotId)}/assets/${encodeURIComponent(assetId)}`, { method: 'DELETE' })
  }
  listStoryboards(id = PROJECT_ID): Promise<StoryboardRecord[]> {
    return this.request(`${this.projectPath(id)}/storyboards`)
  }
  createStoryboard(data: StoryboardDraft, id = PROJECT_ID): Promise<StoryboardRecord> {
    return this.request(`${this.projectPath(id)}/storyboards`, { method: 'POST', body: JSON.stringify(data) })
  }
  updateStoryboard(storyboardId: string, data: StoryboardDraft, revision?: number, id = PROJECT_ID): Promise<StoryboardRecord> {
    return this.request(`${this.projectPath(id)}/storyboards/${encodeURIComponent(storyboardId)}`, {
      method: 'PUT', body: JSON.stringify({ ...storyboardWrite(data), ...(revision === undefined ? {} : { expectedRevision: revision }) }),
    })
  }
  deleteStoryboard(storyboardId: string, revision?: number, id = PROJECT_ID): Promise<void> {
    const query = revision === undefined ? '' : `?expectedRevision=${encodeURIComponent(String(revision))}`
    return this.request(`${this.projectPath(id)}/storyboards/${encodeURIComponent(storyboardId)}${query}`, { method: 'DELETE' })
  }
  syncBatch(mutations: GraphMutation[], revision: number, id = PROJECT_ID): Promise<SyncBatchResult> {
    return this.request(`${this.projectPath(id)}/sync-batch`, {
      method: 'POST', body: JSON.stringify({ expectedRevision: revision, mutations }),
    })
  }
  /** Reconcile storyboard records. Unchanged ids are left in place; edits PUT and removals DELETE. */
  async syncStoryboards(drafts: StoryboardDraft[], revision?: number, id = PROJECT_ID): Promise<StoryboardRecord[]> {
    const existing = await this.listStoryboards(id)
    let nextRevision = revision
    const wanted = new Set(drafts.flatMap(board => board.id ? [board.id] : []))
    for (const board of existing) {
      if (wanted.has(board.id)) continue
      await this.deleteStoryboard(board.id, nextRevision, id)
      if (nextRevision !== undefined) nextRevision++
    }
    const known = new Map(existing.map(board => [board.id, board]))
    const result: StoryboardRecord[] = []
    for (const draft of drafts) {
      const current = draft.id ? known.get(draft.id) : undefined
      if (current && storyboardDraftMatches(current, draft)) result.push(current)
      else if (current && draft.id) {
        result.push(await this.updateStoryboard(draft.id, {
          shotId: draft.shotId,
          cropMode: draft.cropMode ?? current.cropMode,
          mediaPath: draft.mediaPath !== undefined ? draft.mediaPath : current.mediaPath,
          assetId: draft.assetId !== undefined ? draft.assetId : current.assetId,
          assetVersion: draft.assetVersion !== undefined ? draft.assetVersion : current.assetVersion,
          sortIndex: draft.sortIndex ?? current.sortIndex,
          notes: draft.notes ?? current.notes,
        }, nextRevision, id))
        if (nextRevision !== undefined) nextRevision++
      } else {
        result.push(await this.createStoryboard(draft, id))
        if (nextRevision !== undefined) nextRevision++
      }
    }
    return result
  }
}

function storyboardWrite(data: StoryboardDraft) {
  return {
    shotId: data.shotId,
    cropMode: data.cropMode ?? '9:16',
    mediaPath: data.mediaPath ?? null,
    assetId: data.assetId ?? null,
    assetVersion: data.assetVersion ?? null,
    sortIndex: data.sortIndex ?? 0,
    notes: data.notes ?? '',
  }
}

function storyboardDraftMatches(record: StoryboardRecord, draft: StoryboardDraft): boolean {
  if (draft.shotId !== record.shotId) return false
  if (draft.cropMode !== undefined && draft.cropMode !== record.cropMode) return false
  if (draft.mediaPath !== undefined && draft.mediaPath !== record.mediaPath) return false
  if (draft.assetId !== undefined && draft.assetId !== record.assetId) return false
  if (draft.assetVersion !== undefined && draft.assetVersion !== record.assetVersion) return false
  if (draft.sortIndex !== undefined && draft.sortIndex !== record.sortIndex) return false
  if (draft.notes !== undefined && draft.notes !== record.notes) return false
  return true
}
export const apiClient = new ApiClient()
