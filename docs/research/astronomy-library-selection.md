# Astronomy Library Selection for StarCast

**Research date:** 2026-09-09
**Scope:** Python astronomy library evaluation for a FastAPI app that computes celestial visibility for a given lat/lon + date.

---

## Recommendation

**Use Skyfield as the primary library, with Astropy's `get_constellation()` for constellation identification.**

Skyfield covers 8 of 9 requirements natively and is the only library the PyEphem maintainer himself recommends for new projects. The one gap — constellation identification by RA/Dec — is filled by a single Astropy function (`astropy.coordinates.get_constellation`) that requires no additional data files. PyEphem is not recommended for new projects (see § PyEphem below).

**Minimal dependency set:**

| Package | Role |
|---|---|
| `skyfield` | Planets, Moon, stars, comets, rise/set, twilight, conjunctions, oppositions, angular separation |
| `astropy` | `get_constellation()` only (IAU 88-constellation lookup from RA/Dec) |

**Required data files (downloaded at first use, then cached):**

| File | Size | Purpose |
|---|---|---|
| `de440s.bsp` | ~32 MB | JPL planetary/lunar ephemeris 1849–2150 (recommended over DE421) |
| `hipparcos.hdf` | ~47 MB | 118,218-star catalog (Hipparcos) for named-star lookups |
| `CometEls.txt` | ~3 MB (updates weekly) | MPC comet orbital elements for named-comet positions |

---

## Comparison Table

| Requirement | Skyfield | Astropy | PyEphem |
|---|---|---|---|
| 1. Planets (all 8) + Moon | **Native** — via DE440s.bsp; `planets['Mars Barycenter']` | **Native** — `get_body('mars', time, location)` via JPL DE430 | Native — `ephem.Mars()`, but ~1 arcsec accuracy |
| 2. Named constellations (88 IAU) | **Gap** — no built-in constellation lookup | **Native** — `get_constellation(coord)` using Delporte/IAU boundaries | **Native** — `ephem.constellation()` |
| 3. Bright named stars | **Native** — Hipparcos catalog via `Star.from_dataframe()`; lookup by HIP number or name | **Native** — `SkyCoord.from_name()` via SIMBAD (requires network); or load Hipparcos manually | Partial — built-in bright-star catalog; limited entries |
| 4. Large named comets | **Native** — MPC `CometEls.txt` via `mpc.load_comets_dataframe()`; Halley and Hale-Bopp confirmed by name in docs | Not built-in; requires loading orbital elements manually | Partial — `EllipticalBody`/`HyperbolicBody` accept orbital elements but no automatic MPC fetch |
| 5. Messier DSOs (M1–M110) | **Via fixed RA/Dec** — no dedicated catalog; use `Star(ra_hours=..., dec_degrees=...)` with a bundled lookup table | **Via fixed RA/Dec** — `SkyCoord` with fixed coordinates | Manual RA/Dec only — `FixedBody` |
| 6. Conjunction detection (angular separation) | **Native** — `position.separation_from(other)` returns `Angle`; `find_discrete()` for event search | **Native** — `coord1.separation(coord2)` returns `Angle`; no built-in event-search loop | **Native** — `ephem.separation()` |
| 7. Planetary oppositions | **Native** — `almanac.oppositions_conjunctions(eph, body)` + `find_discrete()` | Not built-in; requires manual elongation computation | Not built-in |
| 8. Astronomical twilight times | **Native** — `almanac.dark_twilight_day()` returns 0–4 illumination codes; use `find_discrete()` for precise timestamps | Partial — AltAz transform gives Sun altitude; no dedicated twilight event finder | Partial — `Observer.next_rising(sun, horizon='-18')` workaround |
| 9. lat/lon + date input | **Native** — `wgs84.latlon(lat, lon)`, `ts.utc(year, month, day)` | **Native** — `EarthLocation(lat=, lon=)`, `Time(...)` | **Native** — `Observer.lat`, `Observer.lon`, `Observer.date` |

