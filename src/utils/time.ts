export const FPS = 30
export const TOTAL_FRAMES_SEED = 83 * FPS
export function timecode(frame: number, withFrames = false): string {
  const n = Math.max(0, Math.floor(frame))
  const s = Math.floor(n / FPS)
  const base = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  return withFrames ? `${base}:${String(n % FPS).padStart(2,'0')}` : base
}
export const shotEnd = (startFrame: number, durationFrames: number) => startFrame + durationFrames
export function durationLabel(durationFrames: number) {
  const s = durationFrames / FPS
  return Number.isInteger(s) ? `${s}s` : `${s.toFixed(1)}s`
}
