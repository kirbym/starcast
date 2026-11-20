"""The Significant Event detectors: conjunctions, oppositions and meteor showers.

Each detector finds its event and where and when to look for it, and one constructor turns that
into the night's Significant Event Highlight.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Self

import numpy as np
from skyfield import almanac
from skyfield.timelib import Time

from app.catalog import CatalogBody, MeteorShower
from app.observation import (
    TIMESCALE,
    Night,
    Observation,
    load_ephemeris,
    locate,
    rising_before,
    setting_after,
    to_utc,
)
from app.sky import Highlight, NarrationContext, SignificantEvent, VisibleBody

# Two bodies at most this far apart, both above the horizon at that moment, are in conjunction.
CONJUNCTION_LIMIT_DEGREES = 2.0


# The bodies that move against the stars. Only they can start a conjunction.
_MOVING_TYPES = frozenset({"planet", "moon", "named_comet"})


# The Planets beyond Earth's orbit, by catalog key. Only they can stand opposite the Sun.
_SUPERIOR_PLANETS = frozenset({"mars", "jupiter", "saturn", "uranus", "neptune"})


# Skyfield's almanac.oppositions_conjunctions() code for "opposite the Sun".
_OPPOSITION = 1


# A meteor shower is a Significant Event this many nights either side of its peak, at this ZHR or
# more.
SHOWER_PEAK_NIGHTS = 2


SHOWER_ZHR_LIMIT = 20


def significant_event(
    observed: list[Observation], night: Night, showers: tuple[MeteorShower, ...]
) -> Highlight | None:
    """The night's one Significant Event Highlight.

    When several qualify, a fixed event-type priority decides:
    Conjunction > Opposition > Meteor shower.
    Each detector only runs when every type above it has found nothing.
    """
    return (
        _tightest_conjunction(observed, night.samples)
        or _opposition(observed, night.local_noon)
        or _strongest_meteor_shower(showers, night)
    )


def _tightest_conjunction(observed: list[Observation], samples: Time) -> Highlight | None:
    """The night's tightest conjunction, or None if there is none."""
    tightest = min(
        _conjunctions(observed, samples), key=lambda found: found.separation_degrees, default=None
    )
    return tightest.highlight if tightest else None


@dataclass(frozen=True)
class _Conjunction:
    separation_degrees: float
    highlight: Highlight


def _conjunctions(observed: list[Observation], samples: Time) -> list[_Conjunction]:
    """Every conjunction of the night, between a moving body and another moving body or a Bright
    Star. DSOs never take part.

    Only Visible bodies are given, so a Named Comet too faint to see never takes part either.
    """
    moving = [seen for seen in observed if seen.body.object_type in _MOVING_TYPES]
    bright_stars = [seen for seen in observed if seen.body.object_type == "bright_star"]
    partners = moving + bright_stars
    found = []
    for index, first in enumerate(moving):
        # Each pair once: the moving bodies after this one, then every Bright Star.
        for second in partners[index + 1 :]:
            conjunction = _conjunction(first, second, samples)
            if conjunction:
                found.append(conjunction)
    return found


def _conjunction(first: Observation, second: Observation, samples: Time) -> _Conjunction | None:
    """The pair's conjunction, or None if they never come close enough while both are up.

    Closest approach is the closest sample at which both bodies are above the horizon, so a pair
    that draws closer still after one has set is caught while it can be seen.
    """
    both_up = (first.track.altitudes_degrees > 0) & (second.track.altitudes_degrees > 0)
    separations = first.track.positions.separation_from(second.track.positions).degrees
    separations = np.where(both_up, separations, np.inf)
    closest = int(separations.argmin())
    separation = float(separations[closest])
    if separation > CONJUNCTION_LIMIT_DEGREES:
        return None
    pair = (first.body, second.body)
    highlight = _event_highlight(
        SignificantEvent(
            event_type="conjunction",
            peak_time=to_utc(samples[closest]),
            related_object_names=(first.body.name, second.body.name),
        ),
        key=f"{first.catalog_body.key}_{second.catalog_body.key}",
        name=f"{first.body.name} and {second.body.name} in conjunction",
        where=_WhereToLook(
            # The pair stands within a couple of degrees of the first body: look there.
            peak_altitude_degrees=float(first.track.altitudes_degrees[closest]),
            azimuth_at_peak_degrees=float(first.track.azimuths_degrees[closest]),
            # The span over which both bodies are up together.
            rises_at=max((body.rises_at for body in pair if body.rises_at), default=None),
            sets_at=min((body.sets_at for body in pair if body.sets_at), default=None),
        ),
        context={"separation_degrees": round(separation, 2)},
    )
    return _Conjunction(separation, highlight)


def _opposition(observed: list[Observation], local_noon: datetime) -> Highlight | None:
    """The first Visible superior Planet, in catalog order, within a night of its opposition.

    The Planets inside Earth's orbit never reach opposition, so Mercury and Venus are never
    considered.
    """
    for seen in observed:
        if seen.body.object_type == "planet" and seen.catalog_body.key in _SUPERIOR_PLANETS:
            moment = _opposition_moment(seen.catalog_body, local_noon)
            if moment is not None:
                return _opposition_highlight(seen, moment)
    return None


