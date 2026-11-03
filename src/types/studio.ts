export type AssetCategory = 'rig' | 'environment' | 'prop' | 'graphic' | 'audio'
export type AssetStatus = 'Concept' | '3D Modeling' | 'Rigging' | 'Tested & Ready'
export type StageTab = 'storyboard' | 'assets' | 'render'
export type CropMode = 'both' | '9:16' | '16:9'
export type SyncStatus = 'connecting' | 'synced' | 'offline' | 'pending' | 'conflict' | 'local'
export type WorkspaceView = 'director' | 'agents' | 'calendar'
export interface Shot {
  id: string  // immutable relation key, never re-ordered or recycled
  code: string // stable human-readable code, e.g. SH_001
  startFrame: number
  durationFrames: number
  visual: string
  narration: string
  notes: string
  artKey: string
  mood: string
}
export interface Asset {
  id: string
  name: string
  category: AssetCategory
  status: AssetStatus
  currentVersion: number
  color: string
  shorthand: string
}
export interface AssetLink {
  shotId: string
  assetId: string
  pinnedVersion: number
}
export interface StoryboardRecord {
  id: string
  projectId: string
  shotId: string
  cropMode: CropMode
  mediaPath: string | null
  assetId: string | null
  assetVersion: number | null
  sortIndex: number
  notes: string
}
export interface StoryboardDraft {
  id?: string
  shotId: string
  cropMode?: CropMode
  mediaPath?: string | null
  assetId?: string | null
  assetVersion?: number | null
  sortIndex?: number
  notes?: string
}
export interface AssetVersionRecord {
  version: number
  sha256: string | null
  relativePath: string | null
  description: string
  source: string
  byteSize?: number
  mediaType?: string
}
export interface AssetUploadState {
  fileName: string
  loaded: number
  total: number
  status: 'uploading' | 'error' | 'done'
  message?: string
  sha256?: string
  version?: number
}
export interface VersionReviewNotice {
  assetId: string
  assetName: string
  version: number
  shotIds: string[]
}
export interface ProductionData {
  shots: Record<string, Shot>
  shotOrder: string[]
  assets: Record<string, Asset>
  links: AssetLink[]
  nextShotNumber: number
}
export interface UIState {
  syncStatus: SyncStatus
  syncMessage: string
  selectedShotId: string
  selectedAssetId: string | null
  stageTab: StageTab
  cropMode: CropMode
  workspaceView: WorkspaceView
  playheadFrame: number
  zoom: number
}
export interface StudioActions {
  setSyncStatus: (status: SyncStatus, message: string) => void
  selectShot: (id: string) => void
  selectAsset: (id: string | null) => void
  setStageTab: (tab: StageTab) => void
  setCropMode: (mode: CropMode) => void
  setWorkspaceView: (mode: WorkspaceView) => void
  setPlayheadFrame: (frame: number) => void
  setZoom: (zoom: number) => void
  updateShot: (id: string, field: 'visual' | 'narration' | 'notes', value: string) => void
  addShot: () => void
  linkAsset: (shotId: string, assetId: string) => void
  unlinkAsset: (shotId: string, assetId: string) => void
  setAssetStatus: (id: string, status: AssetStatus) => void
  bumpAssetVersion: (id: string) => void
  adoptAssetVersion: (shotId: string, assetId: string) => void
  upsertStoryboard: (draft: StoryboardDraft) => void
  removeStoryboard: (id: string) => void
  beginUpload: (assetId: string, fileName: string, total: number) => void
  setUploadProgress: (assetId: string, loaded: number, total: number) => void
  failUpload: (assetId: string, message: string) => void
  clearUpload: (assetId: string) => void
  replaceAssetVersions: (assetId: string, versions: AssetVersionRecord[]) => void
  recordVerifiedUpload: (assetId: string, version: AssetVersionRecord) => void
  dismissVersionReview: () => void
  resetPilot: () => void
}
export type StudioState = ProductionData & UIState & StudioActions & {
  storyboards: StoryboardRecord[]
  uploads: Record<string, AssetUploadState>
  assetVersions: Record<string, AssetVersionRecord[]>
  versionReview: VersionReviewNotice | null
}
