import { act, fireEvent, render, screen, within } from '@testing-library/react'
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

const NOMINATIM = 'https://nominatim.openstreetmap.org'

// Every test that geolocates reverse-geocodes the coordinates for the pill.
const server = setupServer(
  http.get(`${NOMINATIM}/reverse`, () =>
    HttpResponse.json({
      name: 'Los Angeles',
      display_name: 'Los Angeles, Los Angeles County, California, United States',
    }),
  ),
)

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  server.resetHandlers()
  localStorage.clear()
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

function saveLocation(location: {
  latitude: number
  longitude: number
  label: string | null
}) {
  localStorage.setItem('starcast.location', JSON.stringify(location))
}

function savedLocation(): unknown {
  const raw = localStorage.getItem('starcast.location')
  return raw === null ? null : JSON.parse(raw)
}

function denyGeolocation() {
  fakeGeolocation((_success, failure) =>
    failure({ code: 1, message: 'denied' } as GeolocationPositionError),
  )
}

function geolocateTo(latitude: number, longitude: number) {
  fakeGeolocation((success) =>
    success({ coords: { latitude, longitude } } as GeolocationPosition),
  )
}

const TOKYO_MATCH = {
  lat: '35.6769',
  lon: '139.7639',
  name: 'Tokyo',
  display_name: 'Tokyo, Japan',
}

function searchFor(query: string) {
  const box = screen.getByRole('searchbox')
  fireEvent.change(box, { target: { value: query } })
  fireEvent.submit(box)
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
      location_label: 'Los Angeles',
    },
  ])
})

test('labels the geolocated pill and saves the location only after the report succeeds', async () => {
  geolocateTo(34.05, -118.24)
  let respond: () => void = () => {}
  const reportRequested = new Promise<void>((requested) => {
    server.use(
      http.post(REPORT_URL, async () => {
        requested()
        await new Promise<void>((resolve) => (respond = resolve))
        return HttpResponse.json(QUIET_NIGHT)
      }),
    )
  })

  renderApp()

  expect(
    await screen.findByRole('button', { name: '📍 Los Angeles ▾' }),
  ).toBeInTheDocument()
  await reportRequested
  expect(savedLocation()).toBeNull()

  respond()

  expect(
    await screen.findByRole('heading', { name: QUIET_NIGHT.headline }),
  ).toBeInTheDocument()
  expect(savedLocation()).toEqual({
    latitude: 34.05,
    longitude: -118.24,
    label: 'Los Angeles',
  })
})

test.each([
  ['denied', 1],
  ['unavailable', 2],
  ['timed out', 3],
])(
  'asks where you are stargazing when geolocation is %s',
  async (_reason, code) => {
    fakeGeolocation((_success, failure) =>
      failure({ code, message: 'no position' } as GeolocationPositionError),
    )

    renderApp()

    expect(
      await screen.findByRole('heading', {
        name: 'Where are you stargazing tonight?',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: '📍 Set location' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  },
)

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
  expect(savedLocation()).toBeNull()
})

test('loads the report for the saved location without asking for geolocation', async () => {
  saveLocation({ latitude: 37.77, longitude: -122.42, label: 'San Francisco' })
  const getCurrentPosition = vi.fn()
  vi.stubGlobal('navigator', { ...navigator, geolocation: { getCurrentPosition } })
  const requests: unknown[] = []
  server.use(
    http.post(REPORT_URL, async ({ request }) => {
      requests.push(await request.json())
      return HttpResponse.json(QUIET_NIGHT)
    }),
  )

  renderApp()

  expect(
    await screen.findByRole('heading', { name: QUIET_NIGHT.headline }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: '📍 San Francisco ▾' }),
  ).toBeInTheDocument()
  expect(requests).toMatchObject([
    { latitude: 37.77, longitude: -122.42, location_label: 'San Francisco' },
  ])
  expect(getCurrentPosition).not.toHaveBeenCalled()
})

test('changes location by searching from the header pill', async () => {
  saveLocation({ latitude: 37.77, longitude: -122.42, label: 'San Francisco' })
  const requests: unknown[] = []
  server.use(
    http.post(REPORT_URL, async ({ request }) => {
      requests.push(await request.json())
      return HttpResponse.json(QUIET_NIGHT)
    }),
    http.get(`${NOMINATIM}/search`, ({ request }) =>
      new URL(request.url).searchParams.get('q') === 'Tokyo'
        ? HttpResponse.json([TOKYO_MATCH])
        : HttpResponse.json([]),
    ),
  )
  renderApp()
  await screen.findByRole('heading', { name: QUIET_NIGHT.headline })

  fireEvent.click(screen.getByRole('button', { name: '📍 San Francisco ▾' }))
  searchFor('Tokyo')
  fireEvent.click(await screen.findByRole('button', { name: 'Tokyo, Japan' }))

  expect(
    await screen.findByRole('button', { name: '📍 Tokyo ▾' }),
  ).toBeInTheDocument()
  await screen.findByRole('heading', { name: QUIET_NIGHT.headline })
  expect(requests[1]).toMatchObject({
    latitude: 35.6769,
    longitude: 139.7639,
    location_label: 'Tokyo',
  })
  expect(savedLocation()).toEqual({
    latitude: 35.6769,
    longitude: 139.7639,
    label: 'Tokyo',
  })
  expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
})

