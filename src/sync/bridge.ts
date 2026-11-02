import type { ProductionData, StoryboardRecord } from '../types/studio'
import { createPilot } from '../data/pilot'
import { useStudioStore } from '../store/useStudioStore'
import { apiClient, ApiClient, ApiError, isOfflineError, PROJECT_ID, type ProjectSnapshot } from '../services/apiClient'
import { fingerprint, productionGraph } from './graph'
import { MutationJournal, createJournalId, type QueuedBatch } from './journal'
import { buildMutations, storyboardFingerprint } from './mutations'

interface Checkpoint { revision: number; graph: ProductionData; storyboards: StoryboardRecord[] }
const CHECKPOINT_KEY = 'blueprint-studios-bs-m2.1-checkpoint'
const DEBOUNCE_MS = 650
const RETRY_MS = 15000

function readCheckpoint(): Checkpoint | null {
  try {
    const raw = localStorage.getItem(CHECKPOINT_KEY)
    if (!raw) return null
    const checkpoint = JSON.parse(raw) as Partial<Checkpoint>
    if (!Number.isInteger(checkpoint.revision) || !checkpoint.graph?.shotOrder) return null
    return { revision: checkpoint.revision as number, graph: checkpoint.graph, storyboards: checkpoint.storyboards ?? [] }
  } catch { return null }
}
function writeCheckpoint(data: Checkpoint): void {
  localStorage.setItem(CHECKPOINT_KEY, JSON.stringify(data))
}
function localGraph(): ProductionData { return productionGraph(useStudioStore.getState()) }
function localBoards(): StoryboardRecord[] { return useStudioStore.getState().storyboards.map(board => ({ ...board })) }
function storeStatus(status: 'connecting' | 'synced' | 'offline' | 'pending' | 'conflict', message: string): void {
  useStudioStore.getState().setSyncStatus(status, message)
}
function sameWorkspace(graph: ProductionData, boards: StoryboardRecord[], otherGraph: ProductionData, otherBoards: StoryboardRecord[]): boolean {
  return fingerprint(graph) === fingerprint(otherGraph) && storyboardFingerprint(boards) === storyboardFingerprint(otherBoards)
}

/**
 * Serializes local graph updates through one atomic batch. Offline edits are
 * queued in the mutation journal and replayed only when the server revision
 * still matches that queue. UI-only selection does not trigger a write.
 */
export class PersistenceBridge {
  private checkpoint: Checkpoint | null = null
  private timer: ReturnType<typeof setTimeout> | null = null
  private retryTimer: ReturnType<typeof setInterval> | null = null
  private active: Promise<void> | null = null
  private stopped = false
  private unsubscribe: (() => void) | null = null
  private suppress = false
  private readonly journal: MutationJournal

  constructor(private readonly client: ApiClient = apiClient, journal?: MutationJournal) {
    this.journal = journal ?? new MutationJournal()
  }

