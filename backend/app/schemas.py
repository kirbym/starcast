"""The request and response shapes of POST /api/report."""

import datetime as dt
import re
from typing import Annotated, Any
from zoneinfo import available_timezones

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field

from app.astronomy import ViewingWindow

# Whole years inside DE440s's coverage (December 1849 to January 2150).
_EARLIEST_YEAR = 1850
_LATEST_YEAR = 2149
_TIMEZONES = available_timezones()


def _known_timezone(value: str) -> str:
    if value not in _TIMEZONES:
        raise ValueError("unknown IANA timezone")
    return value


def _local_date(value: object) -> dt.date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("date must be YYYY-MM-DD")
    parsed = dt.date.fromisoformat(value)
    if not _EARLIEST_YEAR <= parsed.year <= _LATEST_YEAR:
        raise ValueError(f"date must be between {_EARLIEST_YEAR} and {_LATEST_YEAR}")
    return parsed


class ReportRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: Annotated[str, AfterValidator(_known_timezone)]
    date: Annotated[dt.date, BeforeValidator(_local_date)]
    location_label: str | None = None


class ReportResponse(BaseModel):
    headline: str
    viewing_window: ViewingWindow
    highlights: list[dict[str, Any]]
    visible_objects: list[dict[str, Any]]