test('loads a report for a place chosen on the set-location screen', async () => {
  denyGeolocation()
  server.use(
    http.post(REPORT_URL, () => HttpResponse.json(QUIET_NIGHT)),
    http.get(`${NOMINATIM}/search`, () => HttpResponse.json([TOKYO_MATCH])),
  )
  renderApp()
  const setLocationScreen = await screen.findByRole('region', {
    name: 'Where are you stargazing tonight?',
  })

  searchFor('Tokyo')
  fireEvent.click(
    await within(setLocationScreen).findByRole('button', {
      name: 'Tokyo, Japan',
    }),
  )

  expect(
    await screen.findByRole('heading', { name: QUIET_NIGHT.headline }),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '📍 Tokyo ▾' })).toBeInTheDocument()
  expect(savedLocation()).toMatchObject({ label: 'Tokyo' })
})

test.each([
  ['finds nothing', () => HttpResponse.json([]), "No places match 'Atlantis'"],
  [
    'fails',
    () => new HttpResponse(null, { status: 503 }),
    "Couldn't reach place search",
  ],
  ['is unreachable', () => HttpResponse.error(), "Couldn't reach place search"],
])(
  'says so inline when place search %s, keeping the query and not retrying',
  async (_outcome, respond, message) => {
    denyGeolocation()
    let searches = 0
    server.use(
      http.get(`${NOMINATIM}/search`, () => {
        searches += 1
        return respond()
      }),
    )
    renderApp()
    await screen.findByRole('heading', {
      name: 'Where are you stargazing tonight?',
    })

    searchFor('Atlantis')

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toHaveValue('Atlantis')
    expect(screen.queryByRole('button', { name: /retry|try again/i })).toBeNull()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(searches).toBe(1)
  },
)

test('shows the skeleton in place of the previous report while a new location loads', async () => {
  saveLocation({ latitude: 37.77, longitude: -122.42, label: 'San Francisco' })
  const TOKYO_NIGHT = { ...QUIET_NIGHT, headline: 'Tokyo looks up tonight.' }
  let respondForTokyo: () => void = () => {}
  server.use(
    http.post(REPORT_URL, async ({ request }) => {
      const { location_label } = (await request.json()) as {
        location_label: string
      }
      if (location_label !== 'Tokyo') return HttpResponse.json(QUIET_NIGHT)
      await new Promise<void>((resolve) => (respondForTokyo = resolve))
      return HttpResponse.json(TOKYO_NIGHT)
    }),
    http.get(`${NOMINATIM}/search`, () => HttpResponse.json([TOKYO_MATCH])),
  )
  renderApp()
  expect(
    screen.getByRole('status', { name: "Loading tonight's report" }),
  ).toBeInTheDocument()
  await screen.findByRole('heading', { name: QUIET_NIGHT.headline })
  expect(screen.queryByRole('status')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '📍 San Francisco ▾' }))
  searchFor('Tokyo')
  fireEvent.click(await screen.findByRole('button', { name: 'Tokyo, Japan' }))

  expect(
    await screen.findByRole('status', { name: "Loading tonight's report" }),
  ).toBeInTheDocument()
  expect(
    screen.queryByRole('heading', { name: QUIET_NIGHT.headline }),
  ).not.toBeInTheDocument()

  respondForTokyo()

  expect(
    await screen.findByRole('heading', { name: TOKYO_NIGHT.headline }),
  ).toBeInTheDocument()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test('closes the place search on Escape without changing location', async () => {
  saveLocation({ latitude: 37.77, longitude: -122.42, label: 'San Francisco' })
  server.use(http.post(REPORT_URL, () => HttpResponse.json(QUIET_NIGHT)))
  renderApp()
  await screen.findByRole('heading', { name: QUIET_NIGHT.headline })

  const pill = screen.getByRole('button', { name: '📍 San Francisco ▾' })
  fireEvent.click(pill)
  fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Escape' })

  expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
  expect(pill).toHaveAttribute('aria-expanded', 'false')
})

test('keeps a place chosen while geolocation is still pending', async () => {
  let answerGeolocation: () => void = () => {}
  fakeGeolocation((success) => {
    answerGeolocation = () =>
      success({
        coords: { latitude: 34.05, longitude: -118.24 },
      } as GeolocationPosition)
  })
  const labels: unknown[] = []
  server.use(
    http.post(REPORT_URL, async ({ request }) => {
      labels.push(((await request.json()) as { location_label: unknown }).location_label)
      return HttpResponse.json(QUIET_NIGHT)
    }),
    http.get(`${NOMINATIM}/search`, () => HttpResponse.json([TOKYO_MATCH])),
  )
  renderApp()

  fireEvent.click(await screen.findByRole('button', { name: '📍 Locating…' }))
  searchFor('Tokyo')
  fireEvent.click(await screen.findByRole('button', { name: 'Tokyo, Japan' }))
  await screen.findByRole('heading', { name: QUIET_NIGHT.headline })
  await act(async () => {
    answerGeolocation()
    await new Promise((resolve) => setTimeout(resolve, 50))
  })

  expect(screen.getByRole('button', { name: '📍 Tokyo ▾' })).toBeInTheDocument()
  expect(labels).toEqual(['Tokyo'])
  expect(savedLocation()).toMatchObject({ label: 'Tokyo' })
})

test('asks where you are stargazing when the location prompt goes unanswered', async () => {
  vi.useFakeTimers({ toFake: ['setTimeout'] })
  vi.stubGlobal('navigator', {
    ...navigator,
    geolocation: { getCurrentPosition: () => {} },
  })

  renderApp()
  await act(async () => {
    vi.advanceTimersByTime(20_000)
  })

  expect(
    screen.getByRole('heading', { name: 'Where are you stargazing tonight?' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '📍 Set location' })).toBeInTheDocument()
})
