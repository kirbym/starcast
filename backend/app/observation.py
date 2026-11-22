"""Observing the night: the ephemeris, the sample times, and where each catalog body stands.

Every kind of catalog body is observed the same way, through its placement: a fixed point, a
Planet, the Moon, or a Named Comet's orbit.
"""

import logging
import math
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np
from skyfield import almanac
from skyfield.api import Loader, Star, load
from skyfield.jpllib import SpiceKernel
from skyfield.magnitudelib import planetary_magnitude
from skyfield.positionlib import Apparent
from skyfield.timelib import Time
from skyfield.vectorlib import VectorFunction

from app.catalog import CatalogBody
from app.comets import CometElements, CometOrbit, NamedComet
from app.sky import Highlight, NarrationContext, ViewingWindow, VisibleBody

_log = logging.getLogger(__name__)


EPHEMERIS_FILE = "de440s.bsp"


# Every body's Peak Altitude comes from the same sample times, spaced this far apart.
_SAMPLE_SPACING = timedelta(minutes=5)


_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / ".cache" / "skyfield"


TIMESCALE = load.timescale(builtin=True)


def data_dir() -> Path:
    """Where downloaded astronomy data, the ephemeris and the comet elements, is kept."""
    return Path(os.environ.get("STARCAST_DATA_DIR", _DEFAULT_DATA_DIR))


@lru_cache(maxsize=1)
def load_ephemeris() -> SpiceKernel:
    """Load DE440s, downloading it to the data directory on first use."""
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return Loader(str(directory), verbose=False)(EPHEMERIS_FILE)


@dataclass(frozen=True)
class Night:
    """Where the night is observed from, and when."""

    observer: VectorFunction
    latitude: float
    local_noon: datetime
    samples: Time
    # The Named Comets' orbital elements, by designation.
    comet_elements: Callable[[], Mapping[str, CometElements]]


@dataclass(frozen=True)
class Track:
    """Where a body stands at each of the night's sample times."""

    positions: Apparent
    altitudes_degrees: np.ndarray
    azimuths_degrees: np.ndarray


@dataclass(frozen=True)
class Observation:
    catalog_body: CatalogBody
    body: VisibleBody
    peak_time: Time
    track: Track
    context: NarrationContext | None

    @property
    def highlight(self) -> Highlight:
        return Highlight(self.body, self.context)


def observe_visible(bodies: tuple[CatalogBody, ...], night: Night) -> list[Observation]:
    """Every one of the bodies that is Visible across the night's sample times.

    A body that cannot be placed, like a Named Comet without usable orbital elements, is left out.
    """
    observed = []
    for body in bodies:
        placement = _place(body, night)
        seen = placement and _observe(body, placement, night)
        if seen:
            observed.append(seen)
    return observed


class _Placement(Protocol):
    """How one kind of catalog body is placed for the night: what to observe, how bright it is at a
    moment, whether that brightness counts as Visible, and what the Narrator is told about it.

    The adapters are a fixed point (a Named Constellation's Centroid, a Bright Star, a DSO), a
    Planet, the Moon, and a Named Comet's orbit (comets.CometOrbit).
    """

    @property
    def target(self): ...

    def magnitude(self, observer: VectorFunction, moment: Time) -> float | None: ...

    def is_visible(self, magnitude: float | None) -> bool: ...

    def context(self) -> NarrationContext: ...


@dataclass(frozen=True)
class _FixedPoint:
    """A body at a fixed J2000 point, with its magnitude, if any, from the catalog."""

    target: Star
    catalog_magnitude: float | None

    def magnitude(self, _observer: VectorFunction, _moment: Time) -> float | None:
        return self.catalog_magnitude

    def is_visible(self, _magnitude: float | None) -> bool:
        return True

    def context(self) -> NarrationContext:
        return {}


@dataclass(frozen=True)
class _Planet:
    """A Planet, placed by the ephemeris, its magnitude computed for the moment."""

    target: VectorFunction

    def magnitude(self, observer: VectorFunction, moment: Time) -> float | None:
        magnitude = float(planetary_magnitude(observer.at(moment).observe(self.target)))
        # Skyfield has no formula for Saturn at large phase angles, and returns NaN there.
        return None if math.isnan(magnitude) else magnitude

    def is_visible(self, _magnitude: float | None) -> bool:
        return True

    def context(self) -> NarrationContext:
        return {}


@dataclass(frozen=True)
class _Moon:
    """The Moon, placed by the ephemeris, its magnitude from its phase."""

    target: VectorFunction
    sun: VectorFunction

    def magnitude(self, observer: VectorFunction, moment: Time) -> float:
        """Allen's formula for the Moon's apparent magnitude at a given phase angle."""
        position = observer.at(moment).observe(self.target).apparent()
        phase_angle = position.phase_angle(self.sun).degrees
        return float(-12.73 + 0.026 * abs(phase_angle) + 4e-9 * phase_angle**4)

    def is_visible(self, _magnitude: float | None) -> bool:
        return True

    def context(self) -> NarrationContext:
        return {}


