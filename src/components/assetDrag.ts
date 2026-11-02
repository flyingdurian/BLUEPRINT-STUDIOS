export const ASSET_DRAG_TYPE = 'application/x-blueprint-asset'

export function dragTypes(types: ArrayLike<string> | Iterable<string>): string[] {
  return Array.from(types)
}

export function isFileDrag(types: ArrayLike<string> | Iterable<string>): boolean {
  return dragTypes(types).includes('Files')
}

export function isAssetDrag(types: ArrayLike<string> | Iterable<string>): boolean {
  const listed = dragTypes(types)
  return listed.includes(ASSET_DRAG_TYPE) || (!listed.includes('Files') && listed.includes('text/plain'))
}
