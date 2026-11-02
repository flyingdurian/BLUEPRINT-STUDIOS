import { describe, expect, it, vi } from 'vitest'
import { isAssetDrag, isFileDrag } from '../components/assetDrag'
import { MediaUploadError, uploadAssetFile, type UploadTransport } from '../services/mediaClient'

class FakeTransport implements UploadTransport {
  method = ''
  url = ''
  headers: Record<string, string> = {}
  body: FormData | null = null
  status = 0
  responseText = ''
  upload = { onprogress: null as UploadTransport['upload']['onprogress'] }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  open(method: string, url: string) { this.method = method; this.url = url }
  setRequestHeader(name: string, value: string) { this.headers[name] = value }
  send(body: FormData) { this.body = body }
  abort() { this.onabort?.() }
}

const digest = 'ab'.repeat(32)

function file(type = 'image/png', contents = 'png-bytes', name = 'frame.png'): File {
  return new File([contents], name, { type })
}

describe('media upload client', () => {
  it('posts multipart bytes and reports progress without trusting a client hash', async () => {
    const transport = new FakeTransport()
    const onProgress = vi.fn()
    const task = uploadAssetFile({
      file: file(), assetId: 'ast-mug', expectedRevision: 4, baseUrl: 'http://127.0.0.1:8000',
      idempotencyKey: 'upload-001', onProgress,
    }, () => transport)
    expect(transport.method).toBe('POST')
    expect(transport.url).toBe('http://127.0.0.1:8000/api/projects/blueprint-pilot-01/assets/ast-mug/versions/upload')
    expect(transport.headers['Idempotency-Key']).toBe('upload-001')
    expect(transport.body?.get('expectedRevision')).toBe('4')
    expect(transport.body?.get('file')).toBeInstanceOf(Blob)
    transport.upload.onprogress?.({ lengthComputable: true, loaded: 4, total: 9 })
    expect(onProgress).toHaveBeenCalledWith({ loaded: 4, total: 9 })
    transport.status = 201
    transport.responseText = JSON.stringify({
      assetId: 'ast-mug', version: 3, sha256: digest, relativePath: `ab/cd/${digest}`,
      description: 'frame.png', source: 'upload', byteSize: 9, mediaType: 'image/png', revision: 5,
    })
    transport.onload?.()
    await expect(task.promise).resolves.toMatchObject({ sha256: digest, revision: 5, version: 3 })
  })

  it('cancels the request and rejects unsupported types before sending', async () => {
    const transport = new FakeTransport()
    const task = uploadAssetFile({ file: file(), assetId: 'ast-mug', expectedRevision: 1, baseUrl: 'http://127.0.0.1:8000' }, () => transport)
    task.abort()
    await expect(task.promise).rejects.toMatchObject({ cancelled: true, name: 'MediaUploadError' } satisfies Partial<MediaUploadError>)
    const rejected = new FakeTransport()
    const bad = uploadAssetFile({ file: file('text/html', '<html>', 'page.html'), assetId: 'ast-mug', expectedRevision: 1, baseUrl: 'http://127.0.0.1:8000' }, () => rejected)
    await expect(bad.promise).rejects.toMatchObject({ status: 415 })
    expect(rejected.body).toBeNull()
  })

  it('keeps a file drop distinct from an asset-card drag', () => {
    expect(isFileDrag(['Files', 'text/plain'])).toBe(true)
    expect(isAssetDrag(['Files', 'text/plain'])).toBe(false)
    expect(isAssetDrag(['application/x-blueprint-asset', 'text/plain'])).toBe(true)
    expect(isFileDrag(['application/x-blueprint-asset', 'text/plain'])).toBe(false)
  })
})
