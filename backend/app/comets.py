"""The Named Comets and the MPC orbital elements that place them in the sky.

The elements come from the Minor Planet Center's AllCometEls.txt, downloaded on first use and
kept in the data directory. Unlike its CometEls.txt, which lists only comets under current
observation, it covers every Named Comet, including long-gone ones like Comet West. See
docs/research/comet-catalog.md.
"""

import io
import logging
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd
from skyfield.data import mpc

ELEMENTS_URL = "https://www.minorplanetcenter.net/iau/MPCORB/AllCometEls.txt"
ELEMENTS_FILE = "AllCometEls.txt"
# Set to an MPC comet elements file to use it instead of downloading, never refreshing it.
PINNED_ELEMENTS_ENV = "STARCAST_COMET_ELEMENTS"
# Older elements count as stale. Unless a refresh succeeds, the comets are left out.
MAX_AGE = timedelta(days=30)
# After a failed download, reports go without comets for this long before the next attempt.
RETRY_AFTER = timedelta(hours=1)
_DOWNLOAD_TIMEOUT_SECONDS = 30

# One comet's row of MPC orbital elements, as skyfield.data.mpc parses it.
CometElements = pd.Series

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
    return MpcElementsCache(cache_dir / ELEMENTS_FILE)


def _download() -> bytes:
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
        except FileNotFoundError:
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
        except Exception:
            _log.warning("Could not download comet elements from %s", ELEMENTS_URL, exc_info=True)
            self._failed_at = now
            return False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        partial = self._path.with_suffix(".part")
        partial.write_bytes(content)
        partial.replace(self._path)
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
    elements = _parse_named(path.read_bytes())
    if not elements:
        _log.warning("No Named Comet found in the comet elements at %s", path)
    return elements


def _parse_named(content: bytes) -> dict[str, CometElements]:
    """The Named Comets' rows in an MPC comet elements file, or none if it cannot be parsed."""
    try:
        rows = mpc.load_comets_dataframe(io.BytesIO(content))
    except Exception:
        return {}
    return {
        row["designation"]: row
        for _, row in rows.iterrows()
        if row["designation"] in _NAMED_DESIGNATIONS
    }
