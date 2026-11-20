"""A place's own clock: its IANA timezone, looked up from where it is, and its local date."""

import datetime as dt
from functools import cache
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder


@cache
def _finder() -> TimezoneFinder:
    # Loading the timezone boundaries takes a moment, so it is done once, on the first lookup.
    return TimezoneFinder()


def place_timezone(latitude: float, longitude: float) -> str:
    """The IANA timezone in force at a point on Earth.

    Over open ocean this is a nautical zone like "Etc/GMT+9". Should the lookup find nothing at
    all, the nautical zone for the longitude stands in.
    """
    found = _finder().timezone_at(lat=latitude, lng=longitude)
    if found:
        return found
    # Etc/GMT zones are signed the POSIX way: Etc/GMT+9 is nine hours behind UTC.
    offset = -round(longitude / 15)
    return "Etc/GMT" if offset == 0 else f"Etc/GMT{offset:+d}"


def place_local_date(timezone: str, now: dt.datetime) -> dt.date:
    """The place's own date at `now`, which may differ from the requester's."""
    return now.astimezone(ZoneInfo(timezone)).date()


def get_now() -> dt.datetime:
    """The current moment, as a dependency so tests can fix it."""
    return dt.datetime.now(dt.UTC)
