from datetime import UTC, date, datetime, timedelta

import pytest

from app.astronomy import compute_night_sky

# Published values: USNO "Astronomical Twilight for 2026" tables, retrieved 2026-11-04 from
# https://aa.usno.navy.mil/calculated/rstt/year (task=4). The tables print whole minutes in
# standard time, at the rounded coordinates in their header, which are the ones used here.
NEW_YORK = (40.7167, -74.0)  # N40 43, W074 00
SYDNEY = (-33.8667, 151.2167)  # S33 52, E151 13
PUBLISHED_TABLE_PRECISION = timedelta(seconds=90)


def utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    ("location", "timezone", "night", "published_start", "published_end"),
    [
        pytest.param(
            NEW_YORK,
            "America/New_York",
            date(2026, 6, 21),
            utc(2026, 6, 22, 2, 37),  # 21:37 EST
            utc(2026, 6, 22, 7, 19),  # 02:19 EST
            id="new-york-summer",
        ),
        pytest.param(
            NEW_YORK,
            "America/New_York",
            date(2026, 1, 20),
            utc(2026, 1, 20, 23, 35),  # 18:35 EST
            utc(2026, 1, 21, 10, 39),  # 05:39 EST
            id="new-york-winter",
        ),
        pytest.param(
            SYDNEY,
            "Australia/Sydney",
            date(2026, 6, 21),
            utc(2026, 6, 21, 8, 23),  # 18:23 AEST
            utc(2026, 6, 21, 19, 31),  # 05:31 AEST on 22 June
            id="sydney-winter",
        ),
    ],
)
def test_viewing_window_matches_published_astronomical_twilight(
    location, timezone, night, published_start, published_end
):
    latitude, longitude = location

    sky = compute_night_sky(latitude, longitude, timezone, night)

    window = sky.viewing_window
    assert abs(window.starts_at - published_start) <= PUBLISHED_TABLE_PRECISION
    assert abs(window.ends_at - published_end) <= PUBLISHED_TABLE_PRECISION


def test_night_without_astronomical_darkness_has_zero_length_viewing_window_at_darkest_moment():
    # Tromso at midsummer: the midnight sun. Darkest at solar midnight, 22:44 UTC from its
    # longitude (18.96 E -> 1h16m ahead of Greenwich) plus about 2 min equation of time.
    sky = compute_night_sky(69.65, 18.96, "Europe/Oslo", date(2026, 6, 21))

    window = sky.viewing_window
    assert window.starts_at == window.ends_at
    assert abs(window.starts_at - utc(2026, 6, 21, 22, 46)) <= timedelta(minutes=5)
    assert sky.highlights == []
    assert sky.visible_objects == []


def test_night_at_lower_latitude_can_also_lack_astronomical_darkness():
    # London at midsummer never reaches -18 degrees, so it is not only a polar case.
    sky = compute_night_sky(51.5074, -0.1278, "Europe/London", date(2026, 6, 21))

    assert sky.viewing_window.starts_at == sky.viewing_window.ends_at


@pytest.mark.parametrize(
    ("latitude", "night"),
    [
        pytest.param(90.0, date(2026, 6, 21), id="north-pole-midsummer"),
        pytest.param(-90.0, date(2026, 12, 21), id="south-pole-midsummer"),
        pytest.param(90.0, date(2026, 4, 15), id="north-pole-spring"),
        pytest.param(89.99, date(2026, 8, 20), id="near-north-pole-late-summer"),
    ],
)
def test_night_without_astronomical_darkness_at_the_poles_has_zero_length_viewing_window(
    latitude, night
):
    # The Sun's altitude barely changes over a polar day, so it may have no daily low point.
    sky = compute_night_sky(latitude, 0.0, "Etc/UTC", night)

    window = sky.viewing_window
    assert window.starts_at == window.ends_at
    assert datetime(night.year, night.month, night.day, 12, tzinfo=UTC) <= window.starts_at


def test_polar_night_viewing_window_spans_local_noon_to_local_noon():
    # The South Pole at midwinter: the Sun stays near -23.4 degrees all day.
    sky = compute_night_sky(-90.0, 0.0, "Antarctica/South_Pole", date(2026, 6, 21))

    assert sky.viewing_window.starts_at == utc(2026, 6, 21, 0, 0)  # 12:00 NZST
    assert sky.viewing_window.ends_at == utc(2026, 6, 22, 0, 0)
