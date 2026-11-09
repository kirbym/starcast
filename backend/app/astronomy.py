"""The astronomy engine: location + timezone + date -> the night's computed sky."""

import math
import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from skyfield import almanac
from skyfield.api import Loader, load, wgs84
from skyfield.jpllib import SpiceKernel
from skyfield.magnitudelib import planetary_magnitude
from skyfield.timelib import Time
from skyfield.toposlib import GeographicPosition

EPHEMERIS_FILE = "de440s.bsp"
DARK = 0  # The code almanac.dark_twilight_day() uses for "Sun below -18 degrees".
_MINUTES_IN_SEARCH = 24 * 60 + 1
# Every body's Peak Altitude comes from the same sample times, spaced this far apart.
_SAMPLE_SPACING = timedelta(minutes=5)

Category = Literal["planet_moon", "constellation", "featured"]
ObjectType = Literal[
    "planet", "moon", "constellation", "bright_star", "comet", "dso", "significant_event"
]


@dataclass(frozen=True)
class _CatalogBody:
    object_type: ObjectType
    key: str
    name: str
    ephemeris_target: str

    @property
    def id(self) -> str:
        return f"{self.object_type}:{self.key}"


# DE440s carries Mars and the outer planets only as barycenters of their systems.
_MOON = _CatalogBody("moon", "moon", "Moon", "moon")
_SOLAR_SYSTEM = (
    _CatalogBody("planet", "mercury", "Mercury", "mercury"),
    _CatalogBody("planet", "venus", "Venus", "venus"),
    _CatalogBody("planet", "mars", "Mars", "mars barycenter"),
    _CatalogBody("planet", "jupiter", "Jupiter", "jupiter barycenter"),
    _CatalogBody("planet", "saturn", "Saturn", "saturn barycenter"),
    _CatalogBody("planet", "uranus", "Uranus", "uranus barycenter"),
    _CatalogBody("planet", "neptune", "Neptune", "neptune barycenter"),
    _MOON,
)

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

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / ".cache" / "skyfield"
_timescale = load.timescale(builtin=True)


@dataclass(frozen=True)
class ViewingWindow:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class VisibleBody:
    """A catalog body that is Visible tonight, with its positional fields for the Detail Layer."""

    id: str
    category: Category
    object_type: ObjectType
    name: str
    peak_altitude_degrees: float
    azimuth_at_peak_degrees: float
    rises_at: datetime | None
    sets_at: datetime | None
    magnitude: float | None
    event: None = None


@dataclass(frozen=True)
class NightSky:
    viewing_window: ViewingWindow
    highlights: list[VisibleBody] = field(default_factory=list)
    visible_objects: list[VisibleBody] = field(default_factory=list)


