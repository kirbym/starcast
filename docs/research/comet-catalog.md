# Comet Catalog Research for StarCast

**Researched:** 2026-09-09  
**Sources:** Skyfield docs, Astropy/astroquery docs, JPL Horizons API, MPC data portal, Wikipedia (secondary, for names/magnitudes)

---

## Executive Summary

- **10–12 named comets** are worth including in a catalog for general-audience recognition; they split roughly evenly between short-period periodic comets (Halley, Encke, Ikeya–Zhang) and spectacular one-time or very-long-period apparitions (Hale-Bopp, Hyakutake, NEOWISE, West, Tsuchinshan-ATLAS, etc.).
- **Skyfield is the right primary library.** Its `skyfield.data.mpc` module provides `mpc.load_comets_dataframe()` and `mpc.comet_orbit()` that parse the MPC's `CometEls.txt` directly — no SPICE kernels needed for current-epoch comets.
- **Astroquery's `Horizons` class** (from the `astropy` ecosystem) is the best path when you need precise, server-side ephemerides or historical data not in the MPC file; it returns RA/Dec, magnitude, and heliocentric distance from JPL's server.
- **Non-perihelion comets should not be displayed as sky objects.** Halley at aphelion is magnitude 28 — detectable only by the Very Large Telescope. StarCast should show historical comets in a "legacy/lore" mode and flag any currently-near-perihelion comets dynamically from the live MPC feed.
- **Dynamic detection matters more than a static catalog.** The most spectacular recent comets (NEOWISE 2020, Tsuchinshan-ATLAS 2024) were not predictable far in advance; StarCast should query the live MPC `CometEls.txt` for any comet brighter than magnitude 6 on the requested date, then supplement with a static lore catalog for historical names.

---

## Recommended Named Comets

### Periodic Comets (return on a predictable schedule)

| Name | Designation | Period (yr) | Peak Magnitude at Perihelion | Next Perihelion | Notes |
|------|-------------|-------------|------------------------------|-----------------|-------|
| Halley's Comet | 1P/Halley | 74.7 | +2.1 (1986, unfavorable) | 28 Jul 2061 | Only known short-period comet consistently naked-eye visible; 1986 was worst possible geometry |
| Comet Encke | 2P/Encke | 3.3 | ~+4 to +6 (varies) | 10 Feb 2027 | Shortest period of any named comet; usually requires binoculars; spawns Taurid meteor shower |
| Ikeya–Zhang | 153P/Ikeya–Zhang | 365 | +2.9 (2002) | ~2362 | Longest period among numbered periodic comets; naked-eye in 2002; historical sightings back to 877 AD |

### Non-Periodic / Long-Period Comets (one-time or effectively one-time apparitions)

| Name | Designation | Year | Peak Magnitude | Notes |
|------|-------------|------|----------------|-------|
| Hale–Bopp | C/1995 O1 | 1997 | −1.8 | Naked-eye for ~18.5 months (record); next return ~4385; technically elliptical, period ~2,399 yr |
| Hyakutake | C/1996 B2 | 1996 | 0.0 | Passed 0.102 AU from Earth; ~3 months naked-eye but peak lasted only days; period ~70,000 yr post-encounter |
| NEOWISE | C/2020 F3 | 2020 | +0.5 to +1 | Naked-eye throughout July 2020; period ~6,700 yr; will not return on human timescales |
| Tsuchinshan-ATLAS | C/2023 A3 | 2024 | −4.9 | "Great Comet of 2024"; ~6 weeks naked-eye; outbound orbit hyperbolic — will never return |
| West | C/1975 V1 | 1976 | −3.0 | Daylight-visible 25–27 Feb 1976; fragmented into 4 pieces; period ~558,000 yr |
| Bennett | C/1969 Y1 | 1970 | 0.0 | Naked-eye Feb–May 1970; well-studied; period ~1,747 yr |
| Ikeya–Seki | C/1965 S1 | 1965 | −10.0 | "Great Comet of 1965"; Kreutz sungrazer; daylight visible; one of brightest in 1,000 yr; period ~795–946 yr |
| Lovejoy | C/2014 Q2 | 2015 | +4.0 | Weeks of naked-eye visibility Jan 2015; period ~8,000–11,000 yr |

