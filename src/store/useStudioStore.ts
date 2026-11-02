import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { createPilot } from '../data/pilot'
import type { StudioState, AssetStatus, CropMode, StageTab, WorkspaceView, Shot, SyncStatus } from '../types/studio'

const defaultUI = {
  selectedShotId: 'shot-001', selectedAssetId: null, stageTab:'storyboard' as StageTab,
  cropMode:'both' as CropMode, workspaceView:'director' as WorkspaceView,
  playheadFrame:0, zoom:1, syncStatus:'local' as SyncStatus, syncMessage:'Browser state available',
}

export const useStudioStore = create<StudioState>()(
  persist(
    (set) => ({
      ...createPilot(), ...defaultUI,
      setSyncStatus: (status, message) => set({ syncStatus:status, syncMessage:message }),
      selectShot: id => set(state => state.shots[id] ? { selectedShotId:id, playheadFrame:state.shots[id].startFrame, selectedAssetId:null } : {}),
      selectAsset: id => set(state => !id || state.assets[id] ? { selectedAssetId:id, stageTab:'assets' } : {}),
      setStageTab: tab => set({stageTab:tab}),
      setCropMode: mode => set({cropMode:mode}),
      setWorkspaceView: mode => set({workspaceView:mode}),
      setPlayheadFrame: frame => set(state => {
        const limit = state.shotOrder.reduce((m,id) => Math.max(m,state.shots[id].startFrame + state.shots[id].durationFrames),0)
        const next = Math.max(0,Math.min(limit,Math.floor(frame)))
        const hit = state.shotOrder.find(id => next >= state.shots[id].startFrame && next < state.shots[id].startFrame + state.shots[id].durationFrames)
        return {playheadFrame:next,...(hit ? {selectedShotId:hit,selectedAssetId:null} : {})}
      }),
      setZoom: zoom => set({zoom: Math.max(.65,Math.min(2.4, zoom))}),
      updateShot: (id,field,value) => set(state => {
        if (!state.shots[id]) return {}
        return {shots:{...state.shots,[id]:{...state.shots[id],[field]:value}}}
      }),
      addShot: () => set(state => {
        const n = state.nextShotNumber
        const code = `SH_${String(n).padStart(3,'0')}`
        const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `shot-${n}-${Date.now()}`
        const endFrame = state.shotOrder.reduce((m,sid) => Math.max(m,state.shots[sid].startFrame+state.shots[sid].durationFrames),0)
        const shot:Shot = { id, code, startFrame:endFrame,durationFrames:120,visual:'Describe the action. Type @ to link an asset.',narration:'New narration beat...',notes:'New shot',artKey:'new',mood:'neutral' }
        return {shots:{...state.shots,[id]:shot},shotOrder:[...state.shotOrder,id],nextShotNumber:n+1,selectedShotId:id,playheadFrame:endFrame}
      }),
      linkAsset: (shotId,assetId) => set(state => {
        if (!state.shots[shotId] || !state.assets[assetId] || state.links.some(l => l.shotId===shotId && l.assetId===assetId)) return {}
        return {links:[...state.links,{shotId,assetId,pinnedVersion:state.assets[assetId].currentVersion}]}
      }),
      unlinkAsset: (shotId,assetId) => set(state => ({links:state.links.filter(l=>l.shotId!==shotId || l.assetId!==assetId)})),
      setAssetStatus: (id,status:AssetStatus) => set(state => state.assets[id] ? {assets:{...state.assets,[id]:{...state.assets[id],status}}} : {}),
      bumpAssetVersion: id => set(state => state.assets[id] ? {assets:{...state.assets,[id]:{...state.assets[id],currentVersion:state.assets[id].currentVersion+1}}} : {}),
      adoptAssetVersion: (shotId,assetId) => set(state => state.assets[assetId] ? {links:state.links.map(l => l.shotId===shotId && l.assetId===assetId ? {...l,pinnedVersion:state.assets[assetId].currentVersion} : l)} : {}),
      resetPilot: () => set({...createPilot(),...defaultUI}),
    }),
    {
      name:'blueprint-studios-bs-m1-v1',
      version:1,
      storage:createJSONStorage(() => localStorage),
      partialize: state => ({
        shots:state.shots,shotOrder:state.shotOrder,assets:state.assets,links:state.links,nextShotNumber:state.nextShotNumber,
        selectedShotId:state.selectedShotId,selectedAssetId:state.selectedAssetId,stageTab:state.stageTab,
        cropMode:state.cropMode,workspaceView:state.workspaceView,playheadFrame:state.playheadFrame,zoom:state.zoom,
      }),
    },
  ),
)