@lru_cache(maxsize=1)
def _ephemeris() -> SpiceKernel:
    """Load DE440s, downloading it to the data directory on first use."""
    data_dir = Path(os.environ.get("STARCAST_DATA_DIR", _DEFAULT_DATA_DIR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Loader(str(data_dir), verbose=False)(EPHEMERIS_FILE)


def compute_night_sky(
    latitude: float, longitude: float, timezone: str, local_date: date
) -> NightSky:
    """Compute the sky for the night that begins on `local_date` at the given location."""
    local_noon = datetime.combine(local_date, time(12), tzinfo=ZoneInfo(timezone))
    window = _viewing_window(latitude, longitude, local_noon)
    if window.starts_at == window.ends_at:
        return NightSky(viewing_window=window)

    observer = _ephemeris()["earth"] + wgs84.latlon(latitude, longitude)
    samples = _sample_times(window)
    observations = [
        seen
        for catalog_body in _SOLAR_SYSTEM
        if (seen := _observe(catalog_body, observer, samples))
    ]
    category_1 = max(observations, key=_category_1_priority, default=None)
    return NightSky(
        viewing_window=window,
        highlights=[category_1.body] if category_1 else [],
        visible_objects=[seen.body for seen in observations],
    )


@dataclass(frozen=True)
class _Observation:
    body: VisibleBody
    peak_time: Time


def _category_1_priority(seen: _Observation) -> tuple[int, float]:
    """Visual Priority for Category 1: the larger tuple wins, with Peak Altitude breaking ties.

    The Moon is a wildcard: at least half lit at its peak, it outranks every Planet; otherwise
    every Planet outranks it.
    """
    body = seen.body
    if body.object_type == "moon":
        lit = almanac.fraction_illuminated(_ephemeris(), "moon", seen.peak_time) >= 0.5
        tier = _MOON_TIER_HALF_LIT if lit else _MOON_TIER_THIN
    else:
        tier = _CATEGORY_1_TIERS[body.id]
    return tier, body.peak_altitude_degrees


def _sample_times(window: ViewingWindow) -> Time:
    """Evenly spaced times across the Viewing Window, both ends included."""
    count = math.ceil((window.ends_at - window.starts_at) / _SAMPLE_SPACING) + 1
    return _timescale.linspace(
        _timescale.from_datetime(window.starts_at), _timescale.from_datetime(window.ends_at), count
    )


def _observe(body: _CatalogBody, observer, samples: Time) -> _Observation | None:
    """Position one body over the night, or None if it never clears the horizon."""
    target = _ephemeris()[body.ephemeris_target]
    altitudes, azimuths, _ = observer.at(samples).observe(target).apparent().altaz()
    peak = int(altitudes.degrees.argmax())
    if altitudes.degrees[peak] <= 0:
        return None

    peak_time = samples[peak]
    visible = VisibleBody(
        id=body.id,
        category="planet_moon",
        object_type=body.object_type,
        name=body.name,
        peak_altitude_degrees=float(altitudes.degrees[peak]),
        azimuth_at_peak_degrees=float(azimuths.degrees[peak]),
        rises_at=_rising_before(observer, target, peak_time),
        sets_at=_setting_after(observer, target, peak_time),
        magnitude=_magnitude(body, observer, target, peak_time),
    )
    return _Observation(visible, peak_time)


def _rising_before(observer, target, peak_time: Time) -> datetime | None:
    """When the body rose for the pass that carries it to its Peak Altitude.

    None if it has not risen in the day before, meaning it never set: it is circumpolar tonight.
    """
    times, risen = almanac.find_risings(observer, target, peak_time - 1, peak_time)
    risings = [moment for moment, ok in zip(times, risen, strict=True) if ok]
    return _to_utc(risings[-1]) if risings else None


def _setting_after(observer, target, peak_time: Time) -> datetime | None:
    """When the body sets after its Peak Altitude, or None if it stays up for the next day."""
    times, set_ = almanac.find_settings(observer, target, peak_time, peak_time + 1)
    settings = [moment for moment, ok in zip(times, set_, strict=True) if ok]
    return _to_utc(settings[0]) if settings else None


def _magnitude(body: _CatalogBody, observer, target, moment: Time) -> float | None:
    if body.object_type == "moon":
        return _moon_magnitude(observer, target, moment)
    magnitude = float(planetary_magnitude(observer.at(moment).observe(target)))
    # Skyfield has no formula for Saturn at large phase angles, and returns NaN there.
    return None if math.isnan(magnitude) else magnitude


def _moon_magnitude(observer, moon, moment: Time) -> float:
    """Allen's formula for the Moon's apparent magnitude at a given phase angle."""
    sun = _ephemeris()["sun"]
    phase_angle = observer.at(moment).observe(moon).apparent().phase_angle(sun).degrees
    return float(-12.73 + 0.026 * abs(phase_angle) + 4e-9 * phase_angle**4)


def _viewing_window(latitude: float, longitude: float, local_noon: datetime) -> ViewingWindow:
    """Find the night's span of full darkness between local noon and the next local noon.

    Two kinds of night have no dusk or no dawn to find:
    - If it is never fully dark, the window has zero length at the darkest moment. That marks a
      night with no darkness to observe in, so it must always produce a Quiet Night.
    - If it is dark all the way through (polar night), the window is the whole search span.
    """
    ephemeris = _ephemeris()
    location = wgs84.latlon(latitude, longitude)
    twilight = almanac.dark_twilight_day(ephemeris, location)
    search_start = _timescale.from_datetime(local_noon)
    search_end = _timescale.from_datetime(local_noon + timedelta(days=1))

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
    return ViewingWindow(starts_at=_to_utc(dusk), ends_at=_to_utc(dawn))


def _darkest_moment(
    ephemeris: SpiceKernel, location: GeographicPosition, search_start: Time, search_end: Time
) -> datetime:
    """Scan the span minute by minute: near the poles the Sun may have no daily low point."""
    observer = ephemeris["earth"] + location
    times = _timescale.linspace(search_start, search_end, _MINUTES_IN_SEARCH)
    altitudes = observer.at(times).observe(ephemeris["sun"]).apparent().altaz()[0].degrees
    return _to_utc(times[int(altitudes.argmin())])


def _to_utc(moment: Time) -> datetime:
    return moment.utc_datetime().astimezone(UTC).replace(microsecond=0)
