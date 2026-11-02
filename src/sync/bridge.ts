import type { ProductionData } from '../types/studio'
import { createPilot } from '../data/pilot'
import { useStudioStore } from '../store/useStudioStore'
import { apiClient, ApiClient, ApiError, isOfflineError, PROJECT_ID, type ProjectSnapshot } from '../services/apiClient'
import { assetMetadataChanged, fingerprint, productionGraph, shotsChanged } from './graph'

interface Checkpoint { revision: number; graph: ProductionData }
const CHECKPOINT_KEY = 'blueprint-studios-bs-m2.1-checkpoint'
const DEBOUNCE_MS = 650
const RETRY_MS = 15000

function readCheckpoint(): Checkpoint | null {
  try {
    const raw = localStorage.getItem(CHECKPOINT_KEY)
    if (!raw) return null
    const checkpoint = JSON.parse(raw) as Checkpoint
    return Number.isInteger(checkpoint.revision) && checkpoint.graph?.shotOrder ? checkpoint : null
  } catch { return null }
}
function writeCheckpoint(data: Checkpoint): void {
  localStorage.setItem(CHECKPOINT_KEY, JSON.stringify(data))
}
function localGraph(): ProductionData { return productionGraph(useStudioStore.getState()) }
function storeStatus(status: 'connecting' | 'synced' | 'offline' | 'pending' | 'conflict', message: string): void {
  useStudioStore.getState().setSyncStatus(status, message)
}

/**
 * Serializes local graph updates to existing BS-M2 endpoints. UI-only selection
 * does not trigger a write. No destructive remote overwrite on revision conflict.
 */
export class PersistenceBridge {
  private checkpoint: Checkpoint | null = null
  private timer: ReturnType<typeof setTimeout> | null = null
  private retryTimer: ReturnType<typeof setInterval> | null = null
  private active: Promise<void> | null = null
  private stopped = false
  private unsubscribe: (() => void) | null = null
  private suppress = false

  constructor(private readonly client: ApiClient = apiClient) {}

  start(): () => void {
    this.stopped = false
    this.checkpoint = readCheckpoint()
    this.unsubscribe = useStudioStore.subscribe((state, before) => {
      if (this.suppress) return
      if (state.shots !== before.shots || state.shotOrder !== before.shotOrder
          || state.assets !== before.assets || state.links !== before.links
          || state.nextShotNumber !== before.nextShotNumber) {
        storeStatus('pending', 'Local changes saved; waiting to sync')
        this.schedule()
      }
    })
    const online = () => void this.connect()
    window.addEventListener('online', online)
    this.retryTimer = setInterval(() => {
      if (useStudioStore.getState().syncStatus === 'offline') void this.connect()
    }, RETRY_MS)
    void this.connect()
    return () => {
      this.stopped = true
      this.unsubscribe?.()
      this.unsubscribe = null
      window.removeEventListener('online', online)
      if (this.timer) clearTimeout(this.timer)
      if (this.retryTimer) clearInterval(this.retryTimer)
    }
  }

  private schedule() {
    if (this.stopped) return
    if (this.timer) clearTimeout(this.timer)
    this.timer = setTimeout(() => void this.connect(), DEBOUNCE_MS)
  }

  connect(): Promise<void> {
    if (this.stopped) return Promise.resolve()
    if (!this.checkpoint) this.checkpoint = readCheckpoint()
    if (this.active) return this.active
    this.active = this.reconcile().finally(() => {
      this.active = null
      // Edits made during the request must still be sent, not erased.
      if (!this.stopped && this.checkpoint && fingerprint(localGraph()) !== fingerprint(this.checkpoint.graph)
          && useStudioStore.getState().syncStatus !== 'offline'
          && useStudioStore.getState().syncStatus !== 'conflict') this.schedule()
    })
    return this.active
  }

  private applyRemote(snapshot: ProjectSnapshot) {
    const current = useStudioStore.getState()
    const selectedShotId = snapshot.shots[current.selectedShotId] ? current.selectedShotId : snapshot.shotOrder[0]
    this.suppress = true
    useStudioStore.setState({
      ...productionGraph(snapshot), selectedShotId,
      selectedAssetId: current.selectedAssetId && snapshot.assets[current.selectedAssetId] ? current.selectedAssetId : null,
      playheadFrame: snapshot.shots[selectedShotId]?.startFrame ?? 0,
    })
    this.suppress = false
  }

  private saveBaseline(snapshot: ProjectSnapshot): void {
    this.checkpoint = { revision: snapshot.revision, graph: productionGraph(snapshot) }
    writeCheckpoint(this.checkpoint)
  }

