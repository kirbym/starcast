"""The astronomy engine: location + timezone + date -> the night's computed sky."""

import math
from datetime import date, datetime, time, timedelta
from functools import cache
from zoneinfo import ZoneInfo

from skyfield import almanac
from skyfield.api import wgs84
from skyfield.jpllib import SpiceKernel
from skyfield.timelib import Time
from skyfield.toposlib import GeographicPosition

from app.catalog import CATALOG, Catalog, MeteorShower
from app.comets import named_comet_elements
from app.events import significant_event
from app.observation import (
    TIMESCALE,
    Night,
    Observation,
    data_dir,
    load_ephemeris,
    observe_visible,
    sample_times,
    to_utc,
)
from app.sky import Highlight, NightSky, ViewingWindow

DARK = 0  # The code almanac.dark_twilight_day() uses for "Sun below -18 degrees".


_MINUTES_IN_SEARCH = 24 * 60 + 1


# Visual Priority tiers for Category 1, highest first; the Moon takes the top or the bottom tier.
# Only Jupiter and Saturn are gas giants. Uranus and Neptune are faint ice giants, barely or not at
# all visible to the naked eye, so they rank below the rocky planets rather than beating a bright
# Mars or Venus on altitude alone.
_MOON_TIER_HALF_LIT = 4


_MOON_TIER_THIN = 0


_CATEGORY_1_TIERS = {
    "planet:jupiter": 3,
    "planet:saturn": 3,
    "planet:mercury": 2,
    "planet:venus": 2,
    "planet:mars": 2,
    "planet:uranus": 1,
    "planet:neptune": 1,
}


def compute_night_sky(
    latitude: float,
    longitude: float,
    timezone: str,
    local_date: date,
    catalog: Catalog = CATALOG,
) -> NightSky:
    """Compute the sky for the night that begins on `local_date` at the given location."""
    local_noon = datetime.combine(local_date, time(12), tzinfo=ZoneInfo(timezone))
    window = _viewing_window(latitude, longitude, local_noon)
    if window.starts_at == window.ends_at:
        return NightSky(viewing_window=window)

    night = Night(
        observer=load_ephemeris()["earth"] + wgs84.latlon(latitude, longitude),
        latitude=latitude,
        local_noon=local_noon,
        samples=sample_times(window),
        # Loaded only if a Named Comet is placed, and then only once for the night.
        comet_elements=cache(lambda: named_comet_elements(data_dir())),
    )
    planets_and_moon = observe_visible(catalog.planets_and_moon, night)
    constellations = observe_visible(catalog.constellations, night)
    category_3_bodies = observe_visible(catalog.category_3, night)
    category_1 = max(planets_and_moon, key=_category_1_priority, default=None)
    category_2 = max(constellations, key=_category_2_priority, default=None)
    category_3 = _category_3_highlight(
        planets_and_moon + category_3_bodies, night, catalog.meteor_showers
    )
    highlights = [seen.highlight for seen in (category_1, category_2) if seen]
    if category_3:
        highlights.append(category_3)
    return NightSky(
        viewing_window=window,
        highlights=highlights,
        visible_objects=[
            seen.body for seen in planets_and_moon + constellations + category_3_bodies
        ],
    )


def _category_3_highlight(
    observed: list[Observation], night: Night, showers: tuple[MeteorShower, ...]
) -> Highlight | None:
    """Category 3: a Significant Event wins outright; otherwise the best standing body.

    `observed` is every Visible body of the night outside Category 2. The standing candidates
    among them are the Category 3 bodies: the Bright Stars, Named Comets and DSOs.
    """
    event = significant_event(observed, night, showers)
    if event:
        return event
    standing = [seen for seen in observed if seen.body.category == 3]
    best = max(standing, key=_category_3_priority, default=None)
    return best.highlight if best else None


def _category_3_priority(seen: Observation) -> tuple[float, float]:
    """Visual Priority for standing Category 3 bodies: the larger tuple wins.

    The brightest body (the lowest magnitude) wins, with Peak Altitude breaking ties. A body with
    no known magnitude ranks below every body with one.
    """
    magnitude = seen.body.magnitude
    brightness = -math.inf if magnitude is None else -magnitude
    return brightness, seen.body.peak_altitude_degrees


def _category_2_priority(seen: Observation) -> float:
    """Visual Priority for Category 2: the highest Peak Altitude wins."""
    return seen.body.peak_altitude_degrees


def _category_1_priority(seen: Observation) -> tuple[int, float]:
    """Visual Priority for Category 1: the larger tuple wins, with Peak Altitude breaking ties.

    The Moon is a wildcard: at least half lit at its peak, it outranks every Planet; otherwise
    every Planet outranks it.
    """
    body = seen.body
    if body.moon_phase is not None:
        lit = body.moon_phase.illuminated_fraction >= 0.5
        tier = _MOON_TIER_HALF_LIT if lit else _MOON_TIER_THIN
    else:
        tier = _CATEGORY_1_TIERS[body.id]
    return tier, body.peak_altitude_degrees


def _viewing_window(latitude: float, longitude: float, local_noon: datetime) -> ViewingWindow:
    """Find the night's span of full darkness between local noon and the next local noon.

    Two kinds of night have no dusk or no dawn to find:
    - If it is never fully dark, the window has zero length at the darkest moment. That marks a
      night with no darkness to observe in, so it must always produce a Quiet Night.
    - If it is dark all the way through (polar night), the window is the whole search span.
    """
    ephemeris = load_ephemeris()
    location = wgs84.latlon(latitude, longitude)
    twilight = almanac.dark_twilight_day(ephemeris, location)
    search_start = TIMESCALE.from_datetime(local_noon)
    search_end = TIMESCALE.from_datetime(local_noon + timedelta(days=1))

    times, codes = almanac.find_discrete(search_start, search_end, twilight)
    changes = list(zip(times, codes, strict=True))

    if twilight(search_start) == DARK:
        dusk = search_start
    else:
        dusk = next((moment for moment, code in changes if code == DARK), None)
    if dusk is None:
        darkest = _darkest_moment(ephemeris, location, search_start, search_end)
        return ViewingWindow(starts_at=darkest, ends_at=darkest)

    dawn = next(
        (moment for moment, code in changes if code != DARK and moment.tt > dusk.tt), search_end
    )
    return ViewingWindow(starts_at=to_utc(dusk), ends_at=to_utc(dawn))


def _darkest_moment(
    ephemeris: SpiceKernel, location: GeographicPosition, search_start: Time, search_end: Time
) -> datetime:
    """Scan the span minute by minute: near the poles the Sun may have no daily low point."""
    observer = ephemeris["earth"] + location
    times = TIMESCALE.linspace(search_start, search_end, _MINUTES_IN_SEARCH)
    altitudes = observer.at(times).observe(ephemeris["sun"]).apparent().altaz()[0].degrees
    return to_utc(times[int(altitudes.argmin())])
