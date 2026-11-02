import { useState, type DragEvent, type ReactNode } from 'react'
import { Upload, X } from 'lucide-react'
import { isFileDrag } from './assetDrag'
import { cancelAssetUpload, uploadAssetMedia } from '../services/assetIngestion'
import { MEDIA_ACCEPT } from '../services/mediaClient'
import { useStudioStore } from '../store/useStudioStore'

function keepTypingFocus(event: { preventDefault(): void }): void {
  event.preventDefault()
}

export function AssetFilePicker({ assetId }: { assetId: string }) {
  return <label className="asset-upload-button" onMouseDown={keepTypingFocus} onClick={event => event.stopPropagation()}>
    <Upload size={12}/> Upload file
    <input type="file" accept={MEDIA_ACCEPT} aria-label={`Upload a file for ${assetId}`} onClick={event => event.stopPropagation()} onChange={event => {
      const file = event.currentTarget.files?.[0]
      event.currentTarget.value = ''
      if (file) void uploadAssetMedia(assetId, file)
    }}/>
  </label>
}

export function AssetUploader({ assetId, children }: { assetId: string; children: ReactNode }) {
  const upload = useStudioStore(state => state.uploads?.[assetId])
  const [fileOver, setFileOver] = useState(false)
  const fraction = upload && upload.total > 0 ? Math.min(1, upload.loaded / upload.total) : 0

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    if (!isFileDrag(event.dataTransfer.types)) return
    event.preventDefault()
    event.stopPropagation()
    event.dataTransfer.dropEffect = 'copy'
    setFileOver(true)
  }
  function onDragLeave(event: DragEvent<HTMLDivElement>) {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
    setFileOver(false)
  }
  function onDrop(event: DragEvent<HTMLDivElement>) {
    if (!isFileDrag(event.dataTransfer.types)) return
    event.preventDefault()
    event.stopPropagation()
    setFileOver(false)
    const file = event.dataTransfer.files[0]
    if (!file) return
    void uploadAssetMedia(assetId, file)
  }

  return <div className={`asset-drop-shell ${fileOver ? 'file-over' : ''}`} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
    {children}
    {fileOver && <div className="asset-drop-hint">Drop to publish a new version</div>}
    {upload?.status === 'uploading' && <div className="asset-upload-progress" aria-live="polite">
      <div className="asset-upload-bar"><span style={{ width: `${Math.round(fraction * 100)}%` }}/></div>
      <span>{upload.fileName} · {Math.round(fraction * 100)}%</span>
      <button type="button" aria-label={`Cancel upload for ${upload.fileName}`} onMouseDown={keepTypingFocus} onClick={event => { event.stopPropagation(); cancelAssetUpload(assetId) }}><X size={12}/></button>
    </div>}
    {upload?.status === 'error' && <p className="asset-upload-error" role="alert">{upload.message}</p>}
    {upload?.status === 'done' && upload.sha256 && <p className="asset-fingerprint" title={upload.sha256}>SHA-256 {upload.sha256.slice(0, 12)}…{upload.sha256.slice(-6)}</p>}
  </div>
}
