import { useEffect, useRef, useState } from 'react'
import type { Location } from './location.ts'
import PlaceSearch from './PlaceSearch.tsx'

type Props = {
  location: Location | null
  /** True while the first location is still being resolved. */
  locating: boolean
  onChoose: (location: Location) => void
}

/** The header pill showing the current location, opening a place search. */
function LocationControl({ location, locating, onChoose }: Props) {
  const [open, setOpen] = useState(false)
  const control = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function closeOnOutsidePress(event: PointerEvent) {
      if (!control.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', closeOnOutsidePress)
    return () => document.removeEventListener('pointerdown', closeOnOutsidePress)
  }, [open])

  const pillText = location
    ? `📍 ${location.label ?? 'Your location'} ▾`
    : locating
      ? '📍 Locating…'
      : '📍 Set location'

  return (
    <div
      className="location-control"
      ref={control}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpen(false)
      }}
    >
      <button
        type="button"
        className="location-pill"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {pillText}
      </button>
      {open && (
        <div className="location-dropdown">
          <PlaceSearch
            autoFocus
            onChoose={(chosen) => {
              setOpen(false)
              onChoose(chosen)
            }}
          />
        </div>
      )}
    </div>
  )
}

export default LocationControl
