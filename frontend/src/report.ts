import type { Location } from './location.ts'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export type SignificantEvent = {
  event_type: 'conjunction' | 'opposition' | 'meteor_shower'
  peak_time: string
  related_object_names: string[] | null
}

/** A Visible body and its positional fields: one entry of `visible_objects`. */
export type SkyObject = {
  id: string
  name: string
  peak_altitude_degrees: number
  azimuth_at_peak_degrees: number
  /** Null when the body never set before its peak, so it doesn't rise tonight. */
  rises_at: string | null
  /** Null when the body stays up after its peak, so it doesn't set tonight. */
  sets_at: string | null
  magnitude: number | null
  event: SignificantEvent | null
}

export type Highlight = SkyObject & {
  mini_headline: string
  paragraph: string
}

export type ViewingWindow = {
  starts_at: string
  ends_at: string
}

export type CosmicReport = {
  headline: string
  viewing_window: ViewingWindow
  highlights: Highlight[]
  visible_objects: SkyObject[]
}

function localDate(now: Date): string {
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Request tonight's Cosmic Report for a location, on the local date. */
export async function fetchReport(location: Location): Promise<CosmicReport> {
  const response = await fetch(`${API_BASE_URL}/api/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      latitude: location.latitude,
      longitude: location.longitude,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      date: localDate(new Date()),
      location_label: location.label,
    }),
  })
  if (!response.ok) {
    throw new Error(`Report request failed with status ${response.status}`)
  }
  return response.json()
}
