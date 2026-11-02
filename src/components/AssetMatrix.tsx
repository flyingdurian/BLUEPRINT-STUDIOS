import { ArrowUpRight, Box, GripVertical, Layers, Link2, Plus, RefreshCw, ScanFace, Shapes, Volume2 } from 'lucide-react'
import { useState, type DragEvent } from 'react'
import { useStudioStore } from '../store/useStudioStore'
import type { Asset, AssetStatus } from '../types/studio'
import { ASSET_DRAG_TYPE, isAssetDrag, isFileDrag } from './assetDrag'
import { AssetFilePicker, AssetUploader } from './AssetUploader'
import { AssetVersionPanel } from './AssetVersionPanel'

const stages: AssetStatus[] = ['Concept', '3D Modeling', 'Rigging', 'Tested & Ready']
const icons = { rig: ScanFace, environment: Layers, prop: Box, graphic: Shapes, audio: Volume2 }

function AssetCard({ asset }: { asset: Asset }) {
  const selected = useStudioStore(state => state.selectedAssetId === asset.id)
  const activeShot = useStudioStore(state => state.selectedShotId)
  const allLinks = useStudioStore(state => state.links)
  const links = allLinks.filter(link => link.assetId === asset.id)
  const usedInActive = links.some(link => link.shotId === activeShot)
  const shotCodes = useStudioStore(state => state.shots)
  const selectAsset = useStudioStore(state => state.selectAsset)
  const selectShot = useStudioStore(state => state.selectShot)
  const bump = useStudioStore(state => state.bumpAssetVersion)
  const Ico = icons[asset.category]
  const behind = links.filter(link => link.pinnedVersion < asset.currentVersion).length

  function onDragStart(event: DragEvent<HTMLElement>) {
    event.dataTransfer.setData(ASSET_DRAG_TYPE, asset.id)
    event.dataTransfer.setData('text/plain', asset.id)
    event.dataTransfer.effectAllowed = 'move'
  }

  return <AssetUploader assetId={asset.id}>
    <article className={`asset-card ${selected ? 'asset-selected' : ''} ${usedInActive ? 'used-in-active' : ''}`} draggable onDragStart={onDragStart} onClick={() => selectAsset(asset.id)} data-testid={`asset-${asset.id}`}>
      <div className="asset-card-top"><span className="asset-symbol" style={{ color: asset.color, background: `${asset.color}1f` }}><Ico size={18}/></span><span className="asset-version">v{asset.currentVersion}.0</span><GripVertical size={14} className="grip"/></div>
      <h4>{asset.name}</h4>
      <div className="asset-card-meta">{asset.category.toUpperCase()} <span>·</span> {links.length} SHOTS LINKED</div>
      {usedInActive && <span className="asset-in-shot">IN ACTIVE SHOT</span>}
      {behind > 0 && <span className="asset-review-count">{behind} {behind === 1 ? 'SHOT' : 'SHOTS'} TO REVIEW</span>}
      {selected && <div className="asset-card-detail">
        <div className="asset-refs"><Link2 size={11}/> {links.length ? 'USED IN' : 'NO LINKED SHOTS'}</div>
        <div className="asset-ref-list">{links.map(link => <button key={link.shotId} type="button" title={`Go to ${shotCodes[link.shotId]?.code}`} onMouseDown={event => event.preventDefault()} onClick={event => { event.stopPropagation(); selectShot(link.shotId) }}>{shotCodes[link.shotId]?.code}</button>)}</div>
        <div className="asset-publish-row">
          <AssetFilePicker assetId={asset.id}/>
          <button className="publish-version" type="button" onMouseDown={event => event.preventDefault()} onClick={event => { event.stopPropagation(); bump(asset.id) }}><Plus size={12}/> Publish next version</button>
        </div>
        <AssetVersionPanel assetId={asset.id}/>
      </div>}
    </article>
  </AssetUploader>
}

export function AssetMatrix() {
  const assets = useStudioStore(state => state.assets)
  const selectShot = useStudioStore(state => state.selectShot)
  const selected = useStudioStore(state => state.selectedShotId)
  const setStatus = useStudioStore(state => state.setAssetStatus)
  const review = useStudioStore(state => state.versionReview)
  const shots = useStudioStore(state => state.shots)
  const dismissReview = useStudioStore(state => state.dismissVersionReview)
  const [dragTarget, setDragTarget] = useState<AssetStatus | null>(null)
  const arr = Object.values(assets)

  function onColumnDragOver(status: AssetStatus, event: DragEvent<HTMLElement>) {
    if (isFileDrag(event.dataTransfer.types)) {
      event.preventDefault()
      return
    }
    if (!isAssetDrag(event.dataTransfer.types)) return
    event.preventDefault()
    setDragTarget(status)
  }
  function onColumnDrop(status: AssetStatus, event: DragEvent<HTMLElement>) {
    event.preventDefault()
    setDragTarget(null)
    if (isFileDrag(event.dataTransfer.types)) return
    const id = event.dataTransfer.getData(ASSET_DRAG_TYPE) || event.dataTransfer.getData('text/plain')
    if (assets[id]) setStatus(id, status)
  }

  return <div className="asset-matrix">
    <div className="asset-matrix-head"><div><strong>Production Assets</strong><span>Drop a media file on a card to publish a version. Drag cards between stages to update status.</span></div><div className="asset-total"><Box size={13}/> {arr.length} ASSETS</div></div>
    {review && <div className="asset-review-banner" role="status">
      <RefreshCw size={13}/>
      <span>{review.assetName} v{review.version} is ready. {review.shotIds.length} linked {review.shotIds.length === 1 ? 'shot still uses' : 'shots still use'} the pinned version.</span>
      <div>{review.shotIds.map(shotId => <button key={shotId} type="button" onMouseDown={event => event.preventDefault()} onClick={() => selectShot(shotId)}>{shots[shotId]?.code ?? shotId}</button>)}</div>
      <button type="button" onMouseDown={event => event.preventDefault()} onClick={dismissReview}>Dismiss</button>
    </div>}
    <div className="kanban-board">
      {stages.map(status => {
        const items = arr.filter(asset => asset.status === status)
        return <section key={status} className={`kanban-column ${dragTarget === status ? 'drag-over' : ''}`} onDragOver={event => onColumnDragOver(status, event)} onDragLeave={() => setDragTarget(null)} onDrop={event => onColumnDrop(status, event)}>
          <header><span className={`column-marker col-${stages.indexOf(status)}`}/><h3>{status}</h3><span className="kanban-count">{items.length}</span></header>
          <div className="kanban-column-list">{items.map(asset => <AssetCard key={asset.id} asset={asset}/>)}</div>
          <div className="kanban-column-foot">{status === 'Tested & Ready' ? 'READY FOR PRODUCTION' : 'DROP ASSETS HERE'}</div>
        </section>
      })}
    </div>
    <div className="asset-link-footer"><RefreshCw size={14}/><span>Version updates flag all linked shots. Existing shot links stay pinned until adopted.</span><button type="button" onMouseDown={event => event.preventDefault()} onClick={() => { selectShot(selected) }} title="Return focus to active shot"><ArrowUpRight size={13}/></button></div>
  </div>
}
