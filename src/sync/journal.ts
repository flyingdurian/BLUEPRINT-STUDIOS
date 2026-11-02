import type { GraphMutation } from './mutations'

export const JOURNAL_KEY = 'blueprint-studios-bs-m2.2-journal'

export interface QueuedBatch {
  id: string
  baseRevision: number
  mutations: GraphMutation[]
  recordedAt: string
}

interface JournalFile { entries: QueuedBatch[] }

export function createJournalId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `journal-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

/**
 * Durable queue of offline graph edits. Edits against the same confirmed
 * revision coalesce into one ordered batch so a replay cannot publish a version twice.
 */
export class MutationJournal {
  constructor(private readonly storage?: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>,
              private readonly key = JOURNAL_KEY) {}

  private get store(): Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> {
    return this.storage ?? localStorage
  }

  entries(): QueuedBatch[] {
    try {
      const raw = this.store.getItem(this.key)
      if (!raw) return []
      const parsed = JSON.parse(raw) as Partial<JournalFile>
      if (!Array.isArray(parsed.entries)) return []
      return parsed.entries.filter(entry => typeof entry?.id === 'string'
        && Number.isInteger(entry.baseRevision) && Array.isArray(entry.mutations))
    } catch { return [] }
  }

  read(): QueuedBatch | null { return this.entries()[0] ?? null }

  /** Replace the pending batch for this baseline. Returns false when an older queue is still unacknowledged. */
  enqueue(batch: QueuedBatch): boolean {
    const existing = this.entries()
    if (existing.some(entry => entry.baseRevision !== batch.baseRevision)) return false
    const next: QueuedBatch = { ...batch, id: existing[0]?.id ?? batch.id, mutations: [...batch.mutations] }
    this.store.setItem(this.key, JSON.stringify({ entries: [next] } satisfies JournalFile))
    return true
  }

  replay(): GraphMutation[] { return this.entries().flatMap(entry => entry.mutations) }

  clear(): void { this.store.removeItem(this.key) }
}
