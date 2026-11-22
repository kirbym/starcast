import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { StrictMode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'
import App from './App.tsx'
import type { VisibleBody } from './report.ts'

const REPORT_URL = 'http://api.test/api/report'
const QUIET_NIGHT = {
  // The place's own zone and date; here, the same zone the tests run in.
  timezone: 'America/Los_Angeles',
  date: '2026-11-03',
  headline: 'A hush settles over the Pacific sky tonight.',
  viewing_window: {
    starts_at: '2026-11-04T02:30:00Z',
    ends_at: '2026-11-04T13:10:00Z',
  },
  highlights: [],
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
  vi.restoreAllMocks()
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

test('shows the Headline for the browser location, leaving its timezone and date to the backend', async () => {
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
  // The place's timezone and tonight's date there are the backend's to work out: the browser's
  // own would be wrong for a place in another zone.
  expect(requests).toEqual([
    { latitude: 34.05, longitude: -118.24, location_label: 'Los Angeles' },
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

function errorResponse(statusCode: number, type: string, message: string) {
  return HttpResponse.json(
    { error: { statusCode, type, message } },
    { status: statusCode },
  )
}

const SAN_FRANCISCO = { latitude: 37.77, longitude: -122.42, label: 'San Francisco' }

/** San Francisco is saved and its report loads; then Tokyo's report gets `tokyoResponse`. */
async function changeFromSanFranciscoToTokyo(tokyoResponse: () => Response) {
  saveLocation(SAN_FRANCISCO)
  const requests: unknown[] = []
  server.use(
    http.post(REPORT_URL, async ({ request }) => {
      const body = (await request.json()) as { location_label: string }
      requests.push(body)
      return body.location_label === 'Tokyo'
        ? tokyoResponse()
        : HttpResponse.json(QUIET_NIGHT)
    }),
    http.get(`${NOMINATIM}/search`, () => HttpResponse.json([TOKYO_MATCH])),
  )
  renderApp()
  await screen.findByRole('heading', { name: QUIET_NIGHT.headline })

  fireEvent.click(screen.getByRole('button', { name: '📍 San Francisco ▾' }))
  searchFor('Tokyo')
  fireEvent.click(await screen.findByRole('button', { name: 'Tokyo, Japan' }))
  return requests
}

test.each([
  [502, 'narration_failed'],
  [500, 'internal_error'],
  [400, 'invalid_request'],
])(
  'rolls back to the last good location when a location change fails with %i',
  async (status, type) => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})

    await changeFromSanFranciscoToTokyo(() =>
      errorResponse(status, type, 'Backend detail: Claude stopped early'),
    )

    const toast = await screen.findByRole('alert')
    expect(toast).toHaveTextContent('Tokyo')
    expect(toast).toHaveTextContent(/try searching again/i)
    expect(
      screen.getByRole('button', { name: '📍 San Francisco ▾' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: QUIET_NIGHT.headline }),
    ).toBeInTheDocument()
    expect(savedLocation()).toEqual(SAN_FRANCISCO)
    expect(document.body).not.toHaveTextContent('Backend detail')
    expect(logged).toHaveBeenCalledWith(
      expect.stringContaining('Backend detail: Claude stopped early'),
    )
  },
)

test('asks for another place when the location is rejected', async () => {
  const logged = vi.spyOn(console, 'error').mockImplementation(() => {})

  await changeFromSanFranciscoToTokyo(() =>
    errorResponse(400, 'invalid_location', 'latitude: out of range'),
  )

  const toast = await screen.findByRole('alert')
  expect(toast).toHaveTextContent(
    "We couldn't use that location — pick another.",
  )
  expect(toast).not.toHaveTextContent(/try/i)
  expect(
    screen.getByRole('heading', { name: 'Where are you stargazing tonight?' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '📍 Set location' })).toBeInTheDocument()
  expect(savedLocation()).toBeNull()
  expect(document.body).not.toHaveTextContent('latitude: out of range')
  expect(logged).toHaveBeenCalledWith(
    expect.stringContaining('latitude: out of range'),
  )
})

test('keeps the saved location when the rest of the request is rejected', async () => {
  // Only the latitude and longitude are the place; a bad label says nothing about it.
  vi.spyOn(console, 'error').mockImplementation(() => {})
  saveLocation(SAN_FRANCISCO)
  server.use(
    http.post(REPORT_URL, () =>
      errorResponse(400, 'invalid_request', 'location_label: Input should be a valid string'),
    ),
  )

  renderApp()

  expect(await screen.findByRole('alert')).toHaveTextContent(/try searching again/i)
  expect(
    screen.getByRole('button', { name: '📍 San Francisco ▾' }),
  ).toBeInTheDocument()
  expect(savedLocation()).toEqual(SAN_FRANCISCO)
  expect(document.body).not.toHaveTextContent('Input should be a valid string')
})

test('leaves the report area empty when the first report fails', async () => {
  const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
  geolocateTo(34.05, -118.24)
  server.use(
    http.post(REPORT_URL, () =>
      errorResponse(502, 'narration_failed', 'Claude stopped early'),
    ),
  )

  renderApp()

  expect(await screen.findByRole('alert')).toHaveTextContent('Los Angeles')
  expect(screen.getByRole('main')).toBeEmptyDOMElement()
  expect(
    screen.getByRole('button', { name: '📍 Los Angeles ▾' }),
  ).toBeInTheDocument()
  expect(savedLocation()).toBeNull()
  expect(document.body).not.toHaveTextContent('Claude stopped early')
  expect(logged).toHaveBeenCalledWith(
    expect.stringContaining('Claude stopped early'),
  )
})

test('shows one toast at a time, which only informs and can be dismissed', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  geolocateTo(34.05, -118.24)
  let reportRequests = 0
  server.use(
    http.post(REPORT_URL, () => {
      reportRequests += 1
      return errorResponse(502, 'narration_failed', 'Claude stopped early')
    }),
    http.get(`${NOMINATIM}/search`, () => HttpResponse.json([TOKYO_MATCH])),
  )
  renderApp()
  expect(await screen.findByRole('alert')).toHaveTextContent('Los Angeles')

  fireEvent.click(screen.getByRole('button', { name: '📍 Los Angeles ▾' }))
  searchFor('Tokyo')
  fireEvent.click(await screen.findByRole('button', { name: 'Tokyo, Japan' }))
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('Tokyo'),
  )

  const toasts = screen.getAllByRole('alert')
  expect(toasts).toHaveLength(1)
  expect(toasts[0]).not.toHaveTextContent('Los Angeles')
  expect(within(toasts[0]).getAllByRole('button')).toHaveLength(1)
  expect(reportRequests).toBe(2)

  fireEvent.click(within(toasts[0]).getByRole('button', { name: 'Dismiss' }))

  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  await new Promise((resolve) => setTimeout(resolve, 50))
  expect(reportRequests).toBe(2)
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

const JUPITER = {
  id: 'planet:jupiter',
  category: 1,
  object_type: 'planet',
  name: 'Jupiter',
  peak_altitude_degrees: 54.8,
  azimuth_at_peak_degrees: 132.2,
  rises_at: '2026-11-06T04:51:49Z',
  sets_at: '2026-11-06T18:30:12Z',
  magnitude: -2.03,
  event: null,
} satisfies VisibleBody

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
      }),
    ),
  )

  renderApp()

  const card = await screen.findByRole('article', {
    name: 'The king climbs the east Planet',
  })
  expect(card).toHaveTextContent(
    'Jupiter rises late and climbs high before dawn, a steady lamp among the stars.',
  )
  expect(screen.getAllByRole('article')).toHaveLength(1)
  for (const number of ['54.8', '55°', '132', '−2.0', '8:51', '10:30']) {
    expect(document.body).not.toHaveTextContent(number)
  }
})

