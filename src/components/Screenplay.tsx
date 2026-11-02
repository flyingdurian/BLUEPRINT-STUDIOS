import { useEffect,useRef } from 'react'
import { ChevronDown, FilePenLine, Link2, Plus, RotateCcw, Sparkles, Unlink, AlertCircle } from 'lucide-react'
import { useStudioStore } from '../store/useStudioStore'
import { durationLabel,timecode } from '../utils/time'
import { TagEditor } from './TagEditor'

function ShotBlock({id}:{id:string}) {
  const shot=useStudioStore(s=>s.shots[id])
  const active=useStudioStore(s=>s.selectedShotId===id)
  const select=useStudioStore(s=>s.selectShot)
  const allLinks=useStudioStore(s=>s.links)
  const links=allLinks.filter(l=>l.shotId===id)
  const assets=useStudioStore(s=>s.assets)
  const selectedAssetId=useStudioStore(s=>s.selectedAssetId)
  const related=!!selectedAssetId && links.some(l=>l.assetId===selectedAssetId)
  const unlink=useStudioStore(s=>s.unlinkAsset)
  const adopt=useStudioStore(s=>s.adoptAssetVersion)
  const card=useRef<HTMLElement>(null)
  useEffect(()=>{
    if(active && card.current && !card.current.contains(document.activeElement)) card.current.scrollIntoView({block:'nearest',behavior:'smooth'})
  },[active])
  const outdated=links.filter(l=>l.pinnedVersion < (assets[l.assetId]?.currentVersion??0))
  return <article ref={card} data-testid={`shot-block-${shot.code}`} className={`shot-block ${active?'shot-selected':''} ${related?'asset-related':''}`} onMouseDown={()=>{if(!active)select(id)}}>
    <div className="shot-block-top">
      <div className="shot-marker"><span className="shot-marker-dot"/><strong>{shot.code}</strong><span className="shot-time">{timecode(shot.startFrame)} – {timecode(shot.startFrame+shot.durationFrames)}</span></div>
      <div className="shot-block-icons">{outdated.length>0 && <span className="update-flag" title="One or more linked assets have newer versions"><AlertCircle size={12}/> UPDATE AVAILABLE</span>}<span className="shot-duration">{durationLabel(shot.durationFrames)}</span></div>
    </div>
    <div className="shot-edit-grid">
      <div className="shot-edit-cell"><span className="field-heading">VISUAL / ACTION</span><TagEditor shotId={id} field="visual" value={shot.visual} placeholder="Visual action... use @ for assets"/></div>
      <div className="shot-edit-cell dialogue-cell"><span className="field-heading">NARRATION / DIALOGUE</span><TagEditor shotId={id} field="narration" value={shot.narration} placeholder="What does the audience hear?"/></div>
    </div>
    {active && <div className="shot-chip-row"><span className="linked-caption"><Link2 size={12}/> ASSETS</span>
      {links.map(link=>{const a=assets[link.assetId];if(!a)return null;const old=link.pinnedVersion<a.currentVersion;return <span key={a.id} className={`linked-chip ${old?'outdated':''}`} title={old?`Linked v${link.pinnedVersion}, latest v${a.currentVersion}`:`Pinned to v${link.pinnedVersion}`}>
        <i style={{background:a.color}}/><span>{a.name}</span>{old && <button title={`Adopt v${a.currentVersion}`} aria-label={`Update ${a.name} link to version ${a.currentVersion}`} onMouseDown={e=>e.preventDefault()} onClick={()=>adopt(id,a.id)}>↑v{a.currentVersion}</button>}
        <button className="unlink-btn" title={`Unlink ${a.name}`} aria-label={`Unlink ${a.name}`} onMouseDown={e=>e.preventDefault()} onClick={()=>unlink(id,a.id)}><Unlink size={10}/></button>
      </span>})}
      <span className="chip-hint">type @ to link</span>
    </div>}
  </article>
}

export function Screenplay() {
  const order=useStudioStore(s=>s.shotOrder)
  const addShot=useStudioStore(s=>s.addShot)
  const reset=useStudioStore(s=>s.resetPilot)
  return <section className="pane screenplay-pane" aria-label="Living screenplay">
    <div className="pane-header screenplay-heading">
      <div className="pane-heading-left"><span className="pane-icon amber"><FilePenLine size={16}/></span><div><h2>Living Screenplay</h2><p>Script & visual direction</p></div></div>
      <button className="icon-button" type="button" title="Reset to the original 14-shot pilot" aria-label="Reset project to original pilot" onClick={()=>{if(window.confirm('Reset edits and links to the original 14-shot pilot?'))reset()}}><RotateCcw size={15}/></button>
    </div>
    <div className="screenplay-toolbar"><div className="screenplay-tab active"><span className="tiny-indicator"/> SHOT BLOCKS <span className="count-bubble">{order.length}</span></div><span className="auto-save"><span/> LOCAL AUTOSAVE</span></div>
    <div className="field-columns"><span>VISUAL DIRECTION</span><span>DIALOGUE / VOICEOVER</span></div>
    <div className="screenplay-list" data-testid="screenplay-list">
      {order.map(id=><ShotBlock key={id} id={id}/>)}
      <button type="button" className="add-shot" onClick={addShot}><Plus size={16}/> Add new shot block <span>+ timeline placeholder</span></button>
      <div className="screenplay-footer"><Sparkles size={14}/> Use <kbd>@</kbd> in either script column to link assets to a shot. <ChevronDown size={13}/></div>
    </div>
  </section>
}
