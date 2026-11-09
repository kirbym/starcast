import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { StrictMode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'
import App from './App.tsx'

const REPORT_URL = 'http://api.test/api/report'
const QUIET_NIGHT = {
  headline: 'A hush settles over the Pacific sky tonight.',
  viewing_window: {
    starts_at: '2026-11-04T02:30:00Z',
    ends_at: '2026-11-04T13:10:00Z',
  },
  highlights: [],
  visible_objects: [],
}

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  server.resetHandlers()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
afterAll(() => server.close())

function fakeGeolocation(
  answer: (success: PositionCallback, failure: PositionErrorCallback) => void,
) {
  vi.stubGlobal('navigator', {
    ...navigator,
    geolocation: {
      // A browser always answers later, never during the call.
      getCurrentPosition: (
        success: PositionCallback,
        failure: PositionErrorCallback,
      ) => setTimeout(() => answer(success, failure)),
    },
  })
}

function renderApp() {
  render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

test('shows the Headline for the browser location on the local date', async () => {
  // 20:30 on 3 November in Los Angeles, when it is already 4 November in UTC.
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-11-04T04:30:00Z') })
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 34.05, longitude: -118.24 },
    } as GeolocationPosition),
  )
  const requests: unknown[] = []
  server.use(
    http.post(REPORT_URL, async ({ request }) => {
      requests.push(await request.json())
      return HttpResponse.json(QUIET_NIGHT)
    }),
  )

  renderApp()

  expect(
    await screen.findByRole('heading', {
      name: 'A hush settles over the Pacific sky tonight.',
    }),
  ).toBeInTheDocument()
  expect(requests).toEqual([
    {
      latitude: 34.05,
      longitude: -118.24,
      timezone: 'America/Los_Angeles',
      date: '2026-11-03',
      location_label: null,
    },
  ])
})

test('says so when the location cannot be read', async () => {
  fakeGeolocation((_success, failure) =>
    failure({ code: 1, message: 'denied' } as GeolocationPositionError),
  )

  renderApp()

  expect(await screen.findByRole('alert')).toBeInTheDocument()
})

test('says so when the report cannot be fetched', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 34.05, longitude: -118.24 },
    } as GeolocationPosition),
  )
  server.use(
    http.post(REPORT_URL, () => new HttpResponse(null, { status: 500 })),
  )

  renderApp()

  expect(await screen.findByRole('alert')).toBeInTheDocument()
})

const JUPITER = {
  id: 'planet:jupiter',
  category: 'planet_moon',
  object_type: 'planet',
  name: 'Jupiter',
  peak_altitude_degrees: 54.8,
  azimuth_at_peak_degrees: 132.2,
  rises_at: '2026-11-06T04:51:49Z',
  sets_at: '2026-11-06T18:30:12Z',
  magnitude: -2.03,
  event: null,
}

test('shows a Highlight Card for each Highlight, without positional numbers', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 40.72, longitude: -74.0 },
    } as GeolocationPosition),
  )
  server.use(
    http.post(REPORT_URL, () =>
      HttpResponse.json({
        ...QUIET_NIGHT,
        headline: 'Jupiter rules the small hours.',
        highlights: [
          {
            ...JUPITER,
            mini_headline: 'The king climbs the east',
            paragraph:
              'Jupiter rises late and climbs high before dawn, a steady lamp among the stars.',
          },
        ],
        visible_objects: [JUPITER],
      }),
    ),
  )

  renderApp()

  const card = await screen.findByRole('article', {
    name: 'The king climbs the east',
  })
  expect(card).toHaveTextContent(
    'Jupiter rises late and climbs high before dawn, a steady lamp among the stars.',
  )
  expect(screen.getAllByRole('article')).toHaveLength(1)
  for (const number of ['54.8', '132.2', '-2.03', '04:51', '18:30']) {
    expect(document.body).not.toHaveTextContent(number)
  }
})

test('shows no Highlight Cards on a Quiet Night', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 69.65, longitude: 18.96 },
    } as GeolocationPosition),
  )
  server.use(http.post(REPORT_URL, () => HttpResponse.json(QUIET_NIGHT)))

  renderApp()

  await screen.findByRole('heading', { name: QUIET_NIGHT.headline })
  expect(screen.queryByRole('article')).not.toBeInTheDocument()
})
