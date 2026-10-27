# Meteor Shower Calendar Data Sources — Research Findings

**Date of research:** 2026-09-09  
**Purpose:** Evaluate data sources for detecting active meteor shower windows in the StarCast FastAPI night-sky app.

> **Provenance:** This research was completed on 2026-09-09 and posted as the resolution of [#6](https://github.com/kirbym/starcast/issues/6), but the file was never committed alongside the other research docs. It is restored here verbatim from that comment, with only this note added.
>
> **Threshold note (added 2026-10-27):** Significant Event detection was later locked at ZHR ≥ 20 within ±2 days of peak ([#9](https://github.com/kirbym/starcast/issues/9)), not the `min_zhr = 5` / full-active-window logic sketched below. Against the table below, only the Quadrantids, Eta Aquariids, Southern Delta Aquariids, Perseids, Orionids and Geminids can ever qualify; the Daytime Arietids (ZHR 30) are excluded as a daytime shower. The other showers are still worth carrying in the data file for narration context.

---

## Summary and Recommendations

### Best source
The **IMO (International Meteor Organization) Annual Meteor Shower Calendar** is the gold standard — it is published every year by meteor-science experts, freely downloadable as a PDF, citable in academic and application contexts, and is what essentially every astronomy app, planetarium, and news outlet references. The authoritative mirror for programmatic data is the **IAU Meteor Data Center (MDC)** at the Slovak Academy of Sciences, which publishes machine-readable text/CSV files.

**Important note as of September 2026:** The IMO website (imo.net) and the AMS website (amsmeteors.org) are **currently offline** due to a cyberattack. Their PDF calendars are still linked from search results and some mirrors, but the main site pages are unreachable. Plan for this: do not depend on live scraping of either site.

### Storage recommendation
**Hardcode the data as a JSON file loaded at startup.** The annual calendar changes only slightly year to year (peak dates shift by ±1 day due to Earth's orbital mechanics; ZHR values are stable). A `data/meteor_showers.json` file checked into the repo is the right approach:

- It is version-controlled and auditable.
- No network dependency at runtime.
- Easy to update once per year when the new IMO calendar is released.
- The app loads it once at startup (or imports a Python dict directly from a `.py` constants file).

Do **not** try to scrape imo.net or amsmeteors.org at runtime — both have demonstrated vulnerability to extended downtime.

---

## Q1: Best Freely-Usable, Citable Source — and Machine-Readable Availability

### Primary Sources Evaluated

| Source | URL | Status | Machine-Readable? |
|---|---|---|---|
| IMO Annual Calendar | https://www.imo.net/resources/calendar/ | Offline (cyberattack, Sept 2026) | PDF only (annual) |
| IMO Calendar PDFs | https://www.imo.net/files/meteor-shower/cal2026.pdf | Redirects to outage notice | PDF (when available) |
| AMS Meteor Shower Calendar | https://www.amsmeteors.org/meteor-showers/meteor-shower-calendar/ | Offline (same cyberattack) | HTML table (when available) |
| NASA Meteor Showers | https://science.nasa.gov/solar-system/meteors-meteorites/meteor-showers/ | Live | HTML only, no ZHR |
| IAU Meteor Data Center (MDC) | https://www.ta3.sk/IAUC22DB/MDC2022/ | Live | **Text/CSV download** |
| Wikipedia: List of Meteor Showers | https://en.wikipedia.org/wiki/List_of_meteor_showers | Live | HTML table, good data |
| space-calendar (GitHub) | https://github.com/lkorth/space-calendar | Live | **JSON API** (MIT license) |
| gmn-python-api | https://pypi.org/project/gmn-python-api/ | Live | Python/DataFrames (MIT) |

### Verdict

1. **IMO PDF calendar** — the most authoritative citation. Use it as the annual reference for updating your hardcoded data. Citation format: "IMO Meteor Shower Calendar [year], ed. Jürgen Rendtel, International Meteor Organization."

2. **IAU Meteor Data Center** — the canonical machine-readable source. Established showers text file: `https://www.ta3.sk/IAUC22DB/MDC2022/Etc/streamestablisheddata2026.txt`. Contains IAU numbers, codes, solar longitude ranges, radiant coordinates, and velocity. Does **not** include human-readable calendar dates (uses solar longitude instead) or ZHR — those come from the IMO.

3. **space-calendar JSON API** (`https://space-calendar.lukekorth.com/feed.json?c=meteor-showers`) — MIT licensed, returns peak nights. Does not include ZHR or active windows. Useful for event listing, not window detection.

4. **Wikipedia** — reliable for cross-checking individual shower data (active dates, ZHR, parent body). Not appropriate as a production data source but excellent for verification.

**For the StarCast app:** pull the IMO PDF once per year and encode the data into `data/meteor_showers.json`. The IAU MDC text file can serve as a secondary cross-reference for IAU codes and radiant data.

---

## Q2: Major Annual Meteor Showers — Complete Data Table

Sources: Wikipedia List of Meteor Showers (https://en.wikipedia.org/wiki/List_of_meteor_showers), individual Wikipedia shower articles, IMO Calendar data, NASA Science pages, and IAU MDC text file (https://www.ta3.sk/IAUC22DB/MDC2022/Etc/streamestablisheddata2026.txt).

### Top 12 Major Showers

| # | Name | IAU Code | Active Start | Active End | Peak Date | ZHR | Velocity (km/s) | Parent Body |
|---|---|---|---|---|---|---|---|---|
| 1 | Quadrantids | QUA | Dec 28 | Jan 12 | Jan 3–4 | 110–120 | 41 | Asteroid 2003 EH1 |
| 2 | April Lyrids | LYR | Apr 14 | Apr 30 | Apr 22–23 | 18 | 49 | C/1861 G1 (Thatcher) |
| 3 | Eta Aquariids | ETA | Apr 19 | May 28 | May 5–6 | 55 | 66 | 1P/Halley |
| 4 | Daytime Arietids | ARI | May 14 | Jun 24 | Jun 7 | 30 (daytime) | 38 | Asteroid 1566 Icarus |
| 5 | Southern Delta Aquariids | SDA | Jul 12 | Aug 23 | Jul 30–31 | 25 | 41 | 342P/SOHO |
| 6 | Alpha Capricornids | CAP | Jul 3 | Aug 15 | Jul 30–31 | 5 | 23 | 169P/NEAT |
| 7 | Perseids | PER | Jul 17 | Aug 24 | Aug 12–13 | 100 | 59 | 109P/Swift-Tuttle |
| 8 | October Draconids | DRA | Oct 6 | Oct 10 | Oct 8–9 | 5–10 | 20 | 21P/Giacobini-Zinner |
| 9 | Orionids | ORI | Oct 2 | Nov 7 | Oct 21–22 | 20 | 66 | 1P/Halley |
| 10 | Leonids | LEO | Nov 6 | Nov 30 | Nov 17–18 | 15 | 71 | 55P/Tempel-Tuttle |
| 11 | Geminids | GEM | Dec 4 | Dec 17 | Dec 13–14 | 120–150 | 35 | Asteroid 3200 Phaethon |
| 12 | Ursids | URS | Dec 17 | Dec 26 | Dec 22–23 | 10 | 33 | 8P/Tuttle |

### Extended Showers (notable secondaries)

| # | Name | IAU Code | Active Start | Active End | Peak Date | ZHR | Velocity (km/s) | Parent Body |
|---|---|---|---|---|---|---|---|---|
| 13 | Southern Taurids | STA | Sep 10 | Dec 10 | Nov 5 | 5–7 | 27 | 2P/Encke |
| 14 | Northern Taurids | NTA | Oct 20 | Dec 10 | Nov 12 | 5 | 29 | 2004 TG10 |
| 15 | Sigma Hydrids | HYD | Dec 3 | Dec 20 | Dec 9 | 7 | 58 | C/2023 P1 (Nishimura) |
| 16 | Pi Puppids | PPU | Apr 15 | Apr 28 | Apr 24 | Variable | 18 | 26P/Grigg-Skjellerup |
| 17 | June Bootids | JBO | Jun 22 | Jul 2 | Jun 27 | Variable | 18 | 7P/Pons-Winnecke |
| 18 | Aurigids | AUR | Aug 28 | Sep 5 | Sep 1 | 6 | 66 | C/1911 N1 (Kiess) |
| 19 | September Epsilon Perseids | SPE | Sep 5 | Sep 21 | Sep 9 | 8 | 64 | Unknown |
| 20 | Alpha Monocerotids | AMO | Nov 15 | Nov 25 | Nov 22 | Variable | 65 | Unknown |
| 21 | Phoenicids | PHO | Dec 1 | Dec 5 | Dec 2 | Variable | 15 | 289P/Blanpain |
| 22 | Comae Berenicids | COM | Dec 4 | Jan 30 | Dec 23 | 3 | 65 | Unknown |

**Notes on ZHR:**
- "Variable" showers can produce outbursts ranging from near-zero to hundreds per hour depending on orbital geometry.
- Draconids have produced storms (thousands/hr) in 1933, 1946 and modest outbursts in 2011; annual base rate is ~5.
- Leonids produce storms (>1000/hr) every ~33 years aligned with Tempel-Tuttle perihelion; next major storm not expected until ~2031–2032.
- Quadrantids have a very sharp peak (~6 hours FWHM) so the ZHR is highly sensitive to observation timing.

---

## Q3: Data Fields Needed Per Shower Entry

### Recommended Field Schema

| Field | Type | Why It's Needed |
|---|---|---|
| `name` | string | Display name in UI and narrator prompt |
| `iau_code` | string (3 chars) | Canonical identifier; cross-references IAU MDC |
| `iau_number` | int | Numeric IAU identifier for database lookups |
| `active_start` | `{month: int, day: int}` | Determines if "tonight" is within the active window |
| `active_end` | `{month: int, day: int}` | End of active window (inclusive) |
| `peak_month` | int | Month of peak (for display and ranking) |
| `peak_day` | int | Day of peak |
| `peak_day_end` | int or null | Some peaks span 2 days (e.g., Aug 12–13); null if single day |
| `zhr` | int or string | Zenithal Hourly Rate; string for "Variable"; used to rank significance |
| `zhr_note` | string or null | E.g., "storm potential", "sharp 6-hr peak", "outburst possible" |
| `velocity_kms` | float | Entry velocity; higher = brighter streaks, relevant for narrator |
| `parent_body` | string | Comet or asteroid name; flavor text for narrator |
| `radiant_constellation` | string | E.g., "Perseus"; used in display ("meteors appear to radiate from Perseus") |
| `hemisphere_note` | string or null | E.g., "Best from Southern Hemisphere" (Eta Aquariids) |
| `daytime` | bool | True if shower peaks during daytime (e.g., Arietids); skip for night-sky app |

### Field Priority for "Significant Events" Trigger

For the StarCast window-detection logic, the minimum viable fields are:

1. `active_start` + `active_end` — to answer "is tonight in the window?"
2. `peak_month` + `peak_day` — to compute days-to-peak and days-since-peak
3. `zhr` — to set a significance threshold (e.g., only trigger if ZHR ≥ 10)
4. `name` — for display
5. `hemisphere_note` — to suppress or qualify for user's hemisphere

---

## Recommended Python Data Structure

### Option A: Inline Python dict (for small teams, simple updates)

```python
# starcast/data/meteor_showers.py
# Source: IMO Meteor Shower Calendar (annual, ed. Jürgen Rendtel)
# Cross-referenced: Wikipedia List of Meteor Showers, IAU MDC
# Last updated: 2026 calendar year

METEOR_SHOWERS = [
    {
        "name": "Quadrantids",
        "iau_code": "QUA",
        "iau_number": 10,
        "active_start": {"month": 12, "day": 28},
        "active_end": {"month": 1, "day": 12},
        "peak_month": 1,
        "peak_day": 3,
        "peak_day_end": 4,
        "zhr": 120,
        "zhr_note": "Very sharp peak (~6 hours FWHM); ZHR depends heavily on peak timing",
        "velocity_kms": 41.0,
        "parent_body": "Asteroid 2003 EH1",
        "radiant_constellation": "Boötes",
        "hemisphere_note": "Best from Northern Hemisphere",
        "daytime": False,
    },
    {
        "name": "April Lyrids",
        "iau_code": "LYR",
        "iau_number": 6,
        "active_start": {"month": 4, "day": 14},
        "active_end": {"month": 4, "day": 30},
        "peak_month": 4,
        "peak_day": 22,
        "peak_day_end": 23,
        "zhr": 18,
        "zhr_note": None,
        "velocity_kms": 49.0,
        "parent_body": "C/1861 G1 (Thatcher)",
        "radiant_constellation": "Lyra",
        "hemisphere_note": None,
        "daytime": False,
    },
    {
        "name": "Eta Aquariids",
        "iau_code": "ETA",
        "iau_number": None,  # Not in standard IAU established list under this code
        "active_start": {"month": 4, "day": 19},
        "active_end": {"month": 5, "day": 28},
        "peak_month": 5,
        "peak_day": 5,
        "peak_day_end": 6,
        "zhr": 55,
        "zhr_note": None,
        "velocity_kms": 66.0,
        "parent_body": "1P/Halley",
        "radiant_constellation": "Aquarius",
        "hemisphere_note": "Best from Southern Hemisphere and tropics; low from northern mid-latitudes",
        "daytime": False,
    },
    {
        "name": "Southern Delta Aquariids",
        "iau_code": "SDA",
        "iau_number": 5,
        "active_start": {"month": 7, "day": 12},
        "active_end": {"month": 8, "day": 23},
        "peak_month": 7,
        "peak_day": 30,
        "peak_day_end": 31,
        "zhr": 25,
        "zhr_note": None,
        "velocity_kms": 41.0,
        "parent_body": "342P/SOHO",
        "radiant_constellation": "Aquarius",
        "hemisphere_note": "Best from Southern Hemisphere",
        "daytime": False,
    },
    {
        "name": "Alpha Capricornids",
        "iau_code": "CAP",
        "iau_number": 1,
        "active_start": {"month": 7, "day": 3},
        "active_end": {"month": 8, "day": 15},
        "peak_month": 7,
        "peak_day": 30,
        "peak_day_end": 31,
        "zhr": 5,
        "zhr_note": "Produces occasional bright fireballs",
        "velocity_kms": 23.0,
        "parent_body": "169P/NEAT",
        "radiant_constellation": "Capricornus",
        "hemisphere_note": None,
        "daytime": False,
    },
    {
        "name": "Perseids",
        "iau_code": "PER",
        "iau_number": 7,
        "active_start": {"month": 7, "day": 17},
        "active_end": {"month": 8, "day": 24},
        "peak_month": 8,
        "peak_day": 12,
        "peak_day_end": 13,
        "zhr": 100,
        "zhr_note": "Most popular shower of the year; broad peak (~2 days)",
        "velocity_kms": 59.0,
        "parent_body": "109P/Swift-Tuttle",
        "radiant_constellation": "Perseus",
        "hemisphere_note": "Best from Northern Hemisphere",
        "daytime": False,
    },
    {
        "name": "October Draconids",
        "iau_code": "DRA",
        "iau_number": 9,
        "active_start": {"month": 10, "day": 6},
        "active_end": {"month": 10, "day": 10},
        "peak_month": 10,
        "peak_day": 8,
        "peak_day_end": 9,
        "zhr": 10,
        "zhr_note": "Storm potential in years of parent comet perihelion passage",
        "velocity_kms": 20.0,
        "parent_body": "21P/Giacobini-Zinner",
        "radiant_constellation": "Draco",
        "hemisphere_note": "Best from Northern Hemisphere",
        "daytime": False,
    },
    {
        "name": "Orionids",
        "iau_code": "ORI",
        "iau_number": 8,
        "active_start": {"month": 10, "day": 2},
        "active_end": {"month": 11, "day": 7},
        "peak_month": 10,
        "peak_day": 21,
        "peak_day_end": 22,
        "zhr": 20,
        "zhr_note": None,
        "velocity_kms": 66.0,
        "parent_body": "1P/Halley",
        "radiant_constellation": "Orion",
        "hemisphere_note": None,
        "daytime": False,
    },
    {
        "name": "Southern Taurids",
        "iau_code": "STA",
        "iau_number": 2,
        "active_start": {"month": 9, "day": 10},
        "active_end": {"month": 12, "day": 10},
        "peak_month": 11,
        "peak_day": 5,
        "peak_day_end": None,
        "zhr": 7,
        "zhr_note": "Known for bright fireballs; often overlaps with Northern Taurids",
        "velocity_kms": 27.0,
        "parent_body": "2P/Encke",
        "radiant_constellation": "Taurus",
        "hemisphere_note": None,
        "daytime": False,
    },
    {
        "name": "Northern Taurids",
        "iau_code": "NTA",
        "iau_number": 17,
        "active_start": {"month": 10, "day": 20},
        "active_end": {"month": 12, "day": 10},
        "peak_month": 11,
        "peak_day": 12,
        "peak_day_end": None,
        "zhr": 5,
        "zhr_note": "Often produces bright fireballs; overlaps with Southern Taurids",
        "velocity_kms": 29.0,
        "parent_body": "2P/Encke (stream fragment 2004 TG10)",
        "radiant_constellation": "Taurus",
        "hemisphere_note": None,
        "daytime": False,
    },
    {
        "name": "Leonids",
        "iau_code": "LEO",
        "iau_number": 13,
        "active_start": {"month": 11, "day": 6},
        "active_end": {"month": 11, "day": 30},
        "peak_month": 11,
        "peak_day": 17,
        "peak_day_end": 18,
        "zhr": 15,
        "zhr_note": "Storm potential (~1000+/hr) near 55P perihelion; next major storm ~2031–2032",
        "velocity_kms": 71.0,
        "parent_body": "55P/Tempel-Tuttle",
        "radiant_constellation": "Leo",
        "hemisphere_note": None,
        "daytime": False,
    },
    {
        "name": "Geminids",
        "iau_code": "GEM",
        "iau_number": 4,
        "active_start": {"month": 12, "day": 4},
        "active_end": {"month": 12, "day": 17},
        "peak_month": 12,
        "peak_day": 13,
        "peak_day_end": 14,
        "zhr": 150,
        "zhr_note": "Strongest annual shower; parent is an asteroid, not a comet",
        "velocity_kms": 35.0,
        "parent_body": "Asteroid 3200 Phaethon",
        "radiant_constellation": "Gemini",
        "hemisphere_note": None,
        "daytime": False,
    },
    {
        "name": "Ursids",
        "iau_code": "URS",
        "iau_number": 15,
        "active_start": {"month": 12, "day": 17},
        "active_end": {"month": 12, "day": 26},
        "peak_month": 12,
        "peak_day": 22,
        "peak_day_end": 23,
        "zhr": 10,
        "zhr_note": None,
        "velocity_kms": 33.0,
        "parent_body": "8P/Tuttle",
        "radiant_constellation": "Ursa Minor",
        "hemisphere_note": "Best from Northern Hemisphere; radiant circumpolar above ~50°N",
        "daytime": False,
    },
]
```

### Option B: External JSON file (recommended for larger teams)

Store the same data as `data/meteor_showers.json` and load at app startup:

```python
# starcast/data/__init__.py
import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent
with (_DATA_DIR / "meteor_showers.json").open() as f:
    METEOR_SHOWERS = json.load(f)
```

**Recommendation:** Use Option B (JSON file) to keep data separate from code, but keep the Python dict schema definition above in a docstring or type hint for documentation. The JSON file should be at `data/meteor_showers.json` relative to the project root.

---

## Window Detection Logic Sketch

```python
from datetime import date

def get_active_showers(tonight: date, min_zhr: int = 5) -> list[dict]:
    """Return showers active on `tonight` with ZHR >= min_zhr."""
    active = []
    for shower in METEOR_SHOWERS:
        if shower.get("daytime"):
            continue
        zhr = shower.get("zhr", 0)
        if isinstance(zhr, str):  # "Variable"
            zhr = 10  # treat variable as noteworthy
        if zhr < min_zhr:
            continue
        if _is_active(tonight, shower["active_start"], shower["active_end"]):
            days_to_peak = _days_to_peak(tonight, shower)
            active.append({**shower, "days_to_peak": days_to_peak})
    return sorted(active, key=lambda s: abs(s["days_to_peak"]))

def _is_active(tonight: date, start: dict, end: dict) -> bool:
    """Handle year-wrap (e.g., Quadrantids: Dec 28 – Jan 12)."""
    s = date(tonight.year, start["month"], start["day"])
    e = date(tonight.year, end["month"], end["day"])
    if e < s:  # wraps new year
        e = date(tonight.year + 1, end["month"], end["day"])
    return s <= tonight <= e
```

---

## Citations

1. **IMO Meteor Shower Calendar 2026** (PDF, ed. Jürgen Rendtel, International Meteor Organization)  
   URL: https://www.imo.net/files/meteor-shower/cal2026.pdf  
   *(Currently redirects to outage notice as of Sept 2026; was accessible before cyberattack)*

2. **IMO Meteor Shower Calendar 2025** (PDF)  
   URL: https://www.imo.net/files/meteor-shower/cal2025.pdf

3. **IMO Meteor Shower Calendar 2027** (PDF)  
   URL: https://www.imo.net/files/meteor-shower/cal2027.pdf

4. **AMS Meteor Shower Calendar**  
   URL: https://www.amsmeteors.org/meteor-showers/meteor-shower-calendar/  
   *(Currently offline due to same cyberattack as of Sept 2026)*

5. **NASA — Meteor Showers (Science page)**  
   URL: https://science.nasa.gov/solar-system/meteors-meteorites/meteor-showers/  
   *(Live; provides active windows and peak nights but not ZHR)*

6. **NASA — 2026 Meteor Shower Activity Forecast for Low Earth Orbit**  
   URL: https://ntrs.nasa.gov/api/citations/20250009524/downloads/LEO_Forecast_2026.pdf  
   *(Engineering-focused flux data, not ZHR; confirms Quadrantids, Eta Aquariids, Perseids, Geminids as dominant 2026 showers)*

7. **Wikipedia — List of Meteor Showers**  
   URL: https://en.wikipedia.org/wiki/List_of_meteor_showers  
   *(Comprehensive table; sourced from IMO and IAU MDC data; 113 established showers as of March 2026)*

8. **Wikipedia — Quadrantids**  
   URL: https://en.wikipedia.org/wiki/Quadrantids

9. **Wikipedia — Geminids**  
   URL: https://en.wikipedia.org/wiki/Geminids

10. **Wikipedia — Eta Aquariids**  
    URL: https://en.wikipedia.org/wiki/Eta_Aquariids

11. **IAU Meteor Data Center (MDC)**  
    URL: https://www.ta3.sk/IAUC22DB/MDC2022/  
    Machine-readable established showers: `https://www.ta3.sk/IAUC22DB/MDC2022/Etc/streamestablisheddata2026.txt`  
    *(Slovak Academy of Sciences; no formal API but text/CSV downloads available)*

12. **space-calendar (GitHub, MIT license)**  
    URL: https://github.com/lkorth/space-calendar  
    JSON API: `https://space-calendar.lukekorth.com/feed.json?c=meteor-showers`

13. **gmn-python-api (PyPI, MIT license)**  
    URL: https://pypi.org/project/gmn-python-api/  
    *(Global Meteor Network open data; trajectory/orbit data, not annual calendar windows)*

14. **Little Astronomy — Annual Meteor Showers**  
    URL: https://littleastronomy.com/annual-meteor-showers/  
    *(Secondary source; cross-referenced for active date validation)*

15. **NASA Night Sky Network — Geminids 2026**  
    URL: https://nightsky.jpl.nasa.gov/events/bbaa/123173/  
    *(Confirms Geminids as top shower of 2026)*

16. **NASA Skywatching Tips May 2026**  
    URL: https://science.nasa.gov/solar-system/whats-up-may-2026-skywatching-tips-from-nasa/  
    *(Confirms Eta Aquariids peak ~May 5–6, ZHR ~50)*

