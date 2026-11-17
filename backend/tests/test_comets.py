import io
import math
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from skyfield.api import load
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc

from app.comets import (
    _NUMERIC_COLUMNS,
    _ORBIT_COLUMNS,
    NAMED_COMETS,
    PINNED_ELEMENTS_ENV,
    MpcElementsCache,
    _designation,
    named_comet_elements,
)

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)
NAMED_DESIGNATIONS = {comet.designation for comet in NAMED_COMETS}


class FakeFetch:
    """Stands in for the MPC download: returns the given bytes, or raises when there are none."""

    def __init__(self, payload: bytes | None) -> None:
        self.payload = payload
        self.calls = 0

    def __call__(self) -> bytes:
        self.calls += 1
        if self.payload is None:
            raise OSError("MPC unreachable")
        return self.payload


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def write_cache(path: Path, content: bytes, age: timedelta) -> None:
    path.write_bytes(content)
    modified = (NOW - age).timestamp()
    os.utime(path, (modified, modified))


@pytest.fixture
def elements(pinned_comet_elements: Path) -> bytes:
    return pinned_comet_elements.read_bytes()


def make_cache(tmp_path: Path, fetch: FakeFetch, clock: Clock | None = None) -> MpcElementsCache:
    return MpcElementsCache(tmp_path / "AllCometEls.txt", fetch=fetch, clock=clock or Clock(NOW))


def test_pinned_elements_file_supplies_all_11_named_comets(tmp_path: Path):
    found = named_comet_elements(tmp_path)

    assert set(found) == NAMED_DESIGNATIONS
    assert found["C/2020 F3 (NEOWISE)"].perihelion_year == 2020


def test_named_comets_are_the_11_from_the_research_doc():
    assert {comet.key for comet in NAMED_COMETS} == {
        "halley",
        "encke",
        "ikeya_zhang",
        "hale_bopp",
        "hyakutake",
        "neowise",
        "tsuchinshan_atlas",
        "west",
        "bennett",
        "ikeya_seki",
        "lovejoy",
    }


def test_missing_elements_are_downloaded_once_and_then_read_from_the_cache(
    tmp_path: Path, elements: bytes
):
    fetch = FakeFetch(elements)
    cache = make_cache(tmp_path, fetch)

    assert set(cache.named_comet_elements()) == NAMED_DESIGNATIONS
    assert set(cache.named_comet_elements()) == NAMED_DESIGNATIONS
    assert fetch.calls == 1
    assert (tmp_path / "AllCometEls.txt").read_bytes() == elements


def test_fresh_cache_is_used_without_any_network_call(tmp_path: Path, elements: bytes):
    write_cache(tmp_path / "AllCometEls.txt", elements, age=timedelta(days=29))
    fetch = FakeFetch(None)

    assert set(make_cache(tmp_path, fetch).named_comet_elements()) == NAMED_DESIGNATIONS
    assert fetch.calls == 0


def test_stale_cache_is_refreshed(tmp_path: Path, elements: bytes):
    write_cache(tmp_path / "AllCometEls.txt", b"", age=timedelta(days=31))
    fetch = FakeFetch(elements)

    assert set(make_cache(tmp_path, fetch).named_comet_elements()) == NAMED_DESIGNATIONS
    assert fetch.calls == 1


def test_stale_cache_that_cannot_be_refreshed_yields_no_comets(tmp_path: Path, elements: bytes):
    write_cache(tmp_path / "AllCometEls.txt", elements, age=timedelta(days=31))

    assert make_cache(tmp_path, FakeFetch(None)).named_comet_elements() == {}


def test_missing_elements_that_cannot_be_downloaded_yield_no_comets(tmp_path: Path):
    assert make_cache(tmp_path, FakeFetch(None)).named_comet_elements() == {}
    assert not (tmp_path / "AllCometEls.txt").exists()


def test_failed_download_is_not_retried_on_every_report(tmp_path: Path, elements: bytes):
    fetch = FakeFetch(None)
    clock = Clock(NOW)
    cache = make_cache(tmp_path, fetch, clock)
    cache.named_comet_elements()

    fetch.payload = elements
    clock.now = NOW + timedelta(minutes=10)
    assert cache.named_comet_elements() == {}
    clock.now = NOW + timedelta(hours=2)
    assert set(cache.named_comet_elements()) == NAMED_DESIGNATIONS
    assert fetch.calls == 2