const ANDROMEDA = {
  id: 'constellation:and',
  category: 2,
  object_type: 'constellation',
  name: 'Andromeda',
  peak_altitude_degrees: 89.7,
  azimuth_at_peak_degrees: 351.4,
  rises_at: '2026-11-05T12:10:02Z',
  sets_at: '2026-11-06T09:41:37Z',
  magnitude: null,
  event: null,
} satisfies VisibleBody

test('shows a planet and a constellation Highlight Card together, in Category order', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 40.72, longitude: -74.0 },
    } as GeolocationPosition),
  )
  server.use(
    http.post(REPORT_URL, () =>
      HttpResponse.json({
        ...QUIET_NIGHT,
        headline: 'Jupiter rules the small hours while Andromeda passes overhead.',
        highlights: [
          {
            ...JUPITER,
            mini_headline: 'The king climbs the east',
            paragraph: 'Jupiter rises late and climbs high before dawn.',
          },
          {
            ...ANDROMEDA,
            mini_headline: 'The chained princess overhead',
            paragraph: 'Andromeda sails straight overhead in the evening, chained to her rock.',
          },
        ],
      }),
    ),
  )

  renderApp()

  const constellation = await screen.findByRole('article', {
    name: 'The chained princess overhead Constellation',
  })
  expect(constellation).toHaveTextContent(
    'Andromeda sails straight overhead in the evening, chained to her rock.',
  )
  const headings = screen
    .getAllByRole('article')
    .map((card) => card.querySelector('h2')?.textContent)
  expect(headings).toEqual([
    'The king climbs the east Planet',
    'The chained princess overhead Constellation',
  ])
  for (const number of ['89.7', '351.4', '12:10', '09:41']) {
    expect(document.body).not.toHaveTextContent(number)
  }
})

