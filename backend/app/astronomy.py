"""The astronomy engine: location + timezone + date -> the night's computed sky."""

import csv
import logging
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
from skyfield import almanac
from skyfield.api import Loader, Star, load, wgs84
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc
from skyfield.jpllib import SpiceKernel
from skyfield.magnitudelib import planetary_magnitude
from skyfield.positionlib import Apparent
from skyfield.timelib import Time
from skyfield.toposlib import GeographicPosition
from skyfield.vectorlib import VectorFunction

from app.comets import NAMED_COMETS, CometElements, NamedComet, named_comet_elements

_log = logging.getLogger(__name__)

EPHEMERIS_FILE = "de440s.bsp"
DARK = 0  # The code almanac.dark_twilight_day() uses for "Sun below -18 degrees".
_MINUTES_IN_SEARCH = 24 * 60 + 1
# Every body's Peak Altitude comes from the same sample times, spaced this far apart.
_SAMPLE_SPACING = timedelta(minutes=5)
# A Named Comet fainter than this, the naked-eye limit, is not Visible however high it climbs.
COMET_MAGNITUDE_LIMIT = 6.0
# Two bodies at most this far apart, both above the horizon at that moment, are in conjunction.
CONJUNCTION_LIMIT_DEGREES = 2.0

Category = Literal["planet_moon", "constellation", "featured"]
ObjectType = Literal[
    "planet", "moon", "constellation", "bright_star", "comet", "dso", "significant_event"
]
EventType = Literal["conjunction", "opposition", "meteor_shower"]

# The bodies that move against the stars. Only they can start a conjunction.
_MOVING_TYPES = frozenset({"planet", "moon", "comet"})


_CATEGORIES: dict[ObjectType, Category] = {
    "planet": "planet_moon",
    "moon": "planet_moon",
    "constellation": "constellation",
    "bright_star": "featured",
    "comet": "featured",
    "dso": "featured",
}

# Catalog facts about a body that the Narrator can draw on, like a star's spectral type.
NarrationContext = Mapping[str, str | float]


@dataclass(frozen=True)
class CatalogBody:
    object_type: ObjectType
    key: str
    name: str
    # A segment name in the ephemeris for a moving body, a fixed J2000 point, like a Centroid, or
    # a Named Comet, which its MPC orbital elements place for the night.
    target: str | Star | NamedComet
    # A fixed body's catalog magnitude. A moving body's is computed for the night instead.
    magnitude: float | None = None
    context: NarrationContext | None = None

    @property
    def id(self) -> str:
        return f"{self.object_type}:{self.key}"

    @property
    def category(self) -> Category:
        return _CATEGORIES[self.object_type]

    @property
    def is_fixed(self) -> bool:
        """Whether the body sits at a fixed J2000 point rather than moving through the ephemeris."""
        return isinstance(self.target, Star)


@dataclass(frozen=True)
class Catalog:
    """Every In Catalog body, grouped by the Category whose Highlight it competes for."""

    planets_and_moon: tuple[CatalogBody, ...]
    constellations: tuple[CatalogBody, ...]
    # The standing Category 3 candidates: the Bright Stars, Named Comets and DSOs.
    featured: tuple[CatalogBody, ...]


# DE440s carries Mars and the outer planets only as barycenters of their systems.
_SOLAR_SYSTEM = (
    CatalogBody("planet", "mercury", "Mercury", "mercury"),
    CatalogBody("planet", "venus", "Venus", "venus"),
    CatalogBody("planet", "mars", "Mars", "mars barycenter"),
    CatalogBody("planet", "jupiter", "Jupiter", "jupiter barycenter"),
    CatalogBody("planet", "saturn", "Saturn", "saturn barycenter"),
    CatalogBody("planet", "uranus", "Uranus", "uranus barycenter"),
    CatalogBody("planet", "neptune", "Neptune", "neptune barycenter"),
    CatalogBody("moon", "moon", "Moon", "moon"),
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

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _read_data_file(name: str) -> list[dict[str, str]]:
    """The rows of a bundled CSV data file, skipping its `#` header comments."""
    with (_DATA_DIR / name).open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(line for line in file if not line.startswith("#")))


def _fixed_point(row: dict[str, str]) -> Star:
    return Star(ra_hours=float(row["ra_hours"]), dec_degrees=float(row["dec_degrees"]))


def _load_constellations() -> tuple[CatalogBody, ...]:
    """The 88 Named Constellations, each placed at its Centroid.

    The file is generated by scripts/build_constellation_centroids.py; see
    docs/research/constellation-centroids.md.
    """
    return tuple(
        CatalogBody("constellation", row["key"], row["name"], _fixed_point(row))
        for row in _read_data_file("constellations.csv")
    )


