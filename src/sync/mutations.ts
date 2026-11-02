import type { Asset, ProductionData, StoryboardRecord } from '../types/studio'
import { shotsChanged } from './graph'

export type GraphMutation =
  | { op: 'create_asset'; asset: Pick<Asset, 'id' | 'name' | 'category' | 'status' | 'color' | 'shorthand'> }
  | { op: 'update_asset'; assetId: string; name?: string; status?: Asset['status']; color?: string; shorthand?: string }
  | { op: 'publish_version'; assetId: string; description?: string; sha256?: string | null; relativePath?: string | null }
  | { op: 'sync_shots'; shots: ProductionData['shots']; shotOrder: string[]; nextShotNumber: number }
  | { op: 'upsert_link'; shotId: string; assetId: string; pinnedVersion: number }
  | { op: 'delete_link'; shotId: string; assetId: string }
  | { op: 'create_storyboard'; storyboard: StoryboardWrite & { id?: string } }
  | { op: 'update_storyboard'; storyboardId: string; storyboard: StoryboardWrite }
  | { op: 'delete_storyboard'; storyboardId: string }

interface StoryboardWrite {
  shotId: string
  cropMode: StoryboardRecord['cropMode']
  mediaPath: string | null
  assetId: string | null
  assetVersion: number | null
  sortIndex: number
  notes: string
}

function linkKey(shotId: string, assetId: string): string {
  return `${shotId}\u0000${assetId}`
}

function storyboardWrite(board: StoryboardRecord): StoryboardWrite {
  return {
    shotId: board.shotId, cropMode: board.cropMode, mediaPath: board.mediaPath,
    assetId: board.assetId, assetVersion: board.assetVersion, sortIndex: board.sortIndex, notes: board.notes,
  }
}

function sameStoryboard(a: StoryboardRecord, b: StoryboardRecord): boolean {
  const left = storyboardWrite(a)
  const right = storyboardWrite(b)
  return (Object.keys(left) as (keyof StoryboardWrite)[]).every(key => left[key] === right[key])
}

export function storyboardFingerprint(boards: StoryboardRecord[]): string {
  const ordered = [...boards].sort((a, b) => a.id.localeCompare(b.id)).map(board => ({ id: board.id, ...storyboardWrite(board) }))
  return JSON.stringify(ordered)
}

/**
 * Ordered diff from the last confirmed graph to the desired local graph.
 * Deletes run before shot removal; creates and replacements run after the shot list exists.
 * Repeated calls replace a pending journal entry so version bumps are not applied twice.
 */
export function buildMutations(before: ProductionData, desired: ProductionData,
                               beforeBoards: StoryboardRecord[], desiredBoards: StoryboardRecord[]): GraphMutation[] {
  const assetOps: GraphMutation[] = []
  for (const [assetId, asset] of Object.entries(desired.assets)) {
    const original = before.assets[assetId]
    if (!original) {
      assetOps.push({ op: 'create_asset', asset: {
        id: asset.id, name: asset.name, category: asset.category, status: asset.status, color: asset.color, shorthand: asset.shorthand,
      } })
      for (let version = 1; version < asset.currentVersion; version++) {
        assetOps.push({ op: 'publish_version', assetId, description: 'Director OS version update' })
      }
      continue
    }
    if (asset.currentVersion < original.currentVersion) throw new Error(`Cannot decrement asset version: ${assetId}`)
    const metadata: Extract<GraphMutation, { op: 'update_asset' }> = { op: 'update_asset', assetId }
    if (original.name !== asset.name) metadata.name = asset.name
    if (original.status !== asset.status) metadata.status = asset.status
    if (original.color !== asset.color) metadata.color = asset.color
    if (original.shorthand !== asset.shorthand) metadata.shorthand = asset.shorthand
    if (metadata.name || metadata.status || metadata.color || metadata.shorthand) assetOps.push(metadata)
    for (let version = original.currentVersion; version < asset.currentVersion; version++) {
      assetOps.push({ op: 'publish_version', assetId, description: 'Director OS version update' })
    }
  }

  const beforeIds = new Map(beforeBoards.map(board => [board.id, board]))
  const desiredIds = new Map(desiredBoards.map(board => [board.id, board]))
  const storyboardDeletes: GraphMutation[] = beforeBoards
    .filter(board => !desiredIds.has(board.id))
    .map(board => ({ op: 'delete_storyboard', storyboardId: board.id }))

  const beforeLinks = new Map(before.links.map(link => [linkKey(link.shotId, link.assetId), link]))
  const desiredLinks = new Map(desired.links.map(link => [linkKey(link.shotId, link.assetId), link]))
  const linkDeletes: GraphMutation[] = []
  for (const [key, link] of beforeLinks) {
    if (!desiredLinks.has(key)) linkDeletes.push({ op: 'delete_link', shotId: link.shotId, assetId: link.assetId })
  }

  const shotOps: GraphMutation[] = []
  if (shotsChanged(before, desired)) {
    shotOps.push({ op: 'sync_shots', shots: desired.shots, shotOrder: desired.shotOrder, nextShotNumber: desired.nextShotNumber })
  }

  const linkUpserts: GraphMutation[] = []
  for (const [key, link] of desiredLinks) {
    if (beforeLinks.get(key)?.pinnedVersion !== link.pinnedVersion) {
      linkUpserts.push({ op: 'upsert_link', shotId: link.shotId, assetId: link.assetId, pinnedVersion: link.pinnedVersion })
    }
  }

  const storyboardWrites: GraphMutation[] = []
  for (const board of desiredBoards) {
    const previous = beforeIds.get(board.id)
    if (!previous) storyboardWrites.push({ op: 'create_storyboard', storyboard: { id: board.id, ...storyboardWrite(board) } })
    else if (!sameStoryboard(previous, board)) storyboardWrites.push({ op: 'update_storyboard', storyboardId: board.id, storyboard: storyboardWrite(board) })
  }

  return [...assetOps, ...storyboardDeletes, ...linkDeletes, ...shotOps, ...linkUpserts, ...storyboardWrites]
}