const SIRIUS = {
  id: 'bright_star:sirius',
  category: 3,
  object_type: 'bright_star',
  name: 'Sirius',
  peak_altitude_degrees: 31.2,
  azimuth_at_peak_degrees: 168.9,
  rises_at: '2026-11-06T04:23:41Z',
  sets_at: '2026-11-06T14:57:06Z',
  magnitude: -1.44,
  event: null,
} satisfies VisibleBody

test('shows up to three Highlight Cards, one per Category, in Category order', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 40.72, longitude: -74.0 },
    } as GeolocationPosition),
  )
  server.use(
    http.post(REPORT_URL, () =>
      HttpResponse.json({
        ...QUIET_NIGHT,
        headline: 'Sirius blazes up before dawn, with Jupiter riding high beside it.',
        highlights: [
          {
            ...JUPITER,
            mini_headline: 'The king climbs the east',
            paragraph: 'Jupiter rises late and climbs high before dawn.',
          },
          {
            ...ANDROMEDA,
            mini_headline: 'The chained princess overhead',
            paragraph: 'Andromeda sails straight overhead in the evening, chained to her rock.',
          },
          {
            ...SIRIUS,
            mini_headline: 'The Dog Star wakes',
            paragraph: 'Sirius, the brightest star of all, flashes low in the south before dawn.',
          },
        ],
      }),
    ),
  )

  renderApp()

  const star = await screen.findByRole('article', { name: 'The Dog Star wakes Bright Star' })
  expect(star).toHaveTextContent(
    'Sirius, the brightest star of all, flashes low in the south before dawn.',
  )
  const headings = screen
    .getAllByRole('article')
    .map((card) => card.querySelector('h2')?.textContent)
  expect(headings).toEqual([
    'The king climbs the east Planet',
    'The chained princess overhead Constellation',
    'The Dog Star wakes Bright Star',
  ])
  for (const number of ['-1.44', '31.2', '168.9', '04:23', '14:57']) {
    expect(document.body).not.toHaveTextContent(number)
  }
})

