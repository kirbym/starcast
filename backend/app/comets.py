"""The Named Comets and the MPC orbital elements that place them in the sky.

The elements come from the Minor Planet Center's AllCometEls.txt, downloaded on first use and
kept in the data directory. Unlike its CometEls.txt, which lists only comets under current
observation, it covers every Named Comet, including long-gone ones like Comet West. See
docs/research/comet-catalog.md.
"""

import io
import logging
import math
import os
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Self

import pandas as pd
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc
from skyfield.timelib import Time, Timescale
from skyfield.vectorlib import VectorFunction

ELEMENTS_URL = "https://www.minorplanetcenter.net/iau/MPCORB/AllCometEls.txt"
ELEMENTS_FILE = "AllCometEls.txt"
# Set to an MPC comet elements file to use it instead of downloading, never refreshing it.
PINNED_ELEMENTS_ENV = "STARCAST_COMET_ELEMENTS"
# Older elements count as stale. Unless a refresh succeeds, the comets are left out.
MAX_AGE = timedelta(days=30)
# After a failed download, reports go without comets for this long before the next attempt.
RETRY_AFTER = timedelta(hours=1)
_DOWNLOAD_TIMEOUT_SECONDS = 30

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NamedComet:
    key: str
    name: str
    # The full designation the MPC files it under, name included, as in "1P/Halley".
    designation: str

    @property
    def short_designation(self) -> str:
        """The designation without the comet's name, as in "C/2020 F3"."""
        return self.designation.split(" (")[0]


@dataclass(frozen=True)
class CometElements:
    """A comet's MPC orbital elements, with the types the astronomy engine relies on.

    The magnitude parameters are NaN where the MPC leaves them blank. Each field is named as
    Skyfield's MPC parser names its column, and tests/test_comets.py checks it against ours.
    """

    designation: str
    perihelion_year: int
    perihelion_month: int
    perihelion_day: float
    perihelion_distance_au: float
    eccentricity: float
    argument_of_perihelion_degrees: float
    longitude_of_ascending_node_degrees: float
    inclination_degrees: float
    magnitude_g: float
    magnitude_k: float

    def to_skyfield_row(self) -> pd.Series:
        """The elements as the row skyfield.data.mpc.comet_orbit takes."""
        return pd.Series(asdict(self))


# A Named Comet fainter than this, the naked-eye limit, is not Visible however high it climbs.
COMET_MAGNITUDE_LIMIT = 6.0


@dataclass(frozen=True)
class CometOrbit:
    """Where a Named Comet is, and how bright, from its MPC orbital elements.

    This is the Named Comet's placement for the astronomy engine: what to observe, its magnitude
    at a moment, whether that magnitude is bright enough to count as Visible, and what the
    Narrator is told about it.
    """

    elements: CometElements
    # Centred on the Sun, as MPC comet orbits are.
    orbit: VectorFunction
    # The comet itself, placed in the Solar System.
    target: VectorFunction
    perihelion_date: str

    @classmethod
    def place(cls, elements: CometElements, sun: VectorFunction, timescale: Timescale) -> Self:
        """The comet's orbit, raising if the elements cannot place it.

        The orbit is propagated once here, at perihelion, so that unusable elements fail now
        rather than partway through observing the night.
        """
        orbit = mpc.comet_orbit(elements.to_skyfield_row(), timescale, GM_SUN)
        perihelion = timescale.tt(
            elements.perihelion_year, elements.perihelion_month, elements.perihelion_day
        )
        orbit.at(perihelion)
        return cls(elements, orbit, sun + orbit, perihelion.utc_datetime().date().isoformat())

    def magnitude(self, observer: VectorFunction, moment: Time) -> float:
        """The MPC's total-magnitude law: m = H + 5 log10(delta) + 2.5 K log10(r).

        delta is the comet's distance from the observer and r its distance from the Sun, in AU.
        The result is NaN if the elements carry no magnitude parameters.
        """
        delta = observer.at(moment).observe(self.target).distance().au
        r = self.orbit.at(moment).distance().au
        return float(
            self.elements.magnitude_g
            + 5 * math.log10(delta)
            + 2.5 * self.elements.magnitude_k * math.log10(r)
        )

    def is_visible(self, magnitude: float | None) -> bool:
        """Only a comet no fainter than the naked-eye limit counts; a NaN magnitude never does."""
        return magnitude is not None and magnitude <= COMET_MAGNITUDE_LIMIT

    def context(self) -> dict[str, str | float]:
        return {"perihelion_date": self.perihelion_date}