def _load_bright_stars() -> tuple[CatalogBody, ...]:
    """The Bright Stars: every IAU-named star at V <= 2.50, at its J2000 position.

    The file is generated by scripts/build_bright_stars.py from the HYG Database (CC BY-SA 4.0);
    see docs/research/bright-stars-catalog.md.
    """
    return tuple(
        CatalogBody(
            "bright_star",
            row["key"],
            row["name"],
            _fixed_point(row),
            magnitude=float(row["magnitude"]),
            context=_star_context(row),
        )
        for row in _read_data_file("bright_stars.csv")
    )


def _star_context(row: dict[str, str]) -> NarrationContext:
    """What the Narrator may weave in about a star: its designation, colour and distance."""
    context: dict[str, str | float] = {
        "bayer_designation": row["bayer"],
        "constellation": row["constellation"],
        "spectral_type": row["spectral_type"],
    }
    if row["color_index"]:
        context["color_index_b_v"] = float(row["color_index"])
    if row["distance_light_years"]:
        context["distance_light_years"] = float(row["distance_light_years"])
    return context


def _load_dsos() -> tuple[CatalogBody, ...]:
    """The DSOs, M1 to M110, each placed at its Centroid.

    A DSO goes by its common name, or by its Messier number when it has none. The file is
    generated by scripts/build_messier.py from OpenNGC (CC BY-SA 4.0); see
    docs/research/messier-catalog.md.
    """
    return tuple(
        CatalogBody(
            "dso",
            row["key"],
            row["common_name"] or row["messier"],
            _fixed_point(row),
            magnitude=float(row["magnitude"]),
            context=_dso_context(row),
        )
        for row in _read_data_file("messier.csv")
    )


def _dso_context(row: dict[str, str]) -> NarrationContext:
    """What the Narrator may weave in about a DSO: its designations, kind and apparent size."""
    context: dict[str, str | float] = {"messier": row["messier"]}
    if row["designation"]:
        context["designation"] = row["designation"]
    context["type"] = row["type"]
    context["constellation"] = row["constellation"]
    if row["major_axis_arcmin"]:
        context["size_arcminutes"] = float(row["major_axis_arcmin"])
    return context


def _named_comets() -> tuple[CatalogBody, ...]:
    """The Named Comets. Their magnitude, like their position, is computed for the night."""
    return tuple(
        CatalogBody(
            "comet",
            comet.key,
            comet.name,
            comet,
            context={"designation": comet.short_designation},
        )
        for comet in NAMED_COMETS
    )


CATALOG = Catalog(
    planets_and_moon=_SOLAR_SYSTEM,
    constellations=_load_constellations(),
    featured=_load_bright_stars() + _named_comets() + _load_dsos(),
)

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / ".cache" / "skyfield"
_timescale = load.timescale(builtin=True)


@dataclass(frozen=True)
class ViewingWindow:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class SignificantEvent:
    """What makes a Significant Event Highlight time-sensitive: what happens, and when."""

    event_type: EventType
    # The moment the event is at its best, such as a conjunction's closest approach.
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
    # Narration-only facts from the catalog; not part of the API's positional fields.
    context: NarrationContext | None = None


@dataclass(frozen=True)
class NightSky:
    viewing_window: ViewingWindow
    highlights: list[VisibleBody] = field(default_factory=list)
    visible_objects: list[VisibleBody] = field(default_factory=list)


def data_dir() -> Path:
    """Where downloaded astronomy data, the ephemeris and the comet elements, is kept."""
    return Path(os.environ.get("STARCAST_DATA_DIR", _DEFAULT_DATA_DIR))


@lru_cache(maxsize=1)
def _ephemeris() -> SpiceKernel:
    """Load DE440s, downloading it to the data directory on first use."""
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return Loader(str(directory), verbose=False)(EPHEMERIS_FILE)


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

    observer = _ephemeris()["earth"] + wgs84.latlon(latitude, longitude)
    samples = _sample_times(window)
    planets_and_moon = _observe_visible(catalog.planets_and_moon, observer, samples)
    constellations = _observe_visible(catalog.constellations, observer, samples)
    featured = _observe_visible(catalog.featured, observer, samples, _comet_elements(catalog))
    category_1 = max(planets_and_moon, key=_category_1_priority, default=None)
    category_2 = max(constellations, key=_category_2_priority, default=None)
    category_3 = _category_3_highlight(planets_and_moon + featured, samples)
    highlights = [seen.body for seen in (category_1, category_2) if seen]
    if category_3:
        highlights.append(category_3)
    return NightSky(
        viewing_window=window,
        highlights=highlights,
        visible_objects=[seen.body for seen in planets_and_moon + constellations + featured],
    )