const GREAT_CONJUNCTION = {
  id: 'significant_event:conjunction_jupiter_saturn',
  category: 3,
  object_type: 'significant_event',
  name: 'Jupiter and Saturn in conjunction',
  peak_altitude_degrees: 6.1,
  azimuth_at_peak_degrees: 234.6,
  rises_at: '2020-12-21T15:31:07Z',
  sets_at: '2020-12-22T00:16:54Z',
  magnitude: null,
  event: {
    event_type: 'conjunction',
    // Shown in the place's time zone: 3:11 PM in QUIET_NIGHT's Los Angeles.
    peak_time: '2020-12-21T23:11:00Z',
    related_object_names: ['Jupiter', 'Saturn'],
  },
} satisfies VisibleBody

test('shows a Significant Event Highlight Card whose Detail Layer names its bodies and peak time', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 40.72, longitude: -74.0 },
    } as GeolocationPosition),
  )
  server.use(
    http.post(REPORT_URL, () =>
      HttpResponse.json({
        ...QUIET_NIGHT,
        headline: 'Jupiter and Saturn all but touch at dusk.',
        highlights: [
          {
            ...GREAT_CONJUNCTION,
            mini_headline: 'The great conjunction',
            paragraph: 'Jupiter and Saturn sink together in the south-west, nearly one light.',
          },
        ],
      }),
    ),
  )

  renderApp()

  const card = await screen.findByRole('article', { name: 'The great conjunction Conjunction' })
  expect(card).toHaveTextContent(
    'Jupiter and Saturn sink together in the south-west, nearly one light.',
  )
  expect(card).not.toHaveTextContent('3:11')

  const toggle = within(card).getByRole('button', { name: 'Details' })
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(toggle)

  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  const details = within(card).getByRole('region', { name: 'Details' })
  expect(details).toHaveTextContent('Jupiter and Saturn')
  expect(details).toHaveTextContent('3:11 PM')

  fireEvent.click(toggle)
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(within(card).queryByRole('region')).not.toBeInTheDocument()
})

const MARS_OPPOSITION = {
  id: 'significant_event:opposition_mars',
  category: 3,
  object_type: 'significant_event',
  name: 'Mars at opposition',
  peak_altitude_degrees: 49.2,
  azimuth_at_peak_degrees: 180.4,
  rises_at: '2020-10-13T22:43:12Z',
  sets_at: '2020-10-14T11:18:40Z',
  magnitude: -2.6,
  event: {
    event_type: 'opposition',
    // Shown in the place's time zone: 9:55 PM in QUIET_NIGHT's Los Angeles.
    peak_time: '2020-10-14T04:55:00Z',
    related_object_names: ['Mars'],
  },
} satisfies VisibleBody

test('shows an opposition Highlight Card whose Detail Layer names the event, its planet and peak time', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 40.72, longitude: -74.0 },
    } as GeolocationPosition),
  )
  server.use(
    http.post(REPORT_URL, () =>
      HttpResponse.json({
        ...QUIET_NIGHT,
        headline: 'Mars blazes all night long.',
        highlights: [
          {
            ...MARS_OPPOSITION,
            mini_headline: 'Mars at its brightest',
            paragraph: 'Mars rises as the Sun sets and burns orange all night.',
          },
        ],
      }),
    ),
  )

  renderApp()

  const card = await screen.findByRole('article', { name: 'Mars at its brightest Opposition' })
  fireEvent.click(within(card).getByRole('button', { name: 'Details' }))

  const details = within(card).getByRole('region', { name: 'Details' })
  expect(details).toHaveTextContent('EventOpposition')
  expect(details).toHaveTextContent('PlanetMars')
  expect(details).toHaveTextContent('Peak9:55 PM')
})

const PERSEIDS = {
  id: 'significant_event:meteor_shower_per',
  category: 3,
  object_type: 'significant_event',
  name: 'Perseids meteor shower',
  peak_altitude_degrees: 71.4,
  azimuth_at_peak_degrees: 32.8,
  rises_at: null,
  sets_at: null,
  magnitude: null,
  event: {
    event_type: 'meteor_shower',
    // Shown in the place's time zone: 1:20 AM in QUIET_NIGHT's Los Angeles.
    peak_time: '2026-08-13T08:20:00Z',
    related_object_names: ['Perseus'],
  },
} satisfies VisibleBody

