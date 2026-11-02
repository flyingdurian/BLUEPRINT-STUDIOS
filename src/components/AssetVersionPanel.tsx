import { useEffect } from 'react'
import { apiClient, type AssetVersion } from '../services/apiClient'
import { useStudioStore } from '../store/useStudioStore'
import type { AssetVersionRecord } from '../types/studio'

const emptyVersions: AssetVersionRecord[] = []

function asRecord(version: AssetVersion): AssetVersionRecord {
  return {
    version: version.version, sha256: version.sha256, relativePath: version.relativePath,
    description: version.description, source: version.source,
  }
}

export function AssetVersionPanel({ assetId }: { assetId: string }) {
  const stored = useStudioStore(state => state.assetVersions?.[assetId])
  const versions = stored ?? emptyVersions
  const latest = versions[versions.length - 1]

  useEffect(() => {
    let cancelled = false
    void apiClient.listAssetVersions(assetId).then(rows => {
      if (!cancelled) useStudioStore.getState().replaceAssetVersions(assetId, rows.map(asRecord))
    }).catch(() => { /* History stays on the last verified upload when the API is offline. */ })
    return () => { cancelled = true }
  }, [assetId])

  return <div className="asset-version-panel" data-panel="stable-versions">
    <div className="asset-version-heading">Version history</div>
    {latest?.sha256 ? <p className="asset-fingerprint" title={latest.sha256}>Verified SHA-256 {latest.sha256}</p> : <p className="asset-fingerprint muted-fingerprint">No verified file yet. Drop media on this card.</p>}
    <ol>
      {versions.map(version => <li key={version.version}>
        <strong>v{version.version}</strong>
        <span>{version.source}</span>
        <span>{version.sha256 ? `${version.sha256.slice(0, 12)}…` : version.description || 'metadata only'}</span>
      </li>)}
    </ol>
  </div>
}