def _opposition_moment(body: CatalogBody, local_noon: datetime) -> Time | None:
    """The exact moment of the Planet's opposition, if it falls within a night of this one.

    A night runs from local noon to the next, so the nights either side of this one span the
    three days from the previous local noon.
    """
    ephemeris = load_ephemeris()
    times, codes = almanac.find_discrete(
        TIMESCALE.from_datetime(local_noon - timedelta(days=1)),
        TIMESCALE.from_datetime(local_noon + timedelta(days=2)),
        almanac.oppositions_conjunctions(ephemeris, ephemeris[body.target]),
    )
    return next(
        (moment for moment, code in zip(times, codes, strict=True) if code == _OPPOSITION), None
    )


def _opposition_highlight(seen: Observation, moment: Time) -> Highlight:
    """The opposition's Highlight: the Planet itself, best seen at its Peak Altitude."""
    planet = seen.body
    return _event_highlight(
        SignificantEvent(
            event_type="opposition",
            peak_time=to_utc(seen.peak_time),
            related_object_names=(planet.name,),
        ),
        key=seen.catalog_body.key,
        name=f"{planet.name} at opposition",
        where=_WhereToLook.at(planet),
        context={"opposition_time": to_utc(moment).isoformat()},
    )


def _strongest_meteor_shower(showers: tuple[MeteorShower, ...], night: Night) -> Highlight | None:
    """The qualifying meteor shower with the highest ZHR whose radiant clears the horizon during the
    Viewing Window."""
    night_date = night.local_noon.date()
    qualifying = [
        shower for shower in showers if _shower_qualifies(shower, night_date, night.latitude)
    ]
    for shower in sorted(qualifying, key=lambda shower: shower.zhr, reverse=True):
        highlight = _meteor_shower_highlight(shower, night)
        if highlight:
            return highlight
    return None


def _shower_qualifies(shower: MeteorShower, night_date: date, latitude: float) -> bool:
    """Whether the shower is strong enough and near enough its peak, seen from this hemisphere.

    A daytime shower never qualifies, and neither does one that favours the other hemisphere.
    """
    days_from_peak = abs((_nearest_peak(shower, night_date) - night_date).days)
    return (
        not shower.daytime
        and not shower.favours_other_hemisphere(latitude)
        and shower.zhr >= SHOWER_ZHR_LIMIT
        and days_from_peak <= SHOWER_PEAK_NIGHTS
    )


def _nearest_peak(shower: MeteorShower, night_date: date) -> date:
    """The shower's peak date nearest the night's, which may fall in the previous or next year."""
    peaks = (
        date(year, shower.peak_month, shower.peak_day)
        for year in (night_date.year - 1, night_date.year, night_date.year + 1)
    )
    return min(peaks, key=lambda peak: abs(peak - night_date))


def _meteor_shower_highlight(shower: MeteorShower, night: Night) -> Highlight | None:
    """The shower's Highlight, placed at its radiant, or None if the radiant never rises tonight.

    Meteors stream from the radiant, and the higher it stands the more of them are seen, so the
    shower is at its best at the radiant's Peak Altitude.
    """
    located = locate(night.observer, shower.radiant, night.samples)
    if located is None:
        return None
    _, peak = located
    context: dict[str, str | float] = {
        "zhr": shower.zhr,
        "peak_date": _nearest_peak(shower, night.local_noon.date()).isoformat(),
        "velocity_kms": shower.velocity_kms,
        "parent_body": shower.parent_body,
    }
    if shower.zhr_note:
        context["zhr_note"] = shower.zhr_note
    return _event_highlight(
        SignificantEvent(
            event_type="meteor_shower",
            peak_time=to_utc(peak.time),
            related_object_names=(shower.radiant_constellation,),
        ),
        key=shower.key,
        name=f"{shower.name} meteor shower",
        where=_WhereToLook(
            peak_altitude_degrees=peak.altitude_degrees,
            azimuth_at_peak_degrees=peak.azimuth_degrees,
            rises_at=rising_before(night.observer, shower.radiant, peak.time),
            sets_at=setting_after(night.observer, shower.radiant, peak.time),
        ),
        context=context,
    )


@dataclass(frozen=True)
class _WhereToLook:
    """Where and when to look for a Significant Event: its Highlight's positional fields."""

    peak_altitude_degrees: float
    azimuth_at_peak_degrees: float
    rises_at: datetime | None
    sets_at: datetime | None
    magnitude: float | None = None

    @classmethod
    def at(cls, body: VisibleBody) -> Self:
        """Look where a Visible body is, as for a Planet at opposition."""
        return cls(
            peak_altitude_degrees=body.peak_altitude_degrees,
            azimuth_at_peak_degrees=body.azimuth_at_peak_degrees,
            rises_at=body.rises_at,
            sets_at=body.sets_at,
            magnitude=body.magnitude,
        )


def _event_highlight(
    event: SignificantEvent,
    *,
    key: str,
    name: str,
    where: _WhereToLook,
    context: NarrationContext,
) -> Highlight:
    """The night's Significant Event Highlight: a Category 3 Visible body for the event itself.

    `key` tells this event from others of its type, as in "jupiter_saturn" for a conjunction.
    """
    body = VisibleBody(
        id=f"significant_event:{event.event_type}_{key}",
        category=3,
        object_type="significant_event",
        name=name,
        peak_altitude_degrees=where.peak_altitude_degrees,
        azimuth_at_peak_degrees=where.azimuth_at_peak_degrees,
        rises_at=where.rises_at,
        sets_at=where.sets_at,
        magnitude=where.magnitude,
        event=event,
    )
    return Highlight(body, context)