test('shows a meteor shower Highlight Card whose Detail Layer names the event, its radiant and peak time', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 40.72, longitude: -74.0 },
    } as GeolocationPosition),
  )
  server.use(
    http.post(REPORT_URL, () =>
      HttpResponse.json({
        ...QUIET_NIGHT,
        headline: 'The Perseids rain down tonight.',
        highlights: [
          {
            ...PERSEIDS,
            mini_headline: 'Perseids at their peak',
            paragraph: 'Swift streaks fly out of Perseus all night.',
          },
        ],
      }),
    ),
  )

  renderApp()

  const card = await screen.findByRole('article', { name: 'Perseids at their peak Meteor Shower' })
  fireEvent.click(within(card).getByRole('button', { name: 'Details' }))

  const details = within(card).getByRole('region', { name: 'Details' })
  expect(details).toHaveTextContent('EventMeteor shower')
  expect(details).toHaveTextContent('RadiantPerseus')
  expect(details).toHaveTextContent('Peak1:20 AM')
})

/** A one-card night whose card describes `body`, under the mini headline "Look up". */
function oneCardNight(body: VisibleBody) {
  return {
    ...QUIET_NIGHT,
    headline: 'One thing to see tonight.',
    highlights: [{ ...body, mini_headline: 'Look up', paragraph: 'It is up there.' }],
  }
}

const MOON = {
  ...JUPITER,
  id: 'moon:moon',
  object_type: 'moon',
  name: 'Moon',
} satisfies VisibleBody

const COMET = {
  ...SIRIUS,
  id: 'named_comet:12p',
  object_type: 'named_comet',
  name: '12P/Pons-Brooks',
} satisfies VisibleBody

const ANDROMEDA_GALAXY = {
  ...SIRIUS,
  id: 'dso:m31',
  object_type: 'dso',
  name: 'Andromeda Galaxy',
} satisfies VisibleBody

test.each([
  ['a planet', JUPITER, 'Planet'],
  ['the Moon', MOON, 'Moon'],
  ['a constellation', ANDROMEDA, 'Constellation'],
  ['a bright star', SIRIUS, 'Bright Star'],
  ['a named comet', COMET, 'Comet'],
  ['a deep-sky object', ANDROMEDA_GALAXY, 'Deep-Sky Object'],
  ['a conjunction', GREAT_CONJUNCTION, 'Conjunction'],
  ['an opposition', MARS_OPPOSITION, 'Opposition'],
  ['a meteor shower', PERSEIDS, 'Meteor Shower'],
])("ends the title of %s's Highlight Card with its label", async (_, body, label) => {
  geolocateToNewYork()
  respondWith(oneCardNight(body))
  renderApp()

  const card = await screen.findByRole('article', { name: `Look up ${label}` })
  const heading = within(card).getByRole('heading', { level: 2 })
  expect(heading).toHaveAccessibleName(`Look up ${label}`)
  expect(heading.lastElementChild).toHaveTextContent(new RegExp(`^${label}$`))
})

test('shows no Highlight Cards on a Quiet Night', async () => {
  fakeGeolocation((success) =>
    success({
      coords: { latitude: 69.65, longitude: 18.96 },
    } as GeolocationPosition),
  )
  server.use(http.post(REPORT_URL, () => HttpResponse.json(QUIET_NIGHT)))

  renderApp()

  const headline = await screen.findByRole('heading', { name: QUIET_NIGHT.headline })
  expect(screen.queryByRole('article')).not.toBeInTheDocument()
  // Only the Headline: no empty card list, no Viewing Window, no error styling.
  expect(headline.parentElement?.children).toHaveLength(1)
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(document.body).not.toHaveTextContent('6:30 PM')
})

