"""The request and response shapes of POST /api/report."""

import datetime as dt
import re
from typing import Annotated
from zoneinfo import available_timezones

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

from app.astronomy import Category, EventType, ObjectType, ViewingWindow

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


class SignificantEvent(BaseModel):
    """A Significant Event Highlight's event: what happens, at its best when, and between what."""

    model_config = ConfigDict(from_attributes=True)

    event_type: EventType
    peak_time: dt.datetime
    related_object_names: list[str] | None


class SkyObject(BaseModel):
    """A Visible body's raw fields: one entry of visible_objects, and what the Narrator is given."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    category: Category
    object_type: ObjectType
    name: str
    peak_altitude_degrees: float
    azimuth_at_peak_degrees: float
    rises_at: dt.datetime | None
    sets_at: dt.datetime | None
    magnitude: float | None
    event: SignificantEvent | None


class Highlight(SkyObject):
    mini_headline: str
    paragraph: str


class ReportResponse(BaseModel):
    headline: str
    viewing_window: ViewingWindow
    highlights: list[Highlight]
    visible_objects: list[SkyObject]
