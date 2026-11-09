import type { Highlight } from './HighlightList.tsx'
import type { Location } from './location.ts'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export type CosmicReport = {
  headline: string
  highlights: Highlight[]
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