# Comet West and Ikeya-Seki broke apart near the Sun; each is followed by its main fragment, A.
NAMED_COMETS = (
    NamedComet("halley", "Halley's Comet", "1P/Halley"),
    NamedComet("encke", "Comet Encke", "2P/Encke"),
    NamedComet("ikeya_zhang", "Comet Ikeya-Zhang", "153P/Ikeya-Zhang"),
    NamedComet("hale_bopp", "Comet Hale-Bopp", "C/1995 O1 (Hale-Bopp)"),
    NamedComet("hyakutake", "Comet Hyakutake", "C/1996 B2 (Hyakutake)"),
    NamedComet("neowise", "Comet NEOWISE", "C/2020 F3 (NEOWISE)"),
    NamedComet("tsuchinshan_atlas", "Comet Tsuchinshan-ATLAS", "C/2023 A3 (Tsuchinshan-ATLAS)"),
    NamedComet("west", "Comet West", "C/1975 V1-A (West)"),
    NamedComet("bennett", "Comet Bennett", "C/1969 Y1 (Bennett)"),
    NamedComet("ikeya_seki", "Comet Ikeya-Seki", "C/1965 S1-A (Ikeya-Seki)"),
    NamedComet("lovejoy", "Comet Lovejoy", "C/2014 Q2 (Lovejoy)"),
)
_NAMED_DESIGNATIONS = frozenset(comet.designation for comet in NAMED_COMETS)

# The columns that place a comet. A row missing any of them cannot be used. Skyfield keeps no
# list of them, so this one is ours, and tests/test_comets.py checks it against Skyfield.
_ORBIT_COLUMNS = (
    "perihelion_year",
    "perihelion_month",
    "perihelion_day",
    "perihelion_distance_au",
    "eccentricity",
    "argument_of_perihelion_degrees",
    "longitude_of_ascending_node_degrees",
    "inclination_degrees",
)
# Blank in some rows, so read as NaN. A comet of unknown brightness is never Visible.
_MAGNITUDE_COLUMNS = ("magnitude_g", "magnitude_k")
_NUMERIC_COLUMNS = _ORBIT_COLUMNS + _MAGNITUDE_COLUMNS
# Where a row of the MPC comet format keeps the designation and name, read from Skyfield's own
# layout of the format so the two cannot drift apart. Skyfield keeps that layout private, so if
# it is renamed, importing this module fails rather than every Named Comet quietly going missing.
_DESIGNATION_FIELD = slice(*dict(mpc._COMET_COLUMNS)["designation"])


def named_comet_elements(cache_dir: Path) -> dict[str, CometElements]:
    """The orbital elements of each Named Comet, by MPC designation.

    A comet the elements do not cover is missing. If no usable elements can be had, the result
    is empty and the night goes on without comets.
    """
    pinned = os.environ.get(PINNED_ELEMENTS_ENV)
    if pinned:
        return _read_elements(Path(pinned))
    return _cache_in(cache_dir).named_comet_elements()


@lru_cache
def _cache_in(cache_dir: Path) -> "MpcElementsCache":
    """One cache per directory for the life of the process, so its retry back-off persists."""
    return MpcElementsCache(cache_dir / ELEMENTS_FILE)