def _place(body: CatalogBody, night: Night) -> _Placement | None:
    """The body's placement for the night, or None if it cannot be placed.

    This is the one place a catalog body's kind decides how it is observed.
    """
    match body.target:
        case Star():
            return _FixedPoint(body.target, body.magnitude)
        case NamedComet():
            return _place_named_comet(body, body.target, night)
        case str() if body.object_type == "moon":
            return _Moon(load_ephemeris()[body.target], load_ephemeris()["sun"])
        case str():
            return _Planet(load_ephemeris()[body.target])


def _place_named_comet(body: CatalogBody, comet: NamedComet, night: Night) -> CometOrbit | None:
    """A Named Comet's orbit, or None if its elements are missing or unusable."""
    elements = night.comet_elements().get(comet.designation)
    if elements is None:
        return None
    try:
        return CometOrbit.place(elements, load_ephemeris()["sun"], TIMESCALE)
    except Exception:
        _log.warning("Could not place %s from its orbital elements", body.id, exc_info=True)
        return None


def sample_times(window: ViewingWindow) -> Time:
    """Evenly spaced times across the Viewing Window, both ends included."""
    count = math.ceil((window.ends_at - window.starts_at) / _SAMPLE_SPACING) + 1
    return TIMESCALE.linspace(
        TIMESCALE.from_datetime(window.starts_at), TIMESCALE.from_datetime(window.ends_at), count
    )


def _observe(body: CatalogBody, placement: _Placement, night: Night) -> Observation | None:
    """Position one body over the night, or None if it is not Visible.

    It must clear the horizon, and its placement must count its magnitude at its peak as Visible.
    """
    located = locate(night.observer, placement.target, night.samples)
    if located is None:
        return None
    track, peak = located
    magnitude = placement.magnitude(night.observer, peak.time)
    if not placement.is_visible(magnitude):
        return None
    visible = _visible_body(body, night.observer, placement.target, peak, magnitude)
    context = {**(body.context or {}), **placement.context()} or None
    return Observation(body, visible, peak.time, track, context)


def locate(observer, target, samples: Time) -> "tuple[Track, Peak] | None":
    """Where the target stands through the night, and at its highest, or None if it never rises."""
    track = _track(observer, target, samples)
    peak = _peak(track, samples)
    return None if peak is None else (track, peak)


@dataclass(frozen=True)
class Peak:
    """A body's highest point among the night's sample times."""

    time: Time
    altitude_degrees: float
    azimuth_degrees: float


def _track(observer, target, samples: Time) -> Track:
    """Where the body stands at each sample time."""
    positions = observer.at(samples).observe(target).apparent()
    altitudes, azimuths, _ = positions.altaz()
    return Track(positions, altitudes.degrees, azimuths.degrees)


def _peak(track: Track, samples: Time) -> Peak | None:
    """Where the body stands at its highest sample, or None if it never clears the horizon."""
    peak = int(track.altitudes_degrees.argmax())
    if track.altitudes_degrees[peak] <= 0:
        return None
    return Peak(
        samples[peak],
        float(track.altitudes_degrees[peak]),
        float(track.azimuths_degrees[peak]),
    )


def _visible_body(
    body: CatalogBody, observer, target, peak: Peak, magnitude: float | None
) -> VisibleBody:
    """The body's Detail Layer fields, with rise and set taken around its peak."""
    return VisibleBody(
        id=body.id,
        category=body.category,
        object_type=body.object_type,
        name=body.name,
        peak_altitude_degrees=peak.altitude_degrees,
        azimuth_at_peak_degrees=peak.azimuth_degrees,
        rises_at=rising_before(observer, target, peak.time),
        sets_at=setting_after(observer, target, peak.time),
        magnitude=magnitude,
        dso_type=body.dso_type,
    )


def rising_before(observer, target, peak_time: Time) -> datetime | None:
    """When the body rose for the pass that carries it to its Peak Altitude.

    None if it has not risen in the day before, meaning it never set: it is circumpolar tonight.
    """
    times, risen = almanac.find_risings(observer, target, peak_time - 1, peak_time)
    risings = [moment for moment, ok in zip(times, risen, strict=True) if ok]
    return to_utc(risings[-1]) if risings else None


def setting_after(observer, target, peak_time: Time) -> datetime | None:
    """When the body sets after its Peak Altitude, or None if it stays up for the next day."""
    times, set_ = almanac.find_settings(observer, target, peak_time, peak_time + 1)
    settings = [moment for moment, ok in zip(times, set_, strict=True) if ok]
    return to_utc(settings[0]) if settings else None


def to_utc(moment: Time) -> datetime:
    return moment.utc_datetime().astimezone(UTC).replace(microsecond=0)
