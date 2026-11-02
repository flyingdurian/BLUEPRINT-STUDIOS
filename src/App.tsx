import { useState } from 'react'
import { Activity, ArrowLeft, ArrowRight, CalendarDays, ChevronDown, CircleHelp, Clapperboard, Command, Film, FolderOpen, Layers3, LayoutDashboard, Monitor, PanelTop, Settings2, Sparkles, WandSparkles } from 'lucide-react'
import { Screenplay } from './components/Screenplay'
import { VisualStage } from './components/VisualStage'
import { Timeline } from './components/Timeline'
import { useStudioStore } from './store/useStudioStore'
import { persistenceBridge } from './sync/bridge'
import { timecode } from './utils/time'
function App() {
  const syncStatus=useStudioStore(s=>s.syncStatus)
  const syncMessage=useStudioStore(s=>s.syncMessage)
  const view=useStudioStore(s=>s.workspaceView)
  const setView=useStudioStore(s=>s.setWorkspaceView)
  const setTab=useStudioStore(s=>s.setStageTab)
  const selectedId=useStudioStore(s=>s.selectedShotId)
  const selectedShot=useStudioStore(s=>s.shots[s.selectedShotId])
  const shots=useStudioStore(s=>s.shotOrder)
  const select=useStudioStore(s=>s.selectShot)
  const [help,setHelp]=useState(false)
  const index=shots.indexOf(selectedId)
  return <div className="app-shell">
    <aside className="app-sidebar" aria-label="Navigation"><div className="side-logo"><span className="logo-symbol"><Clapperboard size={23} strokeWidth={2.1}/></span></div><div className="side-nav">
      <button className={view==='director'?'active':''} onClick={()=>setView('director')} aria-label="Director Canvas" title="Director Canvas"><LayoutDashboard size={19}/></button>
      <button aria-label="Asset Matrix" title="Asset Matrix" onClick={()=>{setView('director');setTab('assets')}}><Layers3 size={19}/></button>
      <button disabled aria-label="Agent Hub planned for BS-M4" title="Agent Hub • Milestone 4"><WandSparkles size={19}/></button>
      <button disabled aria-label="Calendar planned for BS-M4" title="Publishing Calendar • Milestone 4"><CalendarDays size={19}/></button>
    </div><div className="sidebar-bottom"><button onClick={()=>setHelp(true)} title="Keyboard & workflow tips" aria-label="Help"><CircleHelp size={19}/></button><div className="side-avatar" title="Local single-user workspace">BS</div></div></aside>
    <div className="app-body">
      <header className="topbar"><div className="brand-area"><div className="brand-lockup"><span>BLUEPRINT</span><strong>STUDIOS</strong></div><span className="brand-divider"/><span className="brand-subtitle">DIRECTOR OS <span className="beta-label">BETA 0.1</span></span></div>
        <div className="header-center"><span className="project-prefix"><FolderOpen size={14}/> ACTIVE PRODUCTION</span><span className="header-project">Congratulations, You're the Organizer</span><ChevronDown size={14}/></div>
        <div className="header-right"><span className={`local-status sync-${syncStatus}`} role="status" aria-live="polite" title={syncMessage}><i/> {syncStatus === "synced" ? "SQLITE SAVED" : syncStatus === "offline" ? "OFFLINE · LOCAL DRAFT" : syncStatus === "conflict" ? "SYNC NEEDS REVIEW" : syncStatus === "pending" ? "SAVING…" : "CONNECTING…"}</span>{(syncStatus === "offline" || syncStatus === "conflict") && <button className="sync-action" onClick={()=>void persistenceBridge.connect()}>Retry sync</button>}{syncStatus === "conflict" && <button className="sync-action" title="Discard local browser changes and load the SQLite snapshot" onClick={()=>{if(window.confirm("Discard local browser edits and load the SQLite project? This cannot be undone.")) void persistenceBridge.useServerCopy().catch(()=>useStudioStore.getState().setSyncStatus("offline","Cannot fetch SQLite project"))}}>Use server copy</button>}<button className="header-utility" aria-label="Help" title="Workflow tips" onClick={()=>setHelp(true)}><CircleHelp size={17}/></button><button className="header-utility" title="Preferences planned for next milestone" disabled><Settings2 size={17}/></button></div>
      </header>
      <div className="contextbar"><div className="crumbs"><span>WORKSPACE</span><ArrowRight size={12}/><strong>Director Canvas</strong><span className="context-sep"/><span className="breadcrumb-episode">PILOT 01 <span>·</span> PRODUCTION FOUNDATION</span></div><div className="context-actions"><span className="context-stats"><Film size={13}/> {shots.length} SHOTS</span><span className="context-stats"><Activity size={13}/> {timecode(shots.reduce((v,id)=>Math.max(v,useStudioStore.getState().shots[id].startFrame+useStudioStore.getState().shots[id].durationFrames),0))} DURATION</span><span className="context-chip">BS-M1</span></div></div>
      <main className="director-workspace"><div className="worktop"><Screenplay/><VisualStage/></div><Timeline/></main>
      <footer className="statusbar"><div><span className="status-ready"><i/> SYSTEM READY</span><span className="status-sep"/> <Monitor size={12}/> LOCAL-FIRST BUILD <span className="status-sep"/> <PanelTop size={12}/> 3 PANES LINKED</div><div className="footer-right-status"><span>SELECTED: <strong data-testid="selected-code">{selectedShot?.code??'—'}</strong></span><div className="footer-nav"><button aria-label="Previous shot" disabled={index===0} onClick={()=>select(shots[index-1])}><ArrowLeft size={12}/></button><button aria-label="Next shot" disabled={index>=shots.length-1} onClick={()=>select(shots[index+1])}><ArrowRight size={12}/></button></div><span>{syncStatus === "synced" ? "SQLITE PERSISTED" : "BROWSER DRAFT"}</span></div></footer>
    </div>
    {help && <div className="modal-scrim" onMouseDown={()=>setHelp(false)}><div className="help-modal" onMouseDown={e=>e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Workspace help"><div className="help-modal-head"><Sparkles size={18}/> Workflow tips <button onClick={()=>setHelp(false)}>×</button></div><p>This is a runnable Milestone 1 foundation. The screenplay, storyboard and timeline all share one Zustand store.</p><ul><li>Click a shot in the screenplay, gallery or timeline to synchronize its selection.</li><li>Type <code>@</code> in either screenplay column, then pick an asset to insert a tag and link it.</li><li>Open the Asset Matrix; drag cards across workflow columns, or drop a media file on a card to publish a hashed version.</li><li>Outdated linked shot assets show an orange warning until you adopt the new version.</li><li>All edits and relationship updates are saved locally in this browser.</li></ul><p className="help-note">Dropped media is hashed by the local API. Linked shots keep their pinned version until you adopt the new one. The timeline audio is illustrative only.</p><button className="help-done" onClick={()=>setHelp(false)}>Got it <Command size={14}/></button></div></div>}
  </div>
}
export default App
