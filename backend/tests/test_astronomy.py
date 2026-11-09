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


def visible_ids(sky) -> set[str]:
    return {body.id for body in sky.visible_objects}


def visible_body(sky, body_id: str):
    return next(body for body in sky.visible_objects if body.id == body_id)


def test_visible_planets_and_moon_carry_their_positional_fields():
    # Early November 2026 from New York: Mars, Jupiter and Saturn are well up in the night, and a
    # thin waning crescent Moon rises before dawn. Venus is just past inferior conjunction.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))

    assert {"planet:mars", "planet:jupiter", "planet:saturn", "moon:moon"} <= visible_ids(sky)

    jupiter = visible_body(sky, "planet:jupiter")
    assert jupiter.category == "planet_moon"
    assert jupiter.object_type == "planet"
    assert jupiter.name == "Jupiter"
    # Jupiter sits near declination +15 in Cancer, so it can climb to about 64 degrees here.
    assert 40 < jupiter.peak_altitude_degrees < 65
    assert 0 <= jupiter.azimuth_at_peak_degrees < 360
    # It rises late in the evening and is still up at dawn, setting the next afternoon.
    window = sky.viewing_window
    assert jupiter.rises_at is not None and jupiter.rises_at < window.ends_at
    assert jupiter.sets_at is not None and jupiter.sets_at > window.ends_at
    assert -2.6 < jupiter.magnitude < -1.8

    moon = visible_body(sky, "moon:moon")
    assert moon.object_type == "moon"
    assert moon.name == "Moon"
    # A crescent Moon is far fainter than a full one (about -12.7).
    assert -10 < moon.magnitude < -6


def test_body_that_never_clears_the_horizon_in_the_viewing_window_is_absent():
    # Venus passed inferior conjunction in late October 2026 and is lost in the Sun's glare.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))

    assert "planet:venus" not in visible_ids(sky)
    assert "planet:mercury" not in visible_ids(sky)


def test_body_that_neither_rises_nor_sets_tonight_has_null_rise_and_set_times():
    # Tromso in December 2026: a near-full Moon rides far north in Gemini, above declination
    # +20.35, so from latitude 69.65 N it circles the sky without setting.
    sky = compute_night_sky(69.65, 18.96, "Europe/Oslo", date(2026, 12, 22))

    moon = visible_body(sky, "moon:moon")
    assert moon.rises_at is None
    assert moon.sets_at is None


def category_1_highlight(sky):
    picks = [body for body in sky.highlights if body.category == "planet_moon"]
    assert len(picks) <= 1
    return picks[0] if picks else None


def test_gas_giant_outranks_a_higher_rocky_planet():
    # 2026-11-05 from New York: Mars climbs higher than Jupiter, and the thin crescent Moon is up.
    # Uranus is highest of all, but it is a faint ice giant, not a gas giant.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))
    mars, jupiter = (visible_body(sky, f"planet:{name}") for name in ("mars", "jupiter"))
    assert mars.peak_altitude_degrees > jupiter.peak_altitude_degrees

    assert category_1_highlight(sky).id == "planet:jupiter"


def test_moon_at_least_half_lit_outranks_a_higher_gas_giant():
    # 2026-01-08 from New York: a waning gibbous Moon, two days before last quarter on 10 January,
    # sits lower than Jupiter, which reaches opposition that week.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 1, 8))
    moon, jupiter = (visible_body(sky, body_id) for body_id in ("moon:moon", "planet:jupiter"))
    assert jupiter.peak_altitude_degrees > moon.peak_altitude_degrees

    assert category_1_highlight(sky).id == "moon:moon"


def test_moon_less_than_half_lit_ranks_below_every_planet():
    # 2026-05-21 from New York: a waxing crescent, two days before first quarter, stands
    # higher in the evening twilight than Jupiter, which is sinking into the west.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 5, 21))
    moon, jupiter = (visible_body(sky, body_id) for body_id in ("moon:moon", "planet:jupiter"))
    assert moon.peak_altitude_degrees > jupiter.peak_altitude_degrees

    assert category_1_highlight(sky).id == "planet:jupiter"


def test_peak_altitude_breaks_a_tie_between_equally_ranked_planets():
    # 2026-10-08 from New York, near new Moon: Saturn, a month past opposition, rides high in the
    # south while Jupiter only climbs out of the east before dawn. Both are gas giants.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 10, 8))
    saturn, jupiter = (visible_body(sky, f"planet:{name}") for name in ("saturn", "jupiter"))
    assert saturn.peak_altitude_degrees > jupiter.peak_altitude_degrees

    assert category_1_highlight(sky).id == "planet:saturn"
