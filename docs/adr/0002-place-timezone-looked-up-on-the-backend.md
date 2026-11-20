# 2. The backend looks up a place's timezone and its date tonight

Date: 2026-11-20 · Status: accepted · Issue: #53

## Context

A Cosmic Report used to be computed in the browser's timezone, on the browser's date. The frontend
sent `Intl.DateTimeFormat().resolvedOptions().timeZone` and its own local date. Checking a friend's
sky several zones away (#17, user stories 8 and 9) went wrong because of this. The search for the
Viewing Window starts at local noon. For a place far to the east, the browser's noon already falls
in the place's darkness. Dusk was clamped to the search start, so the window was cut short or
shifted. Rise and set times were also shown on the viewer's clock, not the place's.

There were two ways to get the place's timezone. The backend could look it up from the latitude
and longitude. Or the client could send it, which would need its own lookup, since a geocoder like
Nominatim doesn't return one.

## Decision

- The backend looks the timezone up from the latitude and longitude, with `timezonefinder`
  (`app/place.py`). Its boundary data ships with the package, so the lookup is offline. Open ocean
  gets a nautical zone such as `Etc/GMT+9`.
- `POST /api/report` no longer takes a `timezone`, and one sent anyway is ignored. `date` is
  optional and defaults to today at the place, so the browser's date never decides which night it
  is.
- The response carries the `timezone` and `date` the night was computed for. The frontend shows
  every time in that zone. When the place's clock differs from the viewer's, the Viewing Window line
  names the zone (e.g. "local time (GMT+9)").

## Consequences

- One place to get the zone right, and no client can send a wrong one.
- The backend gains a dependency (~a few MB of boundary data, loaded once, on the first report).
- Timezone boundaries change now and then. Keeping `timezonefinder` current keeps them right.
