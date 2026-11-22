"""The computed sky: what StarCast says is up on one night, and the shapes it is reported in.

These are the result types. The API serves them directly, and the frontend's types are generated
from them.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# Named by number, as CONTEXT.md names them: 1 Planet or Moon, 2 Named Constellation, 3 Bright
# Star, Named Comet, DSO or Significant Event.
Category = Literal[1, 2, 3]


ObjectType = Literal[
    "planet", "moon", "constellation", "bright_star", "named_comet", "dso", "significant_event"
]


# What kind of DSO a DSO is, grouped from its detailed OpenNGC type. It picks the DSO's sprite and
# its Highlight Card's kind label.
DsoType = Literal["galaxy", "nebula", "globular_cluster", "open_cluster"]


EventType = Literal["conjunction", "opposition", "meteor_shower"]


# Catalog facts about a body that the Narrator can draw on, like a star's spectral type.
NarrationContext = Mapping[str, str | float]


@dataclass(frozen=True)
class ViewingWindow:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class SignificantEvent:
    """What makes a Significant Event Highlight time-sensitive: what happens, and when."""

    event_type: EventType
    # The moment the event is at its best: a conjunction's closest approach, or the Peak Altitude
    # of an opposition planet or a meteor shower's radiant.
    peak_time: datetime
    related_object_names: tuple[str, ...] | None


@dataclass(frozen=True)
class VisibleBody:
    """A catalog body that is Visible on the night, with its positional fields for the Detail Layer.

    A Significant Event Highlight has the same shape, with `event` set. Its positional fields say
    where and when to look for the event.
    """

    id: str
    category: Category
    object_type: ObjectType
    name: str
    peak_altitude_degrees: float
    azimuth_at_peak_degrees: float
    rises_at: datetime | None
    sets_at: datetime | None
    magnitude: float | None
    event: SignificantEvent | None = None
    # Set for a DSO, and None for every other kind of body.
    dso_type: DsoType | None = None


@dataclass(frozen=True)
class Highlight:
    """One of the night's Highlights: the Visible body selected for its Category, and the
    narration-only facts about it, like a star's spectral type or a conjunction's separation."""

    body: VisibleBody
    context: NarrationContext | None = None


@dataclass(frozen=True)
class NightSky:
    """The night's computed sky: its Viewing Window, its Highlights, and every Visible body the
    Highlights were selected from. The Cosmic Report carries only the Highlights."""

    viewing_window: ViewingWindow
    highlights: list[Highlight] = field(default_factory=list)
    visible_objects: list[VisibleBody] = field(default_factory=list)
