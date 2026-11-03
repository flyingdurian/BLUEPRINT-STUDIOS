import { useEffect, useState } from 'react'
import { Captions, Clapperboard, Download, RefreshCw } from 'lucide-react'
import { assembleRender, fetchActiveRender, mediaUrl, type RenderJobStatus } from '../services/renderClient'

const AUDIO_LABEL = {
  missing: 'NO NARRATION',
  partial: 'PARTIAL AUDIO',
  ready: 'READY TO MIX',
  aligned: 'AUDIO ALIGNED',
} as const

function clock(seconds: number): string {
  const total = Math.max(0, Math.round(seconds * 1000))
  const minutes = Math.floor(total / 60000)
  const remainder = total % 60000
  const secs = Math.floor(remainder / 1000)
  const millis = remainder % 1000
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(millis).padStart(3, '0')}`
}

export function RenderInspector() {
  const [job, setJob] = useState<RenderJobStatus | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [assembling, setAssembling] = useState(false)
  const [captionsOn, setCaptionsOn] = useState(true)

  async function refresh() {
    setLoading(true)
    setError('')
    try {
      setJob(await fetchActiveRender())
    } catch (caught) {
      setJob(null)
      setError(caught instanceof Error ? caught.message : 'Render status is unavailable')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])

  async function assemble() {
    if (!job) return
    setAssembling(true)
    setError('')
    try {
      setJob(await assembleRender(job.jobId, true))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Assembly failed')
    } finally {
      setAssembling(false)
    }
  }

  const canAssemble = !!job && (job.audioStatus === 'ready' || job.audioStatus === 'aligned') && !assembling
  const preview = mediaUrl(job?.previewUrl ?? null)
  const download = mediaUrl(job?.downloadUrl ?? null)
  const captions = mediaUrl(job?.captionsUrl ?? null)

  return <div className="render-inspector" data-testid="render-inspector">
    <div className="render-inspector-head">
      <div>
        <span className="render-kicker"><Clapperboard size={14}/> M4-D ASSEMBLY</span>
        <h3>{job?.productionLocked ? 'Distribution master' : 'Previs assembly'}</h3>
        <p>{job ? `${job.shotCount} shots · ${job.frameCount} frames · ${job.durationSeconds.toFixed(3)}s` : 'Waiting for a frozen render manifest.'}</p>
      </div>
      <button type="button" className="toolbar-small" onClick={() => void refresh()} disabled={loading || assembling}><RefreshCw size={14}/> Refresh</button>
    </div>

    {error && <p className="render-error" role="alert">{error}</p>}

    <div className="render-status-row">
      <span data-testid="audio-status" className={`render-pill audio-${job?.audioStatus ?? 'missing'}`}>{job ? AUDIO_LABEL[job.audioStatus] : 'NO JOB'} · {job ? `${job.tracksPresent}/${job.tracksExpected}` : '0/0'} WAV</span>
      <span className="render-pill">{job?.silentVideoReady ? 'SILENT OGV READY' : 'NO SILENT MOVIE'}</span>
      <span className="render-pill">{job?.mixReady ? 'MIX LOCKED' : 'MIX NOT BUILT'}</span>
    </div>

    <div className="render-controls">
      <button type="button" className={`render-toggle ${captionsOn ? 'active' : ''}`} data-testid="subtitle-toggle" aria-pressed={captionsOn} onClick={() => setCaptionsOn(value => !value)}>
        <Captions size={15}/> Captions {captionsOn ? 'on' : 'off'}
      </button>
      <button type="button" data-testid="render-assemble" disabled={!canAssemble} onClick={() => void assemble()}>{assembling ? 'Assembling…' : 'Assemble MP4'}</button>
      {download ? <a className="render-download" data-testid="render-download" href={download}>Download MP4 <Download size={14}/></a> : <button type="button" data-testid="render-download" disabled>Download MP4</button>}
    </div>

    {preview ? <video key={preview} className="render-preview" data-testid="render-preview" controls crossOrigin="anonymous" src={preview}>
      {captionsOn && captions && <track kind="subtitles" src={captions} srcLang="en" label="Narration" default/>}
    </video> : <div className="render-preview-empty" data-testid="render-preview">Preview appears after the silent movie and all 14 narration WAVs are assembled.</div>}

    <p className="render-note">Each shot reads <code>narration/SH_###.wav</code> from the active job and starts on that shot's frame. The preview leaves captions toggleable. The download burns them into the H.264 file. This remains a previs assembly while the manifest is unlocked.</p>

    {captionsOn && <ol className="render-cues">
      {(job?.shots ?? []).map(shot => <li key={shot.code}>
        <span>{shot.code}</span>
        <span>{clock(shot.startSeconds)}</span>
        <span className={shot.wavPresent ? 'ready' : 'missing'}>{shot.wavPresent ? 'WAV' : 'NO WAV'}</span>
        <p>{shot.narration}</p>
      </li>)}
    </ol>}
  </div>
}
