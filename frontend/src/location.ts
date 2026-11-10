/** A point on Earth to report on, with the label shown in the header pill. */
export type Location = {
  latitude: number
  longitude: number
  /** Human-readable place name, or null when none could be found. */
  label: string | null
}

const STORAGE_KEY = 'starcast.location'

/** The last location whose report succeeded, if any. */
export function loadSavedLocation(): Location | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    return isLocation(parsed) ? parsed : null
  } catch {
    return null
  }
}

/** Remember a location. Call only after its report succeeds. */
export function saveLocation(location: Location): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(location))
  } catch {
    // Storage can be full or blocked; the app still works without it.
  }
}

/** Forget the saved location, once the backend has rejected it. */
export function clearSavedLocation(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Blocked storage has nothing saved to forget.
  }
}

function isLocation(value: unknown): value is Location {
  if (typeof value !== 'object' || value === null) return false
  const { latitude, longitude, label } = value as Record<string, unknown>
  return (
    typeof latitude === 'number' &&
    typeof longitude === 'number' &&
    (typeof label === 'string' || label === null)
  )
}