### Excluded from Catalog

| Name | Reason |
|------|--------|
| Shoemaker–Levy 9 (D/1993 F2) | Never naked-eye from Earth; impacted Jupiter 1994; orbited Jupiter not Sun |
| Comet Kohoutek (C/1973 E1) | Famous for being over-hyped and under-performing; magnitude +3 at best but predicted −10; poor general-audience recognition for right reasons |

---

## Data Access in Python

### Option 1: Skyfield + MPC (Recommended for position computation)

Skyfield's `skyfield.data.mpc` module natively parses the MPC comet orbital element file.

**Data source:** `https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt`  
Also available compressed: `https://www.minorplanetcenter.net/Extended_Files/cometels.json.gz`

**Key functions (from `skyfield.data.mpc` module):**

```python
from skyfield.api import load, Loader
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005 as GM_SUN

load = Loader('~/.skyfield-data')
ts = load.timescale()
planets = load('de421.bsp')
sun = planets['sun']
earth = planets['earth']

# Download and parse MPC comet elements
with load.open(mpc.COMET_URL) as f:
    comets = mpc.load_comets_dataframe(f)

# Filter to a specific named comet
row = comets[comets['designation'] == 'C/1995 O1'].iloc[0]

# Build orbit object — IMPORTANT: comet orbits are heliocentric, not barycentric
comet = sun + mpc.comet_orbit(row, ts, GM_SUN)

# Observe from Earth at a given time
t = ts.utc(2061, 7, 28)
astrometric = earth.at(t).observe(comet)
ra, dec, distance = astrometric.radec()
```

**Critical note:** `mpc.comet_orbit()` returns a position relative to the Sun, so you **must** add `sun +` before it. Forgetting this gives positions relative to the Solar System barycenter (wrong by ~5 AU in the worst case).

**Three MPC loading functions exist:**
- `mpc.load_comets_dataframe(f)` — fast parser (preferred)
- `mpc.load_comets_dataframe_slow(f)` — slower fallback for edge-case files
- `mpc.load_mpcorb_dataframe(f)` — for asteroids/minor planets (not comets)

**Data format:** The MPC exports `CometEls.txt` in the IAU comet orbital elements format (fixed-width text). Fields include: perihelion distance (q), eccentricity (e), inclination, argument of perihelion, longitude of ascending node, perihelion epoch, and absolute magnitude parameters (H, G). Skyfield parses these into a Pandas DataFrame.

**File caching:** `load.open()` caches downloaded files locally. Pass `reload=True` to force re-download. The MPC updates `CometEls.txt` a few times per month as new comets are designated.

### Option 2: astroquery.jplhorizons (Recommended for current sky position with magnitude)

The `astroquery` package (Astropy ecosystem) wraps the JPL Horizons REST API at `https://ssd.jpl.nasa.gov/api/horizons.api`.

**Key class:** `astroquery.jplhorizons.Horizons`

**Key methods:**
- `.ephemerides()` — returns RA, Dec, apparent magnitude (V), heliocentric distance (r), geocentric distance (delta), and 60+ additional columns as an Astropy Table
- `.elements()` — returns orbital elements
- `.vectors()` — returns state vectors

```python
from astroquery.jplhorizons import Horizons

# Query Halley's Comet from a location (568 = Mauna Kea)
obj = Horizons(
    id='Halley',
    id_type='comet_name',
    location='568',
    epochs={'start': '2061-07-01', 'stop': '2061-09-01', 'step': '1d'}
)
eph = obj.ephemerides()
print(eph['datetime_str', 'RA', 'DEC', 'V', 'r', 'delta'])
```

**JPL Horizons API directly:** The raw REST endpoint is `GET https://ssd.jpl.nasa.gov/api/horizons.api` with parameters including `COMMAND` (comet name or designation), `EPHEM_TYPE` (OBSERVER/VECTORS/ELEMENTS), `START_TIME`, `STOP_TIME`, `STEP_SIZE`, `CENTER` (observer location), and `format` (json or text). No authentication required. No documented rate limits, but the API supports a maximum of 10,000 discrete time points per query.

