import { useEffect,useMemo,useRef } from 'react'
import type { MouseEvent } from 'react'
import { ChevronLeft, ChevronRight, Clock3, Film, Layers, Minus, Plus, SlidersHorizontal, Volume2 } from 'lucide-react'
import { useStudioStore } from '../store/useStudioStore'
import { timecode } from '../utils/time'

const baseScale=9 // pixels per second at 1x, enough detail for 83s in a scrollable editor.
export function Timeline(){
  const order=useStudioStore(s=>s.shotOrder)
  const shots=useStudioStore(s=>s.shots)
  const selected=useStudioStore(s=>s.selectedShotId)
  const selectedAsset=useStudioStore(s=>s.selectedAssetId)
  const links=useStudioStore(s=>s.links)
  const relatedIds=selectedAsset ? new Set(links.filter(l=>l.assetId===selectedAsset).map(l=>l.shotId)) : new Set<string>()
  const selectShot=useStudioStore(s=>s.selectShot)
  const playhead=useStudioStore(s=>s.playheadFrame)
  const setPlayhead=useStudioStore(s=>s.setPlayheadFrame)
  const zoom=useStudioStore(s=>s.zoom)
  const setZoom=useStudioStore(s=>s.setZoom)
  const container=useRef<HTMLDivElement>(null)
  const endFrame=useMemo(()=>order.reduce((m,id)=>Math.max(m,shots[id].startFrame+shots[id].durationFrames),0),[shots,order])
  const pixelsPerFrame=baseScale/30*zoom
  const width=Math.max(950,endFrame*pixelsPerFrame+60)
  const selectedShot=shots[selected]
  const ticks=useMemo(()=>Array.from({length:Math.ceil(endFrame/150)+1},(_,i)=>i*150).filter(f=>f<=endFrame),[endFrame])
  useEffect(()=>{if(!container.current||!selectedShot)return;const x=selectedShot.startFrame*pixelsPerFrame;const el=container.current;if(x<el.scrollLeft+90||x>el.scrollLeft+el.clientWidth-150)el.scrollTo({left:Math.max(0,x-el.clientWidth/3),behavior:'smooth'})},[selected,pixelsPerFrame,selectedShot])
  function jump(e:MouseEvent<HTMLDivElement>){const rect=e.currentTarget.getBoundingClientRect();const frame=Math.round((e.clientX-rect.left)/pixelsPerFrame);setPlayhead(frame)}
  const count=order.length
  return <section className="timeline-pane" aria-label="Unified production timeline">
    <div className="timeline-header"><div className="timeline-title"><span className="pane-icon violet"><Layers size={16}/></span><div><h2>Unified Timeline</h2><p>Frame-accurate shot linking</p></div><span className="timeline-tag">{count} SHOTS</span></div>
      <div className="timeline-actions"><span className="fps-pill"><Clock3 size={12}/> 30 FPS</span><span className="time-counter" data-testid="playhead-time">{timecode(playhead,true)} <small>/ {timecode(endFrame,true)}</small></span><span className="timeline-divider"/><button type="button" title="Previous shot" aria-label="Previous shot" onClick={()=>{const i=order.indexOf(selected);selectShot(order[Math.max(0,i-1)])}}><ChevronLeft size={17}/></button><button type="button" title="Next shot" aria-label="Next shot" onClick={()=>{const i=order.indexOf(selected);selectShot(order[Math.min(order.length-1,i+1)])}}><ChevronRight size={17}/></button><span className="timeline-divider"/><SlidersHorizontal size={15} className="zoom-icon"/><button type="button" title="Zoom out" aria-label="Zoom out" onClick={()=>setZoom(zoom-.25)}><Minus size={15}/></button><span className="zoom-label">{Math.round(zoom*100)}%</span><button type="button" title="Zoom in" aria-label="Zoom in" onClick={()=>setZoom(zoom+.25)}><Plus size={15}/></button></div>
    </div>
    <div className="timeline-main"><div className="timeline-track-labels"><div className="track-label ruler-label">TRACKS</div><div className="track-label script-track"><span className="track-icon"><Layers size={14}/></span><span>SCRIPT CUES</span></div><div className="track-label video-track"><span className="track-icon"><Film size={14}/></span><span>STORYBOARD</span></div><div className="track-label audio-track"><span className="track-icon"><Volume2 size={14}/></span><span>VOICE / AUDIO</span></div></div>
      <div className="timeline-scroll" ref={container}><div className="timeline-content" style={{width}}>
        <div className="timeline-ruler" onClick={jump} role="presentation">{ticks.map(frame=><div key={frame} className="ruler-tick" style={{left:frame*pixelsPerFrame}}><span>{timecode(frame)}</span></div>)}</div>
        <div className="timeline-lane lane-script" onClick={jump}>{order.map(id=>{const s=shots[id];return <button type="button" key={id} data-testid={`timeline-${s.code}`} onClick={e=>{e.stopPropagation();selectShot(id)}} title={`${s.code}: ${s.notes}`} className={`timeline-clip script ${id===selected?'selected':''} ${relatedIds.has(id)?'related':''}`}  style={{left:s.startFrame*pixelsPerFrame,width:Math.max(3,s.durationFrames*pixelsPerFrame-2)}}><span>{s.code}</span></button>})}</div>
        <div className="timeline-lane lane-video" onClick={jump}>{order.map(id=>{const s=shots[id];return <button type="button" key={id} onClick={e=>{e.stopPropagation();selectShot(id)}} title={s.visual} className={`timeline-clip video ${id===selected?'selected':''} ${relatedIds.has(id)?'related':''}`}  style={{left:s.startFrame*pixelsPerFrame,width:Math.max(3,s.durationFrames*pixelsPerFrame-2)}}><span>{s.notes}</span></button>})}</div>
        <div className="timeline-lane lane-audio" onClick={jump}><div className="voice-placeholder" style={{width:endFrame*pixelsPerFrame}}><div className="waveform-faux">{Array.from({length:175},(_,i)=><i key={i} style={{height:`${7+(Math.abs(Math.sin(i*2.11))*15)+(Math.abs(Math.sin(i*.57))*13)}px`}}/>)}</div><span className="audio-placeholder-text"><Volume2 size={12}/> Narrator VO · scratch track placeholder</span></div></div>
        <div className="playhead" style={{left:playhead*pixelsPerFrame}}><span/></div>
      </div></div>
    </div>
    <div className="timeline-footer"><span><span className="footer-dot orange"/> Script</span><span><span className="footer-dot cyan"/> Visual</span><span><span className="footer-dot purple"/> Audio placeholder</span><div className="timeline-footer-right">CLICK CLIPS TO SYNC <span>•</span> SCROLL TO SCRUB THE WORKSPACE</div></div>
  </section>
}