  private async reconcile(): Promise<void> {
    storeStatus('connecting', 'Connecting to local SQLite workspace')
    try {
      let remote: ProjectSnapshot
      try {
        remote = await this.client.getProjectSnapshot(PROJECT_ID)
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 404)) throw err
        // First launch: create an empty project, then import local pilot data.
        try { await this.client.createProject(PROJECT_ID) }
        catch (createErr) { if (!(createErr instanceof ApiError && createErr.status === 409)) throw createErr }
        try { remote = await this.client.bootstrapProject(localGraph(), PROJECT_ID) }
        catch (bootstrapErr) {
          if (!(bootstrapErr instanceof ApiError && bootstrapErr.status === 409)) throw bootstrapErr
          remote = await this.client.getProjectSnapshot(PROJECT_ID)
        }
      }
      if (this.stopped) return
      // Project may exist from an interrupted setup but have no data yet.
      if (remote.shotOrder.length === 0 && Object.keys(remote.assets).length === 0 && !this.checkpoint) {
        try { remote = await this.client.bootstrapProject(localGraph(), PROJECT_ID) }
        catch (err) {
          if (!(err instanceof ApiError && err.status === 409)) throw err
          remote = await this.client.getProjectSnapshot(PROJECT_ID)
        }
      }
      const now = localGraph()
      const localHash = fingerprint(now)
      const remoteHash = fingerprint(remote)
      const base = this.checkpoint
      if (localHash === remoteHash) {
        this.saveBaseline(remote)
        storeStatus('synced', 'Saved in SQLite')
        return
      }
      if (base) {
        const baseHash = fingerprint(base.graph)
        if (localHash === baseHash) {
          this.applyRemote(remote)
          this.saveBaseline(remote)
          storeStatus('synced', 'Loaded latest SQLite snapshot')
          return
        }
        if (base.revision !== remote.revision || baseHash !== remoteHash) {
          storeStatus('conflict', 'Local changes differ from a newer SQLite revision; choose which copy to keep')
          return
        }
        await this.pushChanges(base.graph, now, remote.revision)
      } else if (localHash === fingerprint(createPilot())) {
        // No pre-existing edits: prefer SQLite, never the default pilot seed.
        this.applyRemote(remote)
        this.saveBaseline(remote)
        storeStatus('synced', 'Loaded SQLite project')
        return
      } else {
        // BS-M1 localStorage may hold unpublished work. Keep it untouched.
        storeStatus('conflict', 'Existing local browser edits differ from SQLite; review before replacing either copy')
        return
      }
      const updated = await this.client.getProjectSnapshot(PROJECT_ID)
      this.saveBaseline(updated)
      if (fingerprint(localGraph()) === fingerprint(updated)) storeStatus('synced', 'Saved in SQLite')
      else storeStatus('pending', 'Newer local edits waiting to sync')
    } catch (err) {
      if (this.stopped) return
      if (isOfflineError(err)) storeStatus('offline', 'FastAPI unavailable; changes stay saved locally')
      else if (err instanceof ApiError && err.status === 409) storeStatus('conflict', 'SQLite revision conflict; local edits preserved')
      else storeStatus('conflict', `Sync paused: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  private async pushChanges(before: ProductionData, desired: ProductionData, revision: number): Promise<void> {
    // Writes are serialized. Each response increments project.revision by one.
    // Asset creation and version publication are separate BS-M2 endpoints.
    for (const [assetId, asset] of Object.entries(desired.assets)) {
      const original = before.assets[assetId]
      if (!original) {
        await this.client.createAsset(asset)
        revision++
      } else if (assetMetadataChanged(original, asset)) {
        await this.client.updateAsset(assetId, {
          name: asset.name, status: asset.status, color: asset.color, shorthand: asset.shorthand,
        }, revision)
        revision++
      }
    }
    for (const [assetId, asset] of Object.entries(desired.assets)) {
      const original = before.assets[assetId]
      const oldVersion = original?.currentVersion ?? 1
      if (asset.currentVersion < oldVersion) throw new Error(`Cannot decrement asset version: ${assetId}`)
      for (let v = oldVersion; v < asset.currentVersion; v++) {
        await this.client.publishAssetVersion(assetId, revision)
        revision++
      }
    }
    if (shotsChanged(before, desired)) {
      const result = await this.client.syncShots({
        shots: desired.shots, shotOrder: desired.shotOrder, nextShotNumber: desired.nextShotNumber,
      }, revision)
      revision = result.revision
    }
    const originalLinks = new Map(before.links.map(l => [`${l.shotId}\u0000${l.assetId}`, l]))
    const desiredLinks = new Map(desired.links.map(l => [`${l.shotId}\u0000${l.assetId}`, l]))
    for (const [key, link] of originalLinks) {
      if (!desiredLinks.has(key)) {
        await this.client.unlinkAsset(link.shotId, link.assetId)
        revision++
      }
    }
    for (const [key, link] of desiredLinks) {
      if (originalLinks.get(key)?.pinnedVersion !== link.pinnedVersion) {
        await this.client.linkAsset(link.shotId, link.assetId, link.pinnedVersion, revision)
        revision++
      }
    }
  }

  /** Explicitly discards the browser copy after remote/local conflict. */
  async useServerCopy(): Promise<void> {
    const snapshot = await this.client.getProjectSnapshot(PROJECT_ID)
    this.applyRemote(snapshot)
    this.saveBaseline(snapshot)
    storeStatus('synced', 'Using SQLite project')
  }
}

export const persistenceBridge = new PersistenceBridge()