### Comparison and Recommendation for StarCast

| | Skyfield + MPC | astroquery.jplhorizons |
|-|----------------|------------------------|
| **Setup** | `pip install skyfield pandas` | `pip install astroquery` |
| **Offline capable** | Yes (after initial download) | No (live API calls) |
| **Magnitude output** | No — must implement photometric formula separately | Yes — V magnitude returned directly |
| **Accuracy** | Good for general use | Highest (JPL DE ephemerides) |
| **Speed** | Fast (local computation) | Slower (HTTP round-trip) |
| **Live comet discovery** | Yes — re-download CometEls.txt | Yes — query by name/designation |

**Recommendation:** Use **Skyfield + MPC** as the primary path for position computation (RA/Dec, altitude/azimuth, rise/set times). Use **astroquery.jplhorizons** for magnitude, because MPC orbital elements include H and G parameters but the photometric model implementation is non-trivial and Horizons returns observed V magnitude directly. For the static lore catalog (historical comets not currently in the sky), no ephemeris call is needed — just store metadata.

---

## Non-Perihelion Visibility

### Typical Magnitudes

| Comet | Condition | Approximate Magnitude | Instrument needed |
|-------|-----------|-----------------------|-------------------|
| Halley (1P) | At perihelion (favorable) | +1 to +2 | Naked eye |
| Halley (1P) | At aphelion (~35 AU, 2003 obs.) | +28.2 | 8-m class telescope (VLT) |
| Hale-Bopp (C/1995 O1) | At 1997 perihelion | −1.8 | Naked eye |
| Hale-Bopp (C/1995 O1) | Far from Sun (current, ~50 AU) | >30 | Beyond current instrumentation |
| Hyakutake (C/1996 B2) | At perihelion approach | 0.0 | Naked eye |
| Encke (2P) | At perihelion | ~+4 to +6 | Naked eye to binoculars |
| Encke (2P) | At aphelion (~4.1 AU) | ~+15 | Large amateur telescope |
| Generic long-period comet | Far from Sun (>5 AU) | >+15 | Telescope |

### The Physics

