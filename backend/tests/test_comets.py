import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.comets import NAMED_COMETS, MpcElementsCache, named_comet_elements

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
    monkeypatch.setenv("STARCAST_COMET_ELEMENTS", str(tmp_path / "nowhere.txt"))

    assert named_comet_elements(tmp_path) == {}
