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
