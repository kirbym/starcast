"""The request and response shapes of POST /api/report."""

import datetime as dt
import re
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

from app.sky import ViewingWindow, VisibleBody

# Whole years inside DE440s's coverage (December 1849 to January 2150).
_EARLIEST_YEAR = 1850
_LATEST_YEAR = 2149


def _local_date(value: object) -> dt.date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("date must be YYYY-MM-DD")
    parsed = dt.date.fromisoformat(value)
    if not _EARLIEST_YEAR <= parsed.year <= _LATEST_YEAR:
        raise ValueError(f"date must be between {_EARLIEST_YEAR} and {_LATEST_YEAR}")
    return parsed


class ReportRequest(BaseModel):
    """A place to report on. Its timezone is looked up from where it is, never sent."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    # The place's local date the night begins on; left out, it is today at the place.
    date: Annotated[dt.date | None, BeforeValidator(_local_date)] = None
    location_label: str | None = None


@dataclass(frozen=True, kw_only=True)
class HighlightCard(VisibleBody):
    """What the Cosmic Report shows for one Highlight: its Visible body's positional fields for
    the Detail Layer, and the card the Narrator wrote for it."""

    mini_headline: str
    paragraph: str


class ReportResponse(BaseModel):
    # The place's IANA timezone and local date the night was computed for. Every moment in the
    # report is in UTC; this is the zone to show them in.
    timezone: str
    date: dt.date
    headline: str
    viewing_window: ViewingWindow
    highlights: list[HighlightCard]
    visible_objects: list[VisibleBody]