def _download() -> bytes:
    """Fetch AllCometEls.txt from the MPC."""
    with urllib.request.urlopen(ELEMENTS_URL, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
        return response.read()


class MpcElementsCache:
    """The MPC elements file on disk, downloaded when missing and refreshed when stale.

    Once a fresh copy is cached, reports make no network calls.
    """

    def __init__(
        self,
        path: Path,
        fetch: Callable[[], bytes] = _download,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._path = path
        self._fetch = fetch
        self._clock = clock
        self._failed_at: datetime | None = None

    def named_comet_elements(self) -> dict[str, CometElements]:
        if not self._is_fresh() and not self._refresh():
            return {}
        return _read_elements(self._path)

    def _is_fresh(self) -> bool:
        try:
            modified = datetime.fromtimestamp(self._path.stat().st_mtime, UTC)
        except OSError:
            return False
        return self._clock() - modified <= MAX_AGE

    def _refresh(self) -> bool:
        """Download the elements over the cached copy. False if that fails."""
        now = self._clock()
        if self._failed_at is not None and now - self._failed_at < RETRY_AFTER:
            return False
        try:
            content = self._fetch()
            if not _parse_named(content):
                raise ValueError("no Named Comet found in the downloaded elements")
            self._path.parent.mkdir(parents=True, exist_ok=True)
            partial = self._path.with_suffix(".part")
            partial.write_bytes(content)
            partial.replace(self._path)
        except Exception:
            _log.warning("Could not refresh comet elements from %s", ELEMENTS_URL, exc_info=True)
            self._failed_at = now
            return False
        self._failed_at = None
        return True


def _read_elements(path: Path) -> dict[str, CometElements]:
    try:
        stat = path.stat()
    except OSError:
        _log.warning("No comet elements at %s", path)
        return {}
    return _read_elements_version(path, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=4)
def _read_elements_version(path: Path, _mtime_ns: int, _size: int) -> dict[str, CometElements]:
    """Parse one version of an elements file; a new modification time or size parses again."""
    try:
        content = path.read_bytes()
    except OSError:
        _log.warning("Could not read the comet elements at %s", path, exc_info=True)
        return {}
    elements = _parse_named(content)
    if not elements:
        _log.warning("No Named Comet found in the comet elements at %s", path)
    return elements


def _parse_named(content: bytes) -> dict[str, CometElements]:
    """The Named Comets' usable elements in an MPC comet elements file, by designation.

    Empty if the file holds no Named Comet or cannot be parsed.
    """
    rows = _select_named_rows(content)
    if rows is None:
        return {}
    return {elements.designation: elements for elements in _coerce_elements(rows)}


def _select_named_rows(content: bytes) -> pd.DataFrame | None:
    """The Named Comets' rows of an MPC comet elements file, as Skyfield parses them.

    Some old comets' rows in AllCometEls.txt do not keep the standard column widths, and pandas
    would then read every column as text. So only the Named Comets' rows are handed to Skyfield.
    None if there are none, or Skyfield cannot parse them.
    """
    named_lines = b"".join(
        line
        for line in content.splitlines(keepends=True)
        if _designation(line) in _NAMED_DESIGNATIONS
    )
    if not named_lines:
        return None
    try:
        return mpc.load_comets_dataframe(io.BytesIO(named_lines))
    except Exception:
        return None


def _coerce_elements(rows: pd.DataFrame) -> list[CometElements]:
    """The Named Comets' typed elements, from their parsed rows.

    Numeric columns become numbers, so a blank magnitude parameter becomes NaN; a row whose orbit
    cannot be read is dropped; and each field takes its declared type, so the perihelion year and
    month become integers.
    """
    for column in _NUMERIC_COLUMNS:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    rows = rows.dropna(subset=list(_ORBIT_COLUMNS))
    return [
        CometElements(
            **{field.name: field.type(row[field.name]) for field in fields(CometElements)}
        )
        for _, row in rows.iterrows()
    ]


def _designation(line: bytes) -> str:
    """The designation and name a row is filed under, as in "C/2020 F3 (NEOWISE)"."""
    return line[_DESIGNATION_FIELD].decode("ascii", errors="replace").strip()