function geolocateToNewYork() {
  geolocateTo(40.72, -74.0)
}

function respondWith(report: object) {
  server.use(http.post(REPORT_URL, () => HttpResponse.json(report)))
}

const POLARIS = {
  id: 'bright_star:polaris',
  category: 3,
  object_type: 'bright_star',
  name: 'Polaris',
  peak_altitude_degrees: 41.3,
  azimuth_at_peak_degrees: 0.4,
  // Circumpolar: it neither rises nor sets tonight.
  rises_at: null,
  sets_at: null,
  magnitude: 1.98,
  event: null,
} satisfies VisibleBody

const THREE_CARD_NIGHT = {
  ...QUIET_NIGHT,
  headline: 'Jupiter, Andromeda and Polaris share the sky.',
  highlights: [
    { ...JUPITER, mini_headline: 'The king climbs the east', paragraph: 'Jupiter climbs.' },
    { ...ANDROMEDA, mini_headline: 'The chained princess overhead', paragraph: 'Andromeda sails.' },
    { ...POLARIS, mini_headline: 'The pole star holds still', paragraph: 'Polaris waits.' },
  ],
}

function detailsOf(card: HTMLElement) {
  return within(card).queryByRole('region', { name: 'Details' })
}

test("expands a Highlight Card's Detail Layer to show its positional fields in local time", async () => {
  geolocateToNewYork()
  respondWith(THREE_CARD_NIGHT)
  renderApp()
  const card = await screen.findByRole('article', { name: 'The king climbs the east Planet' })
  const toggle = within(card).getByRole('button', { name: 'Details' })
  expect(detailsOf(card)).not.toBeInTheDocument()

  fireEvent.click(toggle)

  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  const details = detailsOf(card)
  expect(details).toHaveTextContent('Peak altitude55°')
  expect(details).toHaveTextContent('Direction at peak132° SE')
  // 04:51 and 18:30 UTC, in Los Angeles where the tests run.
  expect(details).toHaveTextContent('Rises8:51 PM')
  expect(details).toHaveTextContent('Sets10:30 AM')
  // A true minus sign, not a hyphen.
  expect(details).toHaveTextContent('Magnitude−2.0')

  fireEvent.click(toggle)

  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(detailsOf(card)).not.toBeInTheDocument()
})

test('expands each Highlight Card independently', async () => {
  geolocateToNewYork()
  respondWith(THREE_CARD_NIGHT)
  renderApp()
  const jupiter = await screen.findByRole('article', { name: 'The king climbs the east Planet' })
  const andromeda = screen.getByRole('article', { name: 'The chained princess overhead Constellation' })
  const polaris = screen.getByRole('article', { name: 'The pole star holds still Bright Star' })

  fireEvent.click(within(jupiter).getByRole('button', { name: 'Details' }))
  fireEvent.click(within(andromeda).getByRole('button', { name: 'Details' }))

  expect(detailsOf(jupiter)).toBeInTheDocument()
  expect(detailsOf(andromeda)).toHaveTextContent('Peak altitude90°')
  expect(detailsOf(polaris)).not.toBeInTheDocument()

  fireEvent.click(within(jupiter).getByRole('button', { name: 'Details' }))

  expect(detailsOf(jupiter)).not.toBeInTheDocument()
  expect(detailsOf(andromeda)).toBeInTheDocument()
})

test('says a body does not rise or set tonight when those times are null, and dashes a missing magnitude', async () => {
  geolocateToNewYork()
  respondWith(THREE_CARD_NIGHT)
  renderApp()
  const polaris = await screen.findByRole('article', { name: 'The pole star holds still Bright Star' })
  const andromeda = screen.getByRole('article', { name: 'The chained princess overhead Constellation' })

  fireEvent.click(within(polaris).getByRole('button', { name: 'Details' }))
  fireEvent.click(within(andromeda).getByRole('button', { name: 'Details' }))

  const details = detailsOf(polaris)
  expect(details).toHaveTextContent("RisesDoesn't rise tonight")
  expect(details).toHaveTextContent("SetsDoesn't set tonight")
  expect(details).not.toHaveTextContent(/\d:\d\d/)
  expect(detailsOf(andromeda)).toHaveTextContent(/Magnitude—$/)
  expect(within(andromeda).getByLabelText('No magnitude')).toHaveTextContent('—')
})