**Legend:** Native = documented, first-party API. Partial = possible with workarounds. Gap = not supported natively.

---

## Library Details

### Skyfield

**Source:** https://rhodesmill.org/skyfield/

Skyfield is a pure-Python library (no C extension — installs cleanly via pip/uv) that computes high-precision positions for solar system bodies and stars. It wraps the ERFA library internally and can consume NASA/JPL SPICE kernel (`.bsp`) files directly.

**Accuracy:** Agrees with USNO to within 0.00001 arcseconds for planets. Inner planets reach sub-kilometer positional accuracy; outer planets (Neptune) are limited to several thousand kilometers — sufficient for all StarCast use cases.

#### Requirement coverage details

**Planets + Moon (Req 1)**

Loaded from a JPL `.bsp` ephemeris file. Recommended file is `de440s.bsp` (2020, covers 1849–2150, ~32 MB), which supersedes the older DE421 and DE430. Body names follow SPK convention: `'Mars Barycenter'`, `'Earth'`, `'Moon'`, etc.

```python
from skyfield.api import load
ts = load.timescale()
planets = load('de440s.bsp')
earth, mars = planets['Earth'], planets['Mars Barycenter']
t = ts.utc(2026, 9, 9)
astrometric = earth.at(t).observe(mars)
alt, az, distance = astrometric.apparent().altaz()
```

Source: https://rhodesmill.org/skyfield/planets.html

---

**Constellations (Req 2) — Gap; use Astropy**

Skyfield has no constellation-lookup function. Angular positions can be computed and output as RA/Dec, but mapping RA/Dec to constellation name is out of scope for Skyfield. Use Astropy's `get_constellation()` (see Astropy section).

Source: https://rhodesmill.org/skyfield/positions.html (no constellation functionality documented)

---

**Named stars (Req 3)**

Loaded from the Hipparcos catalog (`hipparcos.hdf`, ~47 MB). Access individual stars by HIP catalog number via `Star.from_dataframe(df.loc[87937])`. Bulk loading supports the full 118,218-star catalog. Note: 263 stars have `nan` positions and must be filtered. Named star lookup requires resolving a common name (e.g., "Sirius" → HIP 32349) — a small bundled lookup table handles this.

Source: https://rhodesmill.org/skyfield/stars.html

---

**Named comets (Req 4)**

Fetched from MPC's `CometEls.txt` via `mpc.load_comets_dataframe()`. Named comets such as `'1P/Halley'` and `'C/1995 O1 (Hale-Bopp)'` are confirmed accessible by name in the official docs. The underlying Kepler orbit routines are documented as "rudimentary and subject to change" — only the public `mpc` API surface is guaranteed stable.

Source: https://rhodesmill.org/skyfield/kepler-orbits.html

---

**Messier DSOs (Req 5)**

No dedicated Messier catalog exists in Skyfield. DSOs are treated as fixed points and instantiated with `Star(ra_hours=..., dec_degrees=...)`. StarCast must bundle a 110-row lookup table (M-number → RA/Dec epoch J2000). This is a one-time build artifact, not a runtime data download.

---

**Conjunction detection (Req 6)**

`position.separation_from(other_position)` returns a Skyfield `Angle`. For event-finding (detecting the moment of closest approach over a time window), combine with `find_minima()`:

```python
from skyfield.api import load
from skyfield.almanac import find_minima

# separation function
def angle(t):
    a = earth.at(t).observe(venus).apparent()
    b = earth.at(t).observe(jupiter).apparent()
    return a.separation_from(b).degrees

angle.step_days = 1.0
times, values = find_minima(t0, t1, angle)
```

Source: https://rhodesmill.org/skyfield/positions.html, https://rhodesmill.org/skyfield/searches.html

---

**Planetary oppositions (Req 7)**