  start(): () => void {
    this.stopped = false
    this.checkpoint = readCheckpoint()
    this.unsubscribe = useStudioStore.subscribe((state, before) => {
      if (this.suppress) return
      if (state.shots !== before.shots || state.shotOrder !== before.shotOrder
          || state.assets !== before.assets || state.links !== before.links
          || state.nextShotNumber !== before.nextShotNumber || state.storyboards !== before.storyboards) {
        storeStatus('pending', 'Local changes saved; waiting to sync')
        this.persistJournal()
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
      const status = useStudioStore.getState().syncStatus
      if (!this.stopped && this.checkpoint && !this.matchesCheckpoint() && status !== 'offline' && status !== 'conflict') this.schedule()
    })
    return this.active
  }

  private matchesCheckpoint(): boolean {
    return !!this.checkpoint && sameWorkspace(localGraph(), localBoards(), this.checkpoint.graph, this.checkpoint.storyboards)
  }

  private applyRemote(snapshot: ProjectSnapshot, storyboards: StoryboardRecord[]) {
    const current = useStudioStore.getState()
    const selectedShotId = snapshot.shots[current.selectedShotId] ? current.selectedShotId : snapshot.shotOrder[0]
    this.suppress = true
    useStudioStore.setState({
      ...productionGraph(snapshot), storyboards: storyboards.map(board => ({ ...board })), selectedShotId,
      selectedAssetId: current.selectedAssetId && snapshot.assets[current.selectedAssetId] ? current.selectedAssetId : null,
      playheadFrame: snapshot.shots[selectedShotId]?.startFrame ?? 0,
    })
    this.suppress = false
  }

  private saveBaseline(snapshot: ProjectSnapshot, storyboards: StoryboardRecord[]): void {
    this.checkpoint = { revision: snapshot.revision, graph: productionGraph(snapshot), storyboards: storyboards.map(board => ({ ...board })) }
    writeCheckpoint(this.checkpoint)
  }

  /** Record the diff from the confirmed baseline. A failed network call leaves this queue intact. */
  private persistJournal(): void {
    try {
      const base = this.checkpoint
      if (!base) return
      const pending = this.journal.read()
      if (pending && pending.baseRevision !== base.revision) return
      const mutations = buildMutations(base.graph, localGraph(), base.storyboards, localBoards())
      if (mutations.length === 0) {
        this.journal.clear()
        return
      }
      const batch: QueuedBatch = {
        id: pending?.id ?? createJournalId(), baseRevision: base.revision, mutations, recordedAt: new Date().toISOString(),
      }
      this.journal.enqueue(batch)
    } catch { /* The studio store still holds the editable draft. */ }
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
      const remoteBoards = await this.client.listStoryboards(PROJECT_ID)
      const now = localGraph()
      const boards = localBoards()
      const base = this.checkpoint
      if (sameWorkspace(now, boards, remote, remoteBoards)) {
        this.journal.clear()
        this.saveBaseline(remote, remoteBoards)
        storeStatus('synced', 'Saved in SQLite')
        return
      }
      if (base) {
        if (sameWorkspace(now, boards, base.graph, base.storyboards)) {
          this.journal.clear()
          this.applyRemote(remote, remoteBoards)
          this.saveBaseline(remote, remoteBoards)
          storeStatus('synced', 'Loaded latest SQLite snapshot')
          return
        }
        if (base.revision !== remote.revision || !sameWorkspace(base.graph, base.storyboards, remote, remoteBoards)) {
          storeStatus('conflict', 'Local changes differ from a newer SQLite revision; choose which copy to keep')
          return
        }
        await this.pushWorkspace(remote.revision)
      } else if (fingerprint(now) === fingerprint(createPilot()) && boards.length === 0) {
        // No pre-existing edits: prefer SQLite, never the default pilot seed.
        this.journal.clear()
        this.applyRemote(remote, remoteBoards)
        this.saveBaseline(remote, remoteBoards)
        storeStatus('synced', 'Loaded SQLite project')
        return
      } else {
        // BS-M1 localStorage may hold unpublished work. Keep it untouched.
        storeStatus('conflict', 'Existing local browser edits differ from SQLite; review before replacing either copy')
        return
      }
      if (this.stopped || useStudioStore.getState().syncStatus === 'conflict') return
      if (this.matchesCheckpoint()) storeStatus('synced', 'Saved in SQLite')
      else storeStatus('pending', 'Newer local edits waiting to sync')
    } catch (err) {
      if (this.stopped) return
      if (isOfflineError(err)) {
        this.persistJournal()
        storeStatus('offline', 'FastAPI unavailable; changes stay saved locally')
      } else if (err instanceof ApiError && err.status === 409) storeStatus('conflict', 'SQLite revision conflict; local edits preserved')
      else storeStatus('conflict', `Sync paused: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  private async pushWorkspace(revision: number): Promise<void> {
    this.persistJournal()
    const pending = this.journal.read()
    if (!pending || pending.mutations.length === 0) return
    if (pending.baseRevision !== revision) {
      storeStatus('conflict', 'Queued edits belong to an older SQLite revision')
      return
    }
    const result = await this.client.syncBatch(this.journal.replay(), pending.baseRevision)
    this.journal.clear()
    this.saveBaseline(result.snapshot, result.storyboards)
  }

  /** Revision to send with an upload. Local edits are flushed first so the file is not a second publish. */
  async readyRevision(): Promise<number> {
    await this.connect()
    if (!this.matchesCheckpoint()) await this.connect()
    const status = useStudioStore.getState().syncStatus
    if (!this.checkpoint || !this.matchesCheckpoint() || status === 'conflict' || status === 'offline') {
      throw new Error('Save the workspace to SQLite before uploading media')
    }
    return this.checkpoint.revision
  }

  /**
   * Fold a server-hashed upload into the confirmed graph.
   * Pins, status, and the selected shot stay as they were. The bridge does not publish a second version.
   */
  acceptUploadedVersion(assetId: string, version: number, revision: number): void {
    if (!Number.isInteger(version) || version < 1) throw new Error('Uploaded version is invalid')
    if (!Number.isInteger(revision) || revision < 0) throw new Error('Uploaded revision is invalid')
    const checkpoint = this.checkpoint
    if (!checkpoint) throw new Error('No confirmed SQLite revision')
    const asset = useStudioStore.getState().assets[assetId]
    const baseline = checkpoint.graph.assets[assetId]
    if (!asset || !baseline) throw new Error(`Unknown asset: ${assetId}`)
    if (version < asset.currentVersion || version < baseline.currentVersion) {
      throw new Error(`Cannot decrement asset version: ${assetId}`)
    }
    this.suppress = true
    try {
      useStudioStore.setState(state => ({
        assets: { ...state.assets, [assetId]: { ...state.assets[assetId], currentVersion: version } },
      }))
    } finally {
      this.suppress = false
    }
    this.checkpoint = {
      revision,
      graph: {
        ...checkpoint.graph,
        assets: { ...checkpoint.graph.assets, [assetId]: { ...baseline, currentVersion: version } },
      },
      storyboards: checkpoint.storyboards,
    }
    writeCheckpoint(this.checkpoint)
    this.journal.clear()
    this.persistJournal()
  }

  /** Explicitly discards the browser copy after remote/local conflict. */
  async useServerCopy(): Promise<void> {
    const snapshot = await this.client.getProjectSnapshot(PROJECT_ID)
    const storyboards = await this.client.listStoryboards(PROJECT_ID)
    this.applyRemote(snapshot, storyboards)
    this.saveBaseline(snapshot, storyboards)
    this.journal.clear()
    storeStatus('synced', 'Using SQLite project')
  }
}

export const persistenceBridge = new PersistenceBridge()