@dataclass(frozen=True)
class _Track:
    """Where a body stands at each of the night's sample times."""

    positions: Apparent
    altitudes_degrees: np.ndarray
    azimuths_degrees: np.ndarray


@dataclass(frozen=True)
class _Observation:
    catalog_body: CatalogBody
    body: VisibleBody
    peak_time: Time
    track: _Track


def _observe_visible(
    bodies: tuple[CatalogBody, ...],
    observer,
    samples: Time,
    comet_elements: Mapping[str, CometElements] | None = None,
) -> list[_Observation]:
    """Every one of the bodies that is Visible across the sample times.

    A Named Comet without orbital elements cannot be placed, so it is left out.
    """
    observed = []
    for body in bodies:
        if isinstance(body.target, NamedComet):
            seen = _observe_named_comet(body, comet_elements or {}, observer, samples)
        else:
            seen = _observe(body, observer, samples)
        if seen:
            observed.append(seen)
    return observed


def _observe_named_comet(
    body: CatalogBody, comet_elements: Mapping[str, CometElements], observer, samples: Time
) -> _Observation | None:
    """Place one Named Comet, leaving it out if its elements are missing or unusable."""
    elements = comet_elements.get(body.target.designation)
    if elements is None:
        return None
    try:
        return _observe_comet(body, elements, observer, samples)
    except Exception:
        _log.warning("Could not place %s from its orbital elements", body.id, exc_info=True)
        return None


def _comet_elements(catalog: Catalog) -> Mapping[str, CometElements]:
    """The Named Comets' orbital elements, if the catalog has any Named Comets to place."""
    if not any(isinstance(body.target, NamedComet) for body in catalog.featured):
        return {}
    return named_comet_elements(data_dir())


def _category_3_highlight(observed: list[_Observation], samples: Time) -> VisibleBody | None:
    """Category 3: a Significant Event wins outright; otherwise the best standing body.

    `observed` is every Visible body of the night outside Category 2. The standing candidates
    among them are the featured ones: the Bright Stars, Named Comets and DSOs.
    """
    event = _significant_event(observed, samples)
    if event:
        return event
    standing = [seen for seen in observed if seen.body.category == "featured"]
    best = max(standing, key=_category_3_priority, default=None)
    return best.body if best else None


def _significant_event(observed: list[_Observation], samples: Time) -> VisibleBody | None:
    """The night's one Significant Event Highlight: for now, its tightest conjunction."""
    tightest = min(
        _conjunctions(observed, samples), key=lambda found: found.separation_degrees, default=None
    )
    return tightest.highlight if tightest else None


@dataclass(frozen=True)
class _Conjunction:
    separation_degrees: float
    highlight: VisibleBody


def _conjunctions(observed: list[_Observation], samples: Time) -> list[_Conjunction]:
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


def _conjunction(first: _Observation, second: _Observation, samples: Time) -> _Conjunction | None:
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
    highlight = VisibleBody(
        id=f"significant_event:conjunction_{first.catalog_body.key}_{second.catalog_body.key}",
        category="featured",
        object_type="significant_event",
        name=f"{first.body.name} and {second.body.name} in conjunction",
        # The pair stands within a couple of degrees of the first body: look there.
        peak_altitude_degrees=float(first.track.altitudes_degrees[closest]),
        azimuth_at_peak_degrees=float(first.track.azimuths_degrees[closest]),
        # The span over which both bodies are up together.
        rises_at=max((body.rises_at for body in pair if body.rises_at), default=None),
        sets_at=min((body.sets_at for body in pair if body.sets_at), default=None),
        magnitude=None,
        event=SignificantEvent(
            event_type="conjunction",
            peak_time=_to_utc(samples[closest]),
            related_object_names=(first.body.name, second.body.name),
        ),
        context={"separation_degrees": round(separation, 2)},
    )
    return _Conjunction(separation, highlight)


def _category_3_priority(seen: _Observation) -> tuple[float, float]:
    """Visual Priority for standing Category 3 bodies: the larger tuple wins.

    The brightest body (the lowest magnitude) wins, with Peak Altitude breaking ties. A body with
    no known magnitude ranks below every body with one.
    """
    magnitude = seen.body.magnitude
    brightness = -math.inf if magnitude is None else -magnitude
    return brightness, seen.body.peak_altitude_degrees


def _category_2_priority(seen: _Observation) -> float:
    """Visual Priority for Category 2: the highest Peak Altitude wins."""
    return seen.body.peak_altitude_degrees


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


