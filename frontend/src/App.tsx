import { useEffect, useRef, useState } from 'react'
import { loadSavedLocation, saveLocation, type Location } from './location.ts'
import { placeName } from './nominatim.ts'
import LocationControl from './LocationControl.tsx'
import PlaceSearch from './PlaceSearch.tsx'
import { fetchReport } from './report.ts'
import ReportSkeleton from './ReportSkeleton.tsx'

const GEOLOCATION_TIMEOUT_MS = 10_000

type ReportState =
  | { status: 'locating' }
  | { status: 'needs-location' }
  | { status: 'loading' }
  | { status: 'ready'; headline: string }
  | { status: 'failed' }

function App() {
  const [location, setLocation] = useState<Location | null>(null)
  const [report, setReport] = useState<ReportState>({ status: 'locating' })
  // Identifies the latest report request. A response for any older request is
  // dropped, so the newest location always wins.
  const latestRequest = useRef(0)

  async function loadReport(target: Location) {
    const request = ++latestRequest.current
    setLocation(target)
    setReport({ status: 'loading' })
    try {
      const { headline } = await fetchReport(target)
      if (request !== latestRequest.current) return
      saveLocation(target)
      setReport({ status: 'ready', headline })
    } catch (error) {
      console.error(error)
      if (request === latestRequest.current) setReport({ status: 'failed' })
    }
  }

  useEffect(() => {
    // StrictMode runs this effect twice. Only the surviving run may call the
    // API, because every report request is a paid Claude call.
    let stale = false

    const saved = loadSavedLocation()
    if (saved) {
      // Defer one tick so the StrictMode cleanup can mark this run stale.
      queueMicrotask(() => {
        if (!stale) void loadReport(saved)
      })
    } else {
      navigator.geolocation.getCurrentPosition(
        async ({ coords: { latitude, longitude } }) => {
          if (stale) return
          const label = await placeName(latitude, longitude)
          if (!stale) void loadReport({ latitude, longitude, label })
        },
        // Denied, unavailable and timed out all mean the same thing here:
        // ask, without scolding about permissions.
        () => {
          if (!stale) setReport({ status: 'needs-location' })
        },
        { timeout: GEOLOCATION_TIMEOUT_MS },
      )
    }

    return () => {
      stale = true
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
          <section className="set-location">
            <h1>Where are you stargazing tonight?</h1>
            <PlaceSearch onChoose={loadReport} />
          </section>
        )}
        {(report.status === 'locating' || report.status === 'loading') && (
          <ReportSkeleton />
        )}
        {report.status === 'ready' && (
          <article className="report">
            <h1 className="headline">{report.headline}</h1>
          </article>
        )}
        {report.status === 'failed' && (
          <p role="alert">Tonight's sky is out of reach right now.</p>
        )}
      </main>
    </>
  )
}

export default App
