// Client-side geocoding through OpenStreetMap's Nominatim. The backend never
// sees a place name; only the chosen coordinates and label leave the browser.
// Usage policy: https://operations.osmfoundation.org/policies/nominatim/
// (at most one request per second, so search runs on submit, never per keystroke).

import type { Location } from './location.ts'

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org'
const TIMEOUT_MS = 8000

type NominatimPlace = { name?: string; display_name: string }

/** A search result: the location to report on plus its full address. */
export type PlaceMatch = Location & { label: string; description: string }

async function fetchNominatim(path: string, params: Record<string, string>) {
  const url = `${NOMINATIM_URL}/${path}?${new URLSearchParams({ format: 'jsonv2', ...params })}`
  const response = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS) })
  if (!response.ok) {
    throw new Error(`Nominatim ${path} failed with status ${response.status}`)
  }
  return response.json()
}

function shortName(place: NominatimPlace): string {
  return place.name || place.display_name.split(',')[0]
}

/** Places matching a free-text query, best match first. */
export async function searchPlaces(query: string): Promise<PlaceMatch[]> {
  const places: (NominatimPlace & { lat: string; lon: string })[] =
    await fetchNominatim('search', { q: query, limit: '5' })
  return places.map((place) => ({
    latitude: Number(place.lat),
    longitude: Number(place.lon),
    label: shortName(place),
    description: place.display_name,
  }))
}

/** A town-level name for coordinates, or null when none can be found. */
export async function placeName(
  latitude: number,
  longitude: number,
): Promise<string | null> {
  try {
    // Nominatim answers 200 with { error } when it has no place there.
    const place: NominatimPlace | { error: string } = await fetchNominatim(
      'reverse',
      { lat: String(latitude), lon: String(longitude), zoom: '10' },
    )
    return 'display_name' in place ? shortName(place) : null
  } catch (error) {
    console.error(error)
    return null
  }
}