def test_unreadable_elements_yield_no_comets(tmp_path: Path):
    write_cache(tmp_path / "AllCometEls.txt", b"<html>Service unavailable</html>", timedelta())

    assert make_cache(tmp_path, FakeFetch(None)).named_comet_elements() == {}


def test_pinned_elements_file_that_is_missing_yields_no_comets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv(PINNED_ELEMENTS_ENV, str(tmp_path / "nowhere.txt"))

    assert named_comet_elements(tmp_path) == {}


def test_elements_that_cannot_be_written_to_the_cache_yield_no_comets(
    tmp_path: Path, elements: bytes
):
    # The cache's parent is a file, so its directory cannot be created: a read-only data dir.
    blocker = tmp_path / "not-a-directory"
    blocker.write_bytes(b"")
    cache = MpcElementsCache(blocker / "AllCometEls.txt", fetch=FakeFetch(elements))

    assert cache.named_comet_elements() == {}


# Rows copied from the live AllCometEls.txt (downloaded 2026-11-10): three old comets whose
# columns are not the standard widths, Ikeya-Seki with its magnitude parameters left blank,
# NEOWISE, and a comet that is not a Named Comet.
IRREGULAR_ELEMENTS = Path(__file__).parent / "fixtures" / "comet_elements_irregular.txt"


def test_irregular_rows_in_the_elements_still_yield_numeric_named_comets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv(PINNED_ELEMENTS_ENV, str(IRREGULAR_ELEMENTS))

    found = named_comet_elements(tmp_path)

    assert set(found) == {"C/2020 F3 (NEOWISE)", "C/1965 S1-A (Ikeya-Seki)"}
    neowise = found["C/2020 F3 (NEOWISE)"]
    assert neowise.perihelion_year == 2020
    assert isinstance(neowise.perihelion_year, int)
    assert neowise.perihelion_day == pytest.approx(5.1107)
    assert neowise.magnitude_g == pytest.approx(7.5)
    assert neowise.magnitude_k == pytest.approx(5.2)


def test_named_comet_with_blank_magnitudes_has_nan_magnitudes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv(PINNED_ELEMENTS_ENV, str(IRREGULAR_ELEMENTS))

    ikeya_seki = named_comet_elements(tmp_path)["C/1965 S1-A (Ikeya-Seki)"]

    assert ikeya_seki.perihelion_year == 1965
    assert math.isnan(ikeya_seki.magnitude_g)
    assert math.isnan(ikeya_seki.magnitude_k)


# Our view of the MPC comet layout must agree with Skyfield's parser, or the Named Comets would
# drop out of reports with only a log warning, as in #40.


def skyfield_rows(content: bytes) -> pd.DataFrame:
    return mpc.load_comets_dataframe(io.BytesIO(content))


def test_skyfield_parses_every_column_we_read(elements: bytes):
    assert set(_NUMERIC_COLUMNS) <= set(skyfield_rows(elements).columns)


def test_skyfield_places_a_comet_from_our_orbit_columns_alone(elements: bytes):
    row = skyfield_rows(elements).iloc[0]

    mpc.comet_orbit(row[[*_ORBIT_COLUMNS, "designation"]], load.timescale(builtin=True), GM_SUN)


@pytest.mark.parametrize("column", _ORBIT_COLUMNS)
def test_skyfield_needs_each_of_our_orbit_columns(elements: bytes, column: str):
    row = skyfield_rows(elements).iloc[0].drop(column)

    with pytest.raises((AttributeError, KeyError)):
        mpc.comet_orbit(row, load.timescale(builtin=True), GM_SUN)


def test_our_designation_of_each_row_is_skyfields(elements: bytes):
    lines = elements.splitlines(keepends=True)

    ours = [_designation(line) for line in lines]

    assert ours == list(skyfield_rows(elements)["designation"])
    assert set(ours) == NAMED_DESIGNATIONS