def _observe(body: CatalogBody, observer, samples: Time) -> _Observation | None:
    """Position one body over the night, or None if it never clears the horizon."""
    target = body.target if body.is_fixed else _ephemeris()[body.target]
    track = _track(observer, target, samples)
    peak = _peak(track, samples)
    if peak is None:
        return None
    magnitude = _magnitude(body, observer, target, peak.time)
    visible = _visible_body(body, observer, target, peak, magnitude)
    return _Observation(body, visible, peak.time, track)


def _observe_comet(
    body: CatalogBody, elements: CometElements, observer, samples: Time
) -> _Observation | None:
    """Place a Named Comet from its orbital elements, or None if it is not Visible that night.

    A Named Comet counts only when it is no fainter than the naked-eye limit at its Peak Altitude.
    """
    # MPC comet orbits are centred on the Sun, not on the Solar System's barycenter.
    orbit = mpc.comet_orbit(elements, _timescale, GM_SUN)
    target = _ephemeris()["sun"] + orbit
    track = _track(observer, target, samples)
    peak = _peak(track, samples)
    if peak is None:
        return None
    magnitude = _comet_magnitude(elements, orbit, observer, target, peak.time)
    # A NaN magnitude, from elements without magnitude parameters, fails this test too.
    if not magnitude <= COMET_MAGNITUDE_LIMIT:
        return None
    visible = _visible_body(body, observer, target, peak, magnitude)
    context = {**(body.context or {}), "perihelion_date": _perihelion_date(elements)}
    return _Observation(body, replace(visible, context=context), peak.time, track)


@dataclass(frozen=True)
class _Peak:
    """A body's highest point among the night's sample times."""

    time: Time
    altitude_degrees: float
    azimuth_degrees: float


def _track(observer, target, samples: Time) -> _Track:
    """Where the body stands at each sample time."""
    positions = observer.at(samples).observe(target).apparent()
    altitudes, azimuths, _ = positions.altaz()
    return _Track(positions, altitudes.degrees, azimuths.degrees)


def _peak(track: _Track, samples: Time) -> _Peak | None:
    """Where the body stands at its highest sample, or None if it never clears the horizon."""
    peak = int(track.altitudes_degrees.argmax())
    if track.altitudes_degrees[peak] <= 0:
        return None
    return _Peak(
        samples[peak],
        float(track.altitudes_degrees[peak]),
        float(track.azimuths_degrees[peak]),
    )


def _visible_body(
    body: CatalogBody, observer, target, peak: _Peak, magnitude: float | None
) -> VisibleBody:
    """The body's Detail Layer fields, with rise and set taken around its peak."""
    return VisibleBody(
        id=body.id,
        category=body.category,
        object_type=body.object_type,
        name=body.name,
        peak_altitude_degrees=peak.altitude_degrees,
        azimuth_at_peak_degrees=peak.azimuth_degrees,
        rises_at=_rising_before(observer, target, peak.time),
        sets_at=_setting_after(observer, target, peak.time),
        magnitude=magnitude,
        context=body.context,
    )


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


def _magnitude(body: CatalogBody, observer, target, moment: Time) -> float | None:
    """The body's apparent magnitude, or None where it has none, as for a Named Constellation.

    A fixed body's magnitude comes from the catalog; a moving body's is computed for the moment.
    """
    if body.is_fixed:
        return body.magnitude
    if body.object_type == "moon":
        return _moon_magnitude(observer, target, moment)
    magnitude = float(planetary_magnitude(observer.at(moment).observe(target)))
    # Skyfield has no formula for Saturn at large phase angles, and returns NaN there.
    return None if math.isnan(magnitude) else magnitude


def _comet_magnitude(
    elements: CometElements, orbit: VectorFunction, observer, comet, moment: Time
) -> float:
    """The MPC's total-magnitude law for a comet: m = H + 5 log10(delta) + 2.5 K log10(r).

    delta is the comet's distance from the observer and r its distance from the Sun, in AU. The
    result is NaN if the elements carry no magnitude parameters.
    """
    delta = observer.at(moment).observe(comet).distance().au
    r = orbit.at(moment).distance().au
    return float(
        elements.magnitude_g + 5 * math.log10(delta) + 2.5 * elements.magnitude_k * math.log10(r)
    )


def _perihelion_date(elements: CometElements) -> str:
    """The date of the perihelion passage the elements describe, as YYYY-MM-DD."""
    perihelion = _timescale.tt(
        int(elements.perihelion_year), int(elements.perihelion_month), elements.perihelion_day
    )
    return perihelion.utc_datetime().date().isoformat()


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
