import { useEffect, useRef } from 'react'
import { Clapperboard, Film, Grid2X2, Image as ImageIcon, Layers3, Maximize2, MonitorPlay, Scan, SquareDashedMousePointer } from 'lucide-react'
import { useStudioStore } from '../store/useStudioStore'
import { timecode } from '../utils/time'
import { StoryboardArt } from './StoryboardArt'
import { AssetMatrix } from './AssetMatrix'
import { RenderInspector } from './RenderInspector'

function StoryboardGallery() {
  const selectedId=useStudioStore(s=>s.selectedShotId)
  const order=useStudioStore(s=>s.shotOrder)
  const shots=useStudioStore(s=>s.shots)
  const selectShot=useStudioStore(s=>s.selectShot)
  const crop=useStudioStore(s=>s.cropMode)
  const setCrop=useStudioStore(s=>s.setCropMode)
  const allLinks=useStudioStore(s=>s.links)
  const links=allLinks.filter(l=>l.shotId===selectedId)
  const assets=useStudioStore(s=>s.assets)
  const selected=shots[selectedId]
  const itemRef=useRef<Record<string,HTMLButtonElement | null>>({})
  useEffect(()=>{itemRef.current[selectedId]?.scrollIntoView({block:'nearest',inline:'nearest',behavior:'smooth'})},[selectedId])
  if(!selected) return null
  return <div className="stage-gallery">
    <div className="gallery-caption-row"><div className="status-caption"><span className="green-led"/> ACTIVE COMPOSITION <span className="gallery-shot-id">{selected.code}</span></div><div className="safe-controls"><Scan size={13}/><span>SAFE ZONES</span>{(['both','9:16','16:9'] as const).map(mode=><button key={mode} type="button" aria-pressed={crop===mode} onClick={()=>setCrop(mode)} className={crop===mode?'active':''}>{mode==='both'?'BOTH':mode}</button>)}</div></div>
    <div className={`hero-stage crop-${crop.replace(':','-')}`} data-testid="storyboard-active" aria-label={`Storyboard for ${selected.code}`}>
      <StoryboardArt shot={selected}/>
      {crop!=='9:16' && <div className="safe-169"><span>16:9 MASTER</span></div>}
      {crop!=='16:9' && <div className="safe-916"><span>9:16 SAFE FRAME</span><div className="safe-916-inner"/></div>}
      <div className="hero-stage-edge top-left"/><div className="hero-stage-edge top-right"/><div className="hero-stage-edge bottom-left"/><div className="hero-stage-edge bottom-right"/>
      <div className="stage-filmstrip"><span className="stage-badge"><Film size={12}/> STORYBOARD / CONCEPT</span><span className="stage-time">{timecode(selected.startFrame)}—{timecode(selected.startFrame+selected.durationFrames)}</span></div>
    </div>
    <div className="stage-notes"><div><span>DIRECTOR'S NOTE</span><p>{selected.notes}</p></div><span className="stage-state-tag"><SquareDashedMousePointer size={12}/> SHOT SELECTED</span></div>
    <div className="linked-stage-row"><span>SCENE ASSETS <b>{links.length}</b></span><div>{links.slice(0,5).map(link=><span key={link.assetId}><i style={{background:assets[link.assetId]?.color}}/>{assets[link.assetId]?.name}</span>)}{links.length>5 && <small>+{links.length-5}</small>}</div></div>
    <div className="gallery-bottom-header"><div><Grid2X2 size={15}/><strong>Storyboard Sequence</strong><span className="muted">{order.length} SHOTS</span></div><button title="Storyboard images are conceptual thumbnails; media ingest is planned for milestone 3" className="toolbar-small"><ImageIcon size={14}/> CONCEPT FRAMES</button></div>
    <div className="storyboard-strip" aria-label="Shot storyboard gallery">
      {order.map(id=>{const shot=shots[id];return <button type="button" key={id} ref={el=>{itemRef.current[id]=el}} data-testid={`gallery-${shot.code}`} onClick={()=>selectShot(id)} className={`storyboard-thumb ${id===selectedId?'selected':''}`} aria-pressed={id===selectedId}>
        <div className="thumb-art"><StoryboardArt shot={shot} compact/><span className="thumb-overlay">{shot.code}</span></div>
        <div className="thumb-meta"><span>{timecode(shot.startFrame)}</span><span>{shot.notes}</span></div>
      </button>})}
    </div>
  </div>
}
export function VisualStage() {
  const tab=useStudioStore(s=>s.stageTab)
  const setTab=useStudioStore(s=>s.setStageTab)
  const linkedCount=useStudioStore(s=>Object.keys(s.assets).length)
  return <section className="pane stage-pane" aria-label="Visual stage and asset matrix">
    <div className="pane-header stage-heading"><div className="pane-heading-left"><span className="pane-icon teal"><Clapperboard size={17}/></span><div><h2>Visual Stage</h2><p>Compositions & production assets</p></div></div><button title="Preview is representative, not final animation" className="icon-button"><Maximize2 size={15}/></button></div>
    <div className="stage-tabs"><button type="button" data-testid="tab-storyboard" className={tab==='storyboard'?'active':''} onClick={()=>setTab('storyboard')}><Film size={15}/> Spatial Storyboard</button><button type="button" data-testid="tab-assets" className={tab==='assets'?'active':''} onClick={()=>setTab('assets')}><Layers3 size={15}/> Asset Matrix <span>{linkedCount}</span></button><button type="button" data-testid="tab-render" className={tab==='render'?'active':''} onClick={()=>setTab('render')}><MonitorPlay size={15}/> Render</button></div>
    <div className="stage-content">{tab==='storyboard'?<StoryboardGallery/>:tab==='assets'?<AssetMatrix/>:<RenderInspector/>}</div>
  </section>
}
