"""The astronomy engine: location + timezone + date -> the night's computed sky."""

import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from skyfield import almanac
from skyfield.api import Loader, load, wgs84
from skyfield.jpllib import SpiceKernel
from skyfield.searchlib import find_minima
from skyfield.timelib import Time
from skyfield.toposlib import GeographicPosition

EPHEMERIS_FILE = "de440s.bsp"
DARK = 0  # The code almanac.dark_twilight_day() uses for "Sun below -18 degrees".

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / ".cache" / "skyfield"
_timescale = load.timescale(builtin=True)


@dataclass(frozen=True)
class ViewingWindow:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class NightSky:
    viewing_window: ViewingWindow
    highlights: list[dict[str, Any]] = field(default_factory=list)
    visible_objects: list[dict[str, Any]] = field(default_factory=list)


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
    return NightSky(viewing_window=_viewing_window(latitude, longitude, local_noon))


def _viewing_window(latitude: float, longitude: float, local_noon: datetime) -> ViewingWindow:
    """Find the night's span of full darkness between local noon and the next local noon.

    Two kinds of night have no dusk or no dawn to find:
    - If it is never fully dark, the window has zero length at the darkest moment. Nothing can
      be Visible in it, so the report is a Quiet Night.
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
    observer = ephemeris["earth"] + location
    sun = ephemeris["sun"]

    def sun_altitude(moment: Time) -> Any:
        return observer.at(moment).observe(sun).apparent().altaz()[0].degrees

    sun_altitude.step_days = 0.04
    times, altitudes = find_minima(search_start, search_end, sun_altitude)
    return _to_utc(times[altitudes.argmin()])


def _to_utc(moment: Time) -> datetime:
    return moment.utc_datetime().astimezone(UTC).replace(microsecond=0)
