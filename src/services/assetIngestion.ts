import { useStudioStore } from '../store/useStudioStore'
import { persistenceBridge } from '../sync/bridge'
import { MediaUploadError, uploadAssetFile, type UploadedAssetVersion } from './mediaClient'

const aborters = new Map<string, () => void>()

export function cancelAssetUpload(assetId: string): void {
  aborters.get(assetId)?.()
}

/** Stream one file to the asset. The server hash is the fingerprint that gets stored. */
export async function uploadAssetMedia(assetId: string, file: File): Promise<UploadedAssetVersion | null> {
  const store = useStudioStore.getState()
  if (!store.assets[assetId] || store.uploads[assetId]?.status === 'uploading') return null
  store.beginUpload(assetId, file.name, file.size)
  try {
    const revision = await persistenceBridge.readyRevision()
    const task = uploadAssetFile({
      assetId, file, expectedRevision: revision, description: file.name,
      onProgress: progress => useStudioStore.getState().setUploadProgress(assetId, progress.loaded, progress.total),
    })
    aborters.set(assetId, task.abort)
    const result = await task.promise
    persistenceBridge.acceptUploadedVersion(assetId, result.version, result.revision)
    useStudioStore.getState().recordVerifiedUpload(assetId, {
      version: result.version, sha256: result.sha256, relativePath: result.relativePath,
      description: result.description, source: result.source, byteSize: result.byteSize, mediaType: result.mediaType,
    })
    return result
  } catch (error) {
    if (error instanceof MediaUploadError && error.cancelled) useStudioStore.getState().clearUpload(assetId)
    else useStudioStore.getState().failUpload(assetId, error instanceof Error ? error.message : 'Upload failed')
    return null
  } finally {
    aborters.delete(assetId)
  }
}
