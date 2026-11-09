import { useState, type FormEvent } from 'react'
import { searchPlaces, type PlaceMatch } from './nominatim.ts'
import type { Location } from './location.ts'

type SearchState =
  | { status: 'idle' }
  | { status: 'searching' }
  | { status: 'found'; query: string; matches: PlaceMatch[] }
  | { status: 'failed' }

type Props = {
  onChoose: (location: Location) => void
  autoFocus?: boolean
}

/** A place-name search box. Searches only on submit, never automatically. */
function PlaceSearch({ onChoose, autoFocus = false }: Props) {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState<SearchState>({ status: 'idle' })

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return
    setSearch({ status: 'searching' })
    try {
      const matches = await searchPlaces(trimmed)
      setSearch({ status: 'found', query: trimmed, matches })
    } catch (error) {
      // A timeout lands here too. No automatic retry: the query stays in the
      // box, so resubmitting is one keypress.
      console.error(error)
      setSearch({ status: 'failed' })
    }
  }

  return (
    <div className="place-search">
      <form role="search" onSubmit={submit}>
        <input
          type="search"
          aria-label="Search for a place"
          placeholder="Search for a place"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoFocus={autoFocus}
        />
      </form>
      {search.status === 'searching' && (
        <p className="place-search-message">Searching…</p>
      )}
      {search.status === 'failed' && (
        <p className="place-search-message">Couldn't reach place search</p>
      )}
      {search.status === 'found' && search.matches.length === 0 && (
        <p className="place-search-message">
          No places match '{search.query}'
        </p>
      )}
      {search.status === 'found' && search.matches.length > 0 && (
        <ul className="place-search-results">
          {search.matches.map((match) => (
            <li key={`${match.latitude},${match.longitude}`}>
              <button
                type="button"
                onClick={() =>
                  onChoose({
                    latitude: match.latitude,
                    longitude: match.longitude,
                    label: match.label,
                  })
                }
              >
                {match.description}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default PlaceSearch
