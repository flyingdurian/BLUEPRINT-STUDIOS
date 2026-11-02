import type { ProductionData, Asset, Shot } from '../types/studio'

export function productionGraph(state: ProductionData): ProductionData {
  return {
    shots: Object.fromEntries(Object.entries(state.shots).map(([key, shot]) => [key, { ...shot }])),
    shotOrder: [...state.shotOrder],
    assets: Object.fromEntries(Object.entries(state.assets).map(([key, asset]) => [key, { ...asset }])),
    links: state.links.map(link => ({ ...link })),
    nextShotNumber: state.nextShotNumber,
  }
}

// SQL SELECT order is not guaranteed, so compare sorted normalized maps / links.
function stable(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stable)
  if (value !== null && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    return Object.fromEntries(Object.keys(obj).sort().map(key => [key, stable(obj[key])]))
  }
  return value
}

export function fingerprint(graph: ProductionData): string {
  const sorted = <T>(values: Record<string, T>) => Object.fromEntries(Object.entries(values).sort(([a], [b]) => a.localeCompare(b)))
  return JSON.stringify(stable({
    shots: sorted(graph.shots), shotOrder: graph.shotOrder,
    assets: sorted(graph.assets),
    links: [...graph.links].sort((a, b) => `${a.shotId}:${a.assetId}`.localeCompare(`${b.shotId}:${b.assetId}`)),
    nextShotNumber: graph.nextShotNumber,
  }))
}

export function shotsChanged(a: ProductionData, b: ProductionData): boolean {
  return JSON.stringify(a.shotOrder) !== JSON.stringify(b.shotOrder)
    || a.nextShotNumber !== b.nextShotNumber
    || JSON.stringify(stable(a.shots)) !== JSON.stringify(stable(b.shots))
}

export function assetMetadataChanged(a: Asset, b: Asset): boolean {
  return a.name !== b.name || a.status !== b.status || a.color !== b.color || a.shorthand !== b.shorthand
}

export function shotChanges(old: Shot, current: Shot): Partial<Shot> {
  const patch: Partial<Shot> = {}
  for (const key of ['visual', 'narration', 'notes', 'startFrame', 'durationFrames', 'artKey', 'mood'] as const) {
    if (old[key] !== current[key]) Object.assign(patch, { [key]: current[key] })
  }
  return patch
}