test('shows no shared list of the other Visible bodies', async () => {
  geolocateToNewYork()
  respondWith(THREE_CARD_NIGHT)
  renderApp()
  await screen.findByRole('article', { name: 'The king climbs the east Planet' })

  expect(screen.queryByText('Also visible tonight')).not.toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Show all/ })).not.toBeInTheDocument()
})

/** The line directly under the Headline. */
async function sublineOfHeadline() {
  const headline = await screen.findByRole('heading', { level: 1 })
  return headline.nextElementSibling as HTMLElement
}

test("shows the Viewing Window's start and end in local time", async () => {
  geolocateToNewYork()
  respondWith(THREE_CARD_NIGHT)
  renderApp()

  const subline = await sublineOfHeadline()

  // 02:30 and 13:10 UTC, in Los Angeles: the place's zone, and the one the tests run in, so it
  // needs no label.
  expect(subline).toHaveTextContent(/^Dark from 6:30 PM to 5:10 AM$/)
  expect(within(subline).getByText('6:30 PM')).toHaveAttribute(
    'datetime',
    QUIET_NIGHT.viewing_window.starts_at,
  )
})

// The same night as THREE_CARD_NIGHT, reported for a place in Tokyo, while the browser (where
// the tests run) is in Los Angeles.
const TOKYO_NIGHT = { ...THREE_CARD_NIGHT, timezone: 'Asia/Tokyo', date: '2026-11-04' }

test("shows every time in the place's zone, not the browser's, each naming that zone", async () => {
  geolocateToNewYork()
  respondWith(TOKYO_NIGHT)
  renderApp()

  // 02:30 and 13:10 UTC are 11:30 AM and 10:10 PM in Tokyo.
  expect(await sublineOfHeadline()).toHaveTextContent('Dark from 11:30 AM GMT+9 to 10:10 PM GMT+9')
  // Jupiter rises at 04:51 and sets at 18:30 UTC.
  const card = screen.getByRole('article', { name: 'The king climbs the east Planet' })
  fireEvent.click(within(card).getByRole('button', { name: 'Details' }))
  expect(detailsOf(card)).toHaveTextContent('Rises1:51 PM GMT+9')
  expect(detailsOf(card)).toHaveTextContent('Sets3:30 AM GMT+9')
})

test("names each time's own offset when the place's clock changes overnight", async () => {
  geolocateToNewYork()
  // New York's clocks fall back at 06:00 UTC on 1 November 2026, between dusk and dawn.
  respondWith({
    ...THREE_CARD_NIGHT,
    timezone: 'America/New_York',
    viewing_window: { starts_at: '2026-11-01T00:00:00Z', ends_at: '2026-11-01T10:00:00Z' },
  })
  renderApp()

  expect(await sublineOfHeadline()).toHaveTextContent('Dark from 8:00 PM EDT to 5:00 AM EST')
})

test("shows a Significant Event's peak in the place's zone", async () => {
  geolocateToNewYork()
  respondWith({
    ...QUIET_NIGHT,
    timezone: 'Asia/Tokyo',
    highlights: [{ ...GREAT_CONJUNCTION, mini_headline: 'The great conjunction', paragraph: 'J.' }],
  })
  renderApp()

  const card = await screen.findByRole('article', { name: 'The great conjunction Conjunction' })
  fireEvent.click(within(card).getByRole('button', { name: 'Details' }))

  // 23:11 UTC on 21 December is 8:11 the next morning in Tokyo.
  expect(detailsOf(card)).toHaveTextContent('Peak8:11 AM GMT+9')
})
