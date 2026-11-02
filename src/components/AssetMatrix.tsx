import { ArrowUpRight, Box, GripVertical, Layers, Link2, Plus, RefreshCw, ScanFace, Shapes, Volume2 } from 'lucide-react'
import { useState } from 'react'
import { useStudioStore } from '../store/useStudioStore'
import type {Asset,AssetStatus} from '../types/studio'
const stages:AssetStatus[]=['Concept','3D Modeling','Rigging','Tested & Ready']
const icons={rig:ScanFace,environment:Layers,prop:Box,graphic:Shapes,audio:Volume2}

function AssetCard({asset}:{asset:Asset}) {
  const selected=useStudioStore(s=>s.selectedAssetId===asset.id)
  const activeShot=useStudioStore(s=>s.selectedShotId)
  const allLinks=useStudioStore(s=>s.links)
  const links=allLinks.filter(l=>l.assetId===asset.id)
  const usedInActive=links.some(l=>l.shotId===activeShot)
  const shotCodes=useStudioStore(s=>s.shots)
  const selectAsset=useStudioStore(s=>s.selectAsset)
  const selectShot=useStudioStore(s=>s.selectShot)
  const bump=useStudioStore(s=>s.bumpAssetVersion)
  const Ico=icons[asset.category]
  return <article className={`asset-card ${selected?'asset-selected':''} ${usedInActive?'used-in-active':''}`} draggable onDragStart={e=>e.dataTransfer.setData('text/plain',asset.id)} onClick={()=>selectAsset(asset.id)} data-testid={`asset-${asset.id}`}>
    <div className="asset-card-top"><span className="asset-symbol" style={{color:asset.color,background:`${asset.color}1f`}}><Ico size={18}/></span><span className="asset-version">v{asset.currentVersion}.0</span><GripVertical size={14} className="grip"/></div>
    <h4>{asset.name}</h4><div className="asset-card-meta">{asset.category.toUpperCase()} <span>·</span> {links.length} SHOTS LINKED</div>{usedInActive && <span className="asset-in-shot">IN ACTIVE SHOT</span>}
    {selected && <div className="asset-card-detail"><div className="asset-refs"><Link2 size={11}/> {links.length? 'USED IN':'NO LINKED SHOTS'}</div>
      <div className="asset-ref-list">{links.map(l=><button key={l.shotId} title={`Go to ${shotCodes[l.shotId]?.code}`} onClick={e=>{e.stopPropagation();selectShot(l.shotId)}}>{shotCodes[l.shotId]?.code}</button>)}</div>
      <button className="publish-version" onClick={e=>{e.stopPropagation();bump(asset.id)}}><Plus size={12}/> Publish next version</button>
    </div>}
  </article>
}

export function AssetMatrix() {
  const assets=useStudioStore(s=>s.assets)
  const selectShot=useStudioStore(s=>s.selectShot)
  const selected=useStudioStore(s=>s.selectedShotId)
  const setStatus=useStudioStore(s=>s.setAssetStatus)
  const [dragTarget,setDragTarget]=useState<AssetStatus | null>(null)
  const arr=Object.values(assets)
  return <div className="asset-matrix">
    <div className="asset-matrix-head"><div><strong>Production Assets</strong><span>Drag cards between stages to update status.</span></div><div className="asset-total"><Box size={13}/> {arr.length} ASSETS</div></div>
    <div className="kanban-board">
      {stages.map(status=>{const items=arr.filter(a=>a.status===status);return <section key={status} className={`kanban-column ${dragTarget===status?'drag-over':''}`} onDragOver={e=>{e.preventDefault();setDragTarget(status)}} onDragLeave={()=>setDragTarget(null)} onDrop={e=>{e.preventDefault();const id=e.dataTransfer.getData('text/plain');if(assets[id])setStatus(id,status);setDragTarget(null)}}>
        <header><span className={`column-marker col-${stages.indexOf(status)}`}/><h3>{status}</h3><span className="kanban-count">{items.length}</span></header>
        <div className="kanban-column-list">{items.map(a=><AssetCard key={a.id} asset={a}/>)}</div>
        <div className="kanban-column-foot">{status==='Tested & Ready'?'READY FOR PRODUCTION':'DROP ASSETS HERE'}</div>
      </section>})}
    </div>
    <div className="asset-link-footer"><RefreshCw size={14}/><span>Version updates flag all linked shots. Existing shot links stay pinned until adopted.</span><button onClick={()=>{selectShot(selected)}} title="Return focus to active shot"><ArrowUpRight size={13}/></button></div>
  </div>
}