Comet brightness scales approximately as the inverse square of heliocentric distance for reflected sunlight, but cometary activity (sublimation of volatile ices) drops off even faster — typically as r⁻⁴ or steeper. A comet at 35 AU (Halley's aphelion) receives ~1,225× less sunlight than at 1 AU, plus the coma and tail are absent entirely. The result is that Halley at aphelion (magnitude 28) requires a Very Large Telescope to detect; it is invisible to any amateur equipment.

The magnitude 28.2 observation for Halley in 2003 was made with three of ESO's Very Large Telescopes at Paranal, Chile — instrumentation unavailable to any general-audience sky-watcher.

### Recommendation for StarCast

**Do not display non-perihelion comets as sky objects.** Apply the following logic:

1. **Dynamic visibility check:** Query the live MPC `CometEls.txt` and compute each comet's predicted magnitude on the requested date. Only include a comet in the "visible tonight" results if it is brighter than magnitude 6.0 (naked-eye limit) or magnitude 10.5 (typical binocular limit, if StarCast supports binocular-tier results).

2. **Historical/lore mode:** Display the static catalog of famous named comets as historical entries — "Halley's Comet last appeared in 1986 and won't return until 2061" — without implying they are sky objects tonight. This satisfies the general-audience recognition factor without misleading users.

3. **Periodic comets near perihelion:** For periodic comets (Halley, Encke, Ikeya–Zhang), compute whether the current date is within ~6 months of perihelion. If yes, include them dynamically. If no, show only in lore mode.

4. **Encke caveat:** Although Encke returns every 3.3 years, it only occasionally reaches naked-eye brightness (~magnitude 4–6) during unusually favorable perihelion passages. Default to requiring a computed magnitude check rather than assuming it's always visible.

---

## Citations

1. **Skyfield Kepler Orbits documentation** — `mpc.load_comets_dataframe()`, `mpc.comet_orbit()`, `mpc.load_comets_dataframe_slow()`, Sun-centered orbit note:  
   https://rhodesmill.org/skyfield/kepler-orbits.html

2. **Skyfield API Reference** — `load_comets_dataframe`, `load_mpcorb_dataframe` listed under "Kepler orbit data":  
   https://rhodesmill.org/skyfield/api.html

3. **Skyfield planet ephemeris loading** — `.bsp` file format, `load()` function, JPL DE series context:  
   https://rhodesmill.org/skyfield/planets.html

4. **JPL Horizons REST API documentation** — endpoint, `COMMAND` parameter, `EPHEM_TYPE`, output formats, rate limits:  
   https://ssd-api.jpl.nasa.gov/doc/horizons.html

5. **Minor Planet Center data files** — `CometEls.txt`, `AllCometEls.txt`, JSON compressed format, download URLs:  
   https://www.minorplanetcenter.net/data

6. **MPC comet elements download (CometEls.txt)**:  
   https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt

7. **astroquery.jplhorizons documentation** — `Horizons` class, `.ephemerides()`, `.elements()`, `.vectors()`, `id_type='comet_name'`, returned columns including V magnitude:  
   https://astroquery.readthedocs.io/en/latest/jplhorizons/jplhorizons.html

8. **Wikipedia: Halley's Comet** — 74.7-yr period, +2.1 magnitude (1986), magnitude 28.2 at aphelion (2003 VLT observation), next perihelion 28 Jul 2061:  
   https://en.wikipedia.org/wiki/Halley%27s_Comet

9. **Wikipedia: Comet Hale–Bopp** — C/1995 O1, peak magnitude −1.8, 18.5 months naked-eye, period ~2,399 yr, next return ~4385:  
   https://en.wikipedia.org/wiki/Comet_Hale%E2%80%93Bopp

10. **Wikipedia: Comet Hyakutake** — C/1996 B2, peak magnitude 0.0, ~3 months visible, eccentricity 0.99989, period ~70,000 yr post-encounter:  
    https://en.wikipedia.org/wiki/Comet_Hyakutake

11. **Wikipedia: Comet NEOWISE** — C/2020 F3, peak magnitude +0.5 to +1, naked-eye through July 2020, period ~6,700 yr:  
    https://en.wikipedia.org/wiki/Comet_NEOWISE

12. **Wikipedia: C/2023 A3 (Tsuchinshan-ATLAS)** — peak magnitude −4.9, ~6 weeks naked-eye (Sep–Nov 2024), outbound hyperbolic — will not return:  
    https://en.wikipedia.org/wiki/C/2023_A3

13. **Wikipedia: Comet West** — C/1975 V1, peak magnitude −3.0, daylight visible Feb 1976, period ~558,000 yr:  
    https://en.wikipedia.org/wiki/Comet_West

14. **Wikipedia: Comet Bennett** — C/1969 Y1, peak magnitude 0.0, naked-eye Feb–May 1970, period ~1,747 yr:  
    https://en.wikipedia.org/wiki/Comet_Bennett

15. **Wikipedia: Comet Ikeya–Seki** — C/1965 S1, peak magnitude −10.0, daylight visible Oct 1965, Kreutz sungrazer, period ~795–946 yr:  
    https://en.wikipedia.org/wiki/Comet_Ikeya%E2%80%93Seki

16. **Wikipedia: C/2014 Q2 (Lovejoy)** — peak magnitude +4.0, naked-eye Jan 2015, eccentricity 0.99811, period ~8,000–11,000 yr:  
    https://en.wikipedia.org/wiki/C/2014_Q2

17. **Wikipedia: 2P/Encke** — 3.304-yr period, spawns Taurid meteor shower, next perihelion 10 Feb 2027:  
    https://en.wikipedia.org/wiki/2P/Encke

18. **Wikipedia: 153P/Ikeya–Zhang** — 365.49-yr period, peak magnitude +2.9 (2002), next return ~2362:  
    https://en.wikipedia.org/wiki/153P/Ikeya%E2%80%93Zhang
