import { useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

type ReportState =
  | { status: 'loading' }
  | { status: 'ready'; headline: string }
  | { status: 'failed' }

function localDate(now: Date): string {
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

async function fetchHeadline(coords: GeolocationCoordinates): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      latitude: coords.latitude,
      longitude: coords.longitude,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      date: localDate(new Date()),
      location_label: null,
    }),
  })
  if (!response.ok) {
    throw new Error(`Report request failed with status ${response.status}`)
  }
  const report: { headline: string } = await response.json()
  return report.headline
}

function App() {
  const [report, setReport] = useState<ReportState>({ status: 'loading' })

  useEffect(() => {
    // StrictMode runs this effect twice. Only the surviving run may call the
    // API, because every report request is a paid Claude call.
    let stale = false

    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        if (stale) return
        try {
          const headline = await fetchHeadline(coords)
          if (!stale) setReport({ status: 'ready', headline })
        } catch (error) {
          console.error(error)
          if (!stale) setReport({ status: 'failed' })
        }
      },
      () => {
        if (!stale) setReport({ status: 'failed' })
      },
    )

    return () => {
      stale = true
    }
  }, [])

  return (
    <main>
      {report.status === 'loading' && <p>Reading tonight's sky…</p>}
      {report.status === 'ready' && <h1>{report.headline}</h1>}
      {report.status === 'failed' && (
        <p role="alert">Tonight's sky is out of reach right now.</p>
      )}
    </main>
  )
}

export default App
