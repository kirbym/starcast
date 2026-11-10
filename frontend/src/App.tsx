import { useEffect, useRef, useState } from 'react'
import { HighlightList } from './HighlightList.tsx'
import {
  clearSavedLocation,
  loadSavedLocation,
  saveLocation,
  type Location,
} from './location.ts'
import { placeName } from './nominatim.ts'
import LocationControl from './LocationControl.tsx'
import PlaceSearch from './PlaceSearch.tsx'
import {
  fetchReport,
  ReportError,
  type CosmicReport,
  type ReportErrorType,
  type SkyObject,
} from './report.ts'
import ReportSkeleton from './ReportSkeleton.tsx'
import Toast from './Toast.tsx'
import { VisibleObjects } from './VisibleObjects.tsx'

const GEOLOCATION_TIMEOUT_MS = 10_000
const UNANSWERED_PROMPT_MS = 15_000

type ReportState =
  | { status: 'locating' }
  | { status: 'needs-location' }
  | { status: 'loading' }
  | { status: 'ready'; report: CosmicReport }
  | { status: 'failed' }

/** The last location whose report succeeded, and that report: what a failure rolls back to. */
type LastGood = { location: Location; report: CosmicReport }

/** Only one toast shows at a time; a newer one replaces it, under a new id. */
type ToastState = { id: number; message: string }

function App() {
  const [location, setLocation] = useState<Location | null>(null)
  const [report, setReport] = useState<ReportState>({ status: 'locating' })
  const [toast, setToast] = useState<ToastState | null>(null)
  const lastGood = useRef<LastGood | null>(null)
  // Identifies the latest report request. A response for any older request is
  // dropped, so the newest location always wins.
  const latestRequest = useRef(0)

  function showToast(message: string) {
    setToast((previous) => ({ id: (previous?.id ?? 0) + 1, message }))
  }

  function reportFailed(target: Location, error: unknown) {
    const type: ReportErrorType =
      error instanceof ReportError ? error.type : 'internal_error'
    if (type === 'invalid_location') {
      clearSavedLocation()
      lastGood.current = null
      setLocation(null)
      setReport({ status: 'needs-location' })
      showToast("We couldn't use that location — pick another.")
      return
    }
    showToast(tryAgainMessage(type, target))
    if (lastGood.current) {
      setLocation(lastGood.current.location)
      setReport({ status: 'ready', report: lastGood.current.report })
    } else {
      // Nothing to roll back to: the pill keeps the attempted location, unsaved.
      setReport({ status: 'failed' })
    }
  }

  async function loadReport(target: Location) {
    const request = ++latestRequest.current
    setLocation(target)
    setReport({ status: 'loading' })
    try {
      const loaded = await fetchReport(target)
      if (request !== latestRequest.current) return
      saveLocation(target)
      lastGood.current = { location: target, report: loaded }
      setReport({ status: 'ready', report: loaded })
    } catch (error) {
      // The backend's message is for developers: logged, never shown.
      console.error(
        error instanceof ReportError
          ? `Report failed with ${error.statusCode} ${error.type}: ${error.message}`
          : error,
      )
      if (request === latestRequest.current) reportFailed(target, error)
    }
  }

  useEffect(() => {
    // StrictMode runs this effect twice. Only the surviving run may call the
    // API, because every report request is a paid Claude call.
    let stale = false
    let giveUp: ReturnType<typeof setTimeout> | undefined

    const saved = loadSavedLocation()
    if (saved) {
      // Defer one tick so the StrictMode cleanup can mark this run stale.
      queueMicrotask(() => {
        if (!stale) void loadReport(saved)
      })
    } else {
      // Geolocation only fills in a location while nothing else has: once a
      // place is chosen from the pill, a late answer must not override it.
      const nothingChosen = () => !stale && latestRequest.current === 0
      const askForLocation = () => {
        if (nothingChosen()) setReport({ status: 'needs-location' })
      }
      // The geolocation timeout excludes time spent on the permission prompt,
      // so an ignored prompt would otherwise leave the page locating forever.
      giveUp = setTimeout(askForLocation, UNANSWERED_PROMPT_MS)

      navigator.geolocation.getCurrentPosition(
        async ({ coords: { latitude, longitude } }) => {
          clearTimeout(giveUp)
          if (!nothingChosen()) return
          const label = await placeName(latitude, longitude)
          if (nothingChosen()) void loadReport({ latitude, longitude, label })
        },
        // Denied, unavailable and timed out all mean the same thing here:
        // ask, without scolding about permissions.
        () => {
          clearTimeout(giveUp)
          askForLocation()
        },
        { timeout: GEOLOCATION_TIMEOUT_MS },
      )
    }

    return () => {
      stale = true
      clearTimeout(giveUp)
    }
  }, [])

  return (
    <>
      <header>
        <LocationControl
          location={location}
          locating={report.status === 'locating'}
          onChoose={loadReport}
        />
      </header>
      <main>
        {report.status === 'needs-location' && (
          <section className="set-location" aria-labelledby="set-location-title">
            <h1 id="set-location-title">Where are you stargazing tonight?</h1>
            <PlaceSearch onChoose={loadReport} />
          </section>
        )}
        {(report.status === 'locating' || report.status === 'loading') && (
          <ReportSkeleton />
        )}
        {report.status === 'ready' && (
          <div className="report">
            <h1 className="headline">{report.report.headline}</h1>
            {/* A Quiet Night is just its Headline: no cards, and no Detail Layer. */}
            {report.report.highlights.length > 0 && (
              <>
                <HighlightList highlights={report.report.highlights} />
                <VisibleObjects
                  viewingWindow={report.report.viewing_window}
                  objects={notHighlighted(report.report)}
                />
              </>
            )}
          </div>
        )}
      </main>
      {toast && (
        <Toast
          key={toast.id}
          message={toast.message}
          onDismiss={() => setToast(null)}
        />
      )}
    </>
  )
}

/** A failure the backend may not repeat, so its copy suggests searching again. */
function tryAgainMessage(type: ReportErrorType, { label }: Location): string {
  const sky = label ? `${label}'s sky` : 'the sky over your location'
  const reason =
    type === 'narration_failed'
      ? 'the narrator lost the thread'
      : 'something went wrong on our end'
  return `Couldn't read ${sky} — ${reason}. Try searching again.`
}

/** The Visible objects without a Highlight Card: a highlighted object's details are on its card. */
function notHighlighted({ highlights, visible_objects }: CosmicReport): SkyObject[] {
  const onCards = new Set(highlights.map((highlight) => highlight.id))
  return visible_objects.filter((body) => !onCards.has(body.id))
}

export default App
