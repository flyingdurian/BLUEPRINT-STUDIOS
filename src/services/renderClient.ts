import { PROJECT_ID } from './apiClient'

const defaultApiBase = 'http://127.0.0.1:8000'

export interface RenderShotStatus {
  code: string
  shotId: string | null
  startFrame: number
  durationFrames: number
  startSeconds: number
  narration: string
  wavPresent: boolean
  sourceSeconds: number | null
}

export interface RenderJobStatus {
  jobId: string
  projectId: string
  revision: number
  quality: string
  productionLocked: boolean
  frameCount: number
  shotCount: number
  durationSeconds: number
  audioStatus: 'missing' | 'partial' | 'ready' | 'aligned'
  tracksPresent: number
  tracksExpected: number
  mixReady: boolean
  captionsReady: boolean
  silentVideoReady: boolean
  previewReady: boolean
  finalReady: boolean
  burnedCaptions: boolean
  shots: RenderShotStatus[]
  previewUrl: string | null
  downloadUrl: string | null
  captionsUrl: string | null
}

export class RenderRequestError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'RenderRequestError'
  }
}

function apiBase(): string {
  return (import.meta.env.VITE_STUDIO_API_BASE_URL || defaultApiBase).replace(/\/$/, '')
}

export function mediaUrl(path: string | null): string | null {
  if (!path) return null
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  return `${apiBase()}${path}`
}

async function request(path: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(`${apiBase()}${path}`, { ...init, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

async function parseStatus(response: Response): Promise<RenderJobStatus> {
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null
    const detail = typeof body?.detail === 'string' ? body.detail : `Render API ${response.status}`
    throw new RenderRequestError(detail)
  }
  return response.json() as Promise<RenderJobStatus>
}

export function fetchActiveRender(projectId = PROJECT_ID): Promise<RenderJobStatus> {
  return request(`/api/projects/${encodeURIComponent(projectId)}/renders/active`, {}, 8000).then(parseStatus)
}

export function assembleRender(jobId: string, burnCaptions = true, projectId = PROJECT_ID): Promise<RenderJobStatus> {
  return request(`/api/projects/${encodeURIComponent(projectId)}/renders/${encodeURIComponent(jobId)}/assemble`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ burnCaptions }),
  }, 300000).then(parseStatus)
}
