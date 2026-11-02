import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { createPilot } from '../data/pilot'
import { FPS, TOTAL_FRAMES_SEED } from '../utils/time'

const pilot = createPilot()

describe('83-second Pilot 1 seed', () => {
  it('has 14 unique, consecutive shots ending at frame 2490', () => {
    expect(pilot.shotOrder).toHaveLength(14)
    expect(new Set(pilot.shotOrder).size).toBe(14)
    let end = 0
    for (const id of pilot.shotOrder) {
      const shot = pilot.shots[id]
      expect(shot.startFrame).toBe(end)
      expect(shot.durationFrames).toBeGreaterThan(0)
      end = shot.startFrame + shot.durationFrames
    }
    expect(end).toBe(TOTAL_FRAMES_SEED)
    expect(end / FPS).toBe(83)
  })
  it('keeps every asset link referentially valid', () => {
    for (const link of pilot.links) {
      expect(pilot.shots[link.shotId]).toBeDefined()
      expect(pilot.assets[link.assetId]).toBeDefined()
      expect(link.pinnedVersion).toBe(pilot.assets[link.assetId].currentVersion)
    }
  })
})

// Zustand is loaded after localStorage is available. This makes these tests run
// without a browser and exercises the same mutations used by the UI.
describe('Tri-Link Zustand actions', () => {
  let store: typeof import('../store/useStudioStore')['useStudioStore']
  beforeAll(async () => {
    const data = new Map<string,string>()
    Object.defineProperty(globalThis, 'localStorage', { configurable:true, value:{
      getItem:(key:string)=>data.get(key)??null,
      setItem:(key:string,value:string)=>{data.set(key,value)},
      removeItem:(key:string)=>{data.delete(key)},
      clear:()=>data.clear(),
    }})
    store=(await import('../store/useStudioStore')).useStudioStore
  })
  beforeEach(()=>store.getState().resetPilot())
  it('selecting a shot updates active shot and playhead in one operation', () => {
    store.getState().selectShot('shot-009')
    expect(store.getState().selectedShotId).toBe('shot-009')
    expect(store.getState().playheadFrame).toBe(46*FPS)
  })
  it('links assets once and flags old pinned versions until adopted', () => {
    const s=store.getState()
    s.linkAsset('shot-001','ast-mug')
    s.linkAsset('shot-001','ast-mug')
    expect(store.getState().links.filter(l=>l.shotId==='shot-001'&&l.assetId==='ast-mug')).toHaveLength(1)
    s.bumpAssetVersion('ast-mug')
    const old=store.getState().links.find(l=>l.shotId==='shot-001'&&l.assetId==='ast-mug')!
    expect(old.pinnedVersion).toBeLessThan(store.getState().assets['ast-mug'].currentVersion)
    s.adoptAssetVersion('shot-001','ast-mug')
    const updated=store.getState().links.find(l=>l.shotId==='shot-001'&&l.assetId==='ast-mug')!
    expect(updated.pinnedVersion).toBe(store.getState().assets['ast-mug'].currentVersion)
  })
  it('renaming a script field preserves shot identity and links', () => {
    const oldLinks=store.getState().links.filter(l=>l.shotId==='shot-005')
    store.getState().updateShot('shot-005','narration','A revised test line')
    expect(store.getState().shots['shot-005'].narration).toBe('A revised test line')
    expect(store.getState().links.filter(l=>l.shotId==='shot-005')).toEqual(oldLinks)
  })
  it('upserts one storyboard record and can remove it', () => {
    store.getState().upsertStoryboard({ id: 'board-1', shotId: 'shot-001', notes: 'First' })
    store.getState().upsertStoryboard({ id: 'board-1', shotId: 'shot-001', notes: 'Second' })
    expect(store.getState().storyboards).toHaveLength(1)
    expect(store.getState().storyboards[0].notes).toBe('Second')
    expect(store.getState().storyboards[0].shotId).toBe('shot-001')
    store.getState().removeStoryboard('board-1')
    expect(store.getState().storyboards).toEqual([])
  })
  it('records a verified upload without moving pins, status, or the selected shot', () => {
    const before = store.getState()
    const shotId = before.selectedShotId
    const status = before.assets['ast-mug'].status
    const pins = before.links.filter(link => link.assetId === 'ast-mug').map(link => link.pinnedVersion)
    store.getState().recordVerifiedUpload('ast-mug', {
      version: before.assets['ast-mug'].currentVersion + 1,
      sha256: 'ab'.repeat(32), relativePath: 'ab/cd/' + 'ab'.repeat(32),
      description: 'sample.png', source: 'upload', byteSize: 12, mediaType: 'image/png',
    })
    const after = store.getState()
    expect(after.selectedShotId).toBe(shotId)
    expect(after.assets['ast-mug'].status).toBe(status)
    expect(after.assets['ast-mug'].currentVersion).toBe(before.assets['ast-mug'].currentVersion)
    expect(after.links.filter(link => link.assetId === 'ast-mug').map(link => link.pinnedVersion)).toEqual(pins)
    expect(after.uploads['ast-mug'].sha256).toBe('ab'.repeat(32))
    expect(after.versionReview?.assetId).toBe('ast-mug')
    expect(after.versionReview?.shotIds.length).toBeGreaterThan(0)
  })
  it('adding a shot does not change existing permanent IDs', () => {
    const before=[...store.getState().shotOrder]
    store.getState().addShot()
    expect(store.getState().shotOrder.slice(0,14)).toEqual(before)
    expect(store.getState().shotOrder).toHaveLength(15)
    expect(store.getState().shots[store.getState().selectedShotId].code).toBe('SH_015')
  })
})