`almanac.oppositions_conjunctions(eph, target_body)` generates a discrete state function. Pass to `find_discrete(t0, t1, fn)` to get timestamps and event labels (0 = conjunction, 1 = opposition).

Source: https://rhodesmill.org/skyfield/almanac.html

---

**Astronomical twilight times (Req 8)**

`almanac.dark_twilight_day(eph, observer_topos)` returns a function that yields integer codes at any time:

- `0` = astronomical night (dark; Sun below −18°)
- `1` = astronomical twilight (Sun between −18° and −12°)
- `2` = nautical twilight (Sun between −12° and −6°)
- `3` = civil twilight (Sun between −6° and 0°)
- `4` = full daylight

Combine with `find_discrete(t0, t1, fn)` to find the precise start/end of the dark window for any night.

Source: https://rhodesmill.org/skyfield/api-almanac.html

---

**lat/lon + date input (Req 9)**

```python
from skyfield.api import wgs84, load
ts = load.timescale()
observer = wgs84.latlon(latitude_degrees=34.05, longitude_degrees=-118.24)
t = ts.utc(2026, 9, 9, 4, 0)  # UTC midnight
```

Source: https://rhodesmill.org/skyfield/

---

### Astropy

**Source:** https://docs.astropy.org/en/stable/

Astropy is a comprehensive astronomy toolkit. For StarCast it is used for exactly one thing — IAU constellation lookup — which Skyfield does not provide.

#### Constellation lookup (Req 2 — fills Skyfield gap)

`astropy.coordinates.get_constellation(coord, short_name=False, constellation_list='iau')` returns the IAU constellation name (or 3-letter abbreviation) for any SkyCoord. Uses the Delporte 1930 boundaries precessed to B1875, as tabulated by Roman 1987 — the authoritative IAU standard used in all modern atlases. Works on scalar or array inputs. **No extra data file download required** — the boundary table is bundled inside the `astropy` package.

```python
from astropy.coordinates import SkyCoord, get_constellation
import astropy.units as u

coord = SkyCoord(ra=83.82*u.degree, dec=-5.39*u.degree)
name = get_constellation(coord)             # 'Orion'
abbr = get_constellation(coord, short_name=True)  # 'Ori'
```

Source: https://docs.astropy.org/en/stable/api/astropy.coordinates.get_constellation.html

#### Other Astropy capabilities (reference only)

- **Angular separation:** `skycoord1.separation(skycoord2)` returns an `Angle` via great-circle calculation, auto-converting frames. Source: https://docs.astropy.org/en/stable/coordinates/matchsep.html
- **Solar system bodies:** `get_body('mars', time, location)` via JPL DE430 (115 MB) or built-in ERFA ephemeris (low precision — up to 71 arcsec error for Jupiter). Source: https://docs.astropy.org/en/stable/coordinates/solarsystem.html
- **Coordinate frames:** AltAz, ICRS, FK5, Galactic and more. Source: https://docs.astropy.org/en/stable/coordinates/index.html
- **Time:** `astropy.time.Time` supports UTC, TDB, TT, UT1; sub-nanosecond precision. Source: https://docs.astropy.org/en/stable/time/index.html

**Astropy gaps for StarCast:**
- No built-in rise/set or twilight event finder
- No opposition/conjunction event finder
- No MPC comet catalog loader
- No Hipparcos catalog loader (network-dependent `from_name()` is unsuitable for production)

---

### PyEphem

**Source:** https://rhodesmill.org/pyephem/  
**Quick reference:** https://rhodesmill.org/pyephem/quick.html

PyEphem predates modern Python astronomy tooling. Its maintainer (Brandon Rhodes — the same person who wrote Skyfield) explicitly states in the PyEphem documentation:

> "The Skyfield astronomy library should be preferred over PyEphem for new projects."

**Do not use PyEphem for StarCast.** Key reasons:

1. **Accuracy ceiling:** ~1 arcsecond, based on 1980s astronomical techniques. Skyfield achieves 0.00001 arcsecond agreement with USNO.
2. **Confusing API:** Angle values behave differently when printed vs. used mathematically; floats are treated as radians, strings as degrees — inconsistent throughout the library.
3. **Maintenance mode:** Only critical bugfixes; development is effectively frozen.
4. **C dependency:** Requires a compiled C extension, which complicates Docker/serverless deployment. Skyfield is pure Python.

PyEphem does have a `constellation()` function and `separation()` function, but both requirements are better served by Astropy and Skyfield respectively.

Source: https://rhodesmill.org/pyephem/

---

## Supplemental Data Files and Catalogs

| File | Source URL | Size | How to obtain | Required for |
|---|---|---|---|---|
| `de440s.bsp` | NASA JPL via Skyfield | ~32 MB | `load('de440s.bsp')` auto-downloads on first call | Planets, Moon, oppositions, twilight |
| `hipparcos.hdf` | ESA/Skyfield | ~47 MB | `load.open('hipparcos.hdf')` auto-downloads | Named stars |
| `CometEls.txt` | MPC (updates weekly) | ~3 MB | `mpc.load_comets_dataframe()` auto-downloads | Named comets |
| Messier catalog | Bundle with StarCast | <5 KB | Write a 110-row dict or CSV (M-number → RA/Dec J2000) | DSO M1–M110 positions |
| IAU name → HIP table | IAU WGSN list | <50 KB | Download from https://www.iau.org/public/themes/naming_stars/ | Named-star lookup by common name |

Data files are downloaded by Skyfield's `load` helper on first run and cached locally. In a container or serverless environment, pre-populate a persistent volume with these files at build/deploy time to avoid cold-start latency.

---

## Sources Cited

| Claim | Primary Source URL |
|---|---|
| Skyfield overview, DE421/DE440 support, `wgs84.latlon()` API | https://rhodesmill.org/skyfield/ |
| Skyfield planet API, ephemeris file selection, accuracy table | https://rhodesmill.org/skyfield/planets.html |
| Skyfield star / Hipparcos catalog API, 263 nan entries caveat | https://rhodesmill.org/skyfield/stars.html |
| Skyfield almanac: rise/set, twilight, oppositions | https://rhodesmill.org/skyfield/almanac.html |
| Skyfield almanac API reference (function signatures and return codes) | https://rhodesmill.org/skyfield/api-almanac.html |
| Skyfield comet/MPC catalog API, Halley and Hale-Bopp confirmed by name | https://rhodesmill.org/skyfield/kepler-orbits.html |
| Skyfield `separation_from()` — no constellation support confirmed | https://rhodesmill.org/skyfield/positions.html |
| Skyfield event searching (`find_discrete`, `find_maxima`, `find_minima`) | https://rhodesmill.org/skyfield/searches.html |
| Astropy `get_constellation()` — IAU Delporte boundaries, Roman 1987 | https://docs.astropy.org/en/stable/api/astropy.coordinates.get_constellation.html |
| Astropy `SkyCoord.separation()` — angular separation | https://docs.astropy.org/en/stable/coordinates/matchsep.html |
| Astropy solar system: `get_body()`, DE430 accuracy table (71 arcsec Jupiter) | https://docs.astropy.org/en/stable/coordinates/solarsystem.html |
| Astropy coordinate frames (AltAz, ICRS, `SkyCoord.get_constellation()`) | https://docs.astropy.org/en/stable/coordinates/index.html |
| Astropy time scales (UTC, TDB, TT, UT1, sub-nanosecond precision) | https://docs.astropy.org/en/stable/time/index.html |
| PyEphem: "Skyfield should be preferred for new projects" | https://rhodesmill.org/pyephem/ |
| PyEphem: full API (constellation, separation, rise/set, comet classes) | https://rhodesmill.org/pyephem/quick.html |
