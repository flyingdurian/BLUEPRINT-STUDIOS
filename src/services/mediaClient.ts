import { PROJECT_ID } from './apiClient'

const defaultApiBase = 'http://127.0.0.1:8000'

export const ALLOWED_MEDIA_TYPES = [
  'image/png', 'image/jpeg', 'image/webp', 'image/gif',
  'video/mp4', 'video/webm', 'video/quicktime',
  'audio/wav', 'audio/mpeg', 'audio/ogg', 'audio/flac', 'audio/webm',
  'model/gltf+json', 'model/gltf-binary',
] as const

const TYPE_ALIASES: Record<string, string> = {
  'audio/mp3': 'audio/mpeg',
  'audio/x-wav': 'audio/wav',
  'audio/wave': 'audio/wav',
  'image/jpg': 'image/jpeg',
}

export const MEDIA_ACCEPT = [...ALLOWED_MEDIA_TYPES, ...Object.keys(TYPE_ALIASES)].join(',')

export class MediaUploadError extends Error {
  constructor(readonly status: number, message: string, readonly cancelled = false) {
    super(message)
    this.name = 'MediaUploadError'
  }
}

export interface UploadProgress {
  loaded: number
  total: number
}

export interface UploadedAssetVersion {
  assetId: string
  version: number
  sha256: string
  relativePath: string
  description: string
  source: string
  byteSize: number
  mediaType: string
  revision: number
}

export interface UploadProgressEvent {
  lengthComputable: boolean
  loaded: number
  total: number
}

export interface UploadTransport {
  open(method: string, url: string): void
  setRequestHeader(name: string, value: string): void
  send(body: FormData): void
  abort(): void
  upload: { onprogress: ((event: UploadProgressEvent) => void) | null }
  onload: (() => void) | null
  onerror: (() => void) | null
  onabort: (() => void) | null
  status: number
  responseText: string
}

export interface UploadAssetFileOptions {
  file: File
  assetId: string
  expectedRevision: number
  projectId?: string
  description?: string
  idempotencyKey?: string
  baseUrl?: string
  onProgress?: (progress: UploadProgress) => void
}

export interface UploadTask {
  promise: Promise<UploadedAssetVersion>
  abort: () => void
}

export function canonicalMediaType(type: string): string {
  const base = type.split(';', 1)[0].trim().toLowerCase()
  return TYPE_ALIASES[base] ?? base
}

export function uploadAssetFile(options: UploadAssetFileOptions, createTransport: () => UploadTransport = createXhr): UploadTask {
  const mediaType = canonicalMediaType(options.file.type)
  const transport = createTransport()
  const promise = new Promise<UploadedAssetVersion>((resolve, reject) => {
    if (options.file.size <= 0) {
      reject(new MediaUploadError(422, 'Upload is empty'))
      return
    }
    if (!ALLOWED_MEDIA_TYPES.includes(mediaType as typeof ALLOWED_MEDIA_TYPES[number])) {
      reject(new MediaUploadError(415, 'This file type cannot be stored'))
      return
    }
    transport.upload.onprogress = event => {
      if (event.lengthComputable) options.onProgress?.({ loaded: event.loaded, total: event.total })
    }
    transport.onload = () => {
      if (transport.status === 200 || transport.status === 201) {
        try { resolve(parseUploadedVersion(transport.responseText)) }
        catch (error) { reject(error) }
        return
      }
      reject(new MediaUploadError(transport.status, uploadErrorMessage(transport.status, transport.responseText)))
    }
    transport.onerror = () => reject(new MediaUploadError(0, 'Upload failed before the server responded'))
    transport.onabort = () => reject(new MediaUploadError(0, 'Upload cancelled', true))
    const projectId = options.projectId ?? PROJECT_ID
    const base = (options.baseUrl ?? import.meta.env.VITE_STUDIO_API_BASE_URL ?? defaultApiBase).replace(/\/$/, '')
    const url = `${base}/api/projects/${encodeURIComponent(projectId)}/assets/${encodeURIComponent(options.assetId)}/versions/upload`
    transport.open('POST', url)
    transport.setRequestHeader('Idempotency-Key', options.idempotencyKey ?? createIdempotencyKey())
    const body = new FormData()
    const payload = mediaType === options.file.type ? options.file : new Blob([options.file], { type: mediaType })
    body.append('file', payload, options.file.name)
    body.append('description', options.description ?? options.file.name)
    body.append('expectedRevision', String(options.expectedRevision))
    transport.send(body)
  })
  return { promise, abort: () => transport.abort() }
}

export function uploadErrorMessage(status: number, body: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown }
    const detail = parsed.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const message = (detail as { message?: unknown }).message
      if (typeof message === 'string' && message.trim()) return message
    }
  } catch { /* The status line below is the readable fallback. */ }
  if (status === 409) return 'The workspace revision changed; the file was not published'
  if (status === 413) return 'File exceeds the upload limit'
  if (status === 415) return 'This file type cannot be stored'
  if (status === 422) return 'The file was rejected'
  return `Upload failed (${status})`
}

function parseUploadedVersion(body: string): UploadedAssetVersion {
  const value = JSON.parse(body) as Partial<UploadedAssetVersion>
  if (!value.sha256 || !/^[a-f0-9]{64}$/.test(value.sha256) || !value.version || !value.relativePath || value.revision === undefined) {
    throw new MediaUploadError(0, 'Server response did not include a verified fingerprint')
  }
  return value as UploadedAssetVersion
}

function createIdempotencyKey(): string {
  const suffix = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}`
  return `upload-${suffix}`
}

function createXhr(): UploadTransport {
  return new XMLHttpRequest() as unknown as UploadTransport
}
