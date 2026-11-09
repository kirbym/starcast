from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from skyfield.api import Loader, load, wgs84
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc

from app.astronomy import CATALOG, Catalog, compute_night_sky, data_dir
from app.comets import PINNED_ELEMENTS_ENV
from tests.conftest import PINNED_COMET_ELEMENTS

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


def highlight_in(sky, category: str):
    """The night's one Highlight in a Category, or None."""
    picks = [body for body in sky.highlights if body.category == category]
    assert len(picks) <= 1
    return picks[0] if picks else None


def category_1_highlight(sky):
    return highlight_in(sky, "planet_moon")


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


TROMSO = (69.65, 18.96)


def constellations(sky) -> list:
    return [body for body in sky.visible_objects if body.object_type == "constellation"]


def test_all_88_named_constellations_are_in_catalog():
    # On a polar night every Centroid north of the celestial equator circles the North Pole, and
    # every one south of it circles the South Pole, so the two nights together show all 88.
    north = compute_night_sky(90.0, 0.0, "Etc/UTC", date(2026, 12, 21))
    south = compute_night_sky(-90.0, 0.0, "Etc/UTC", date(2026, 6, 21))
    seen = constellations(north) + constellations(south)

    assert len({body.id for body in seen}) == 88
    for body in seen:
        assert body.id.startswith("constellation:")
        assert body.category == "constellation"
        assert body.magnitude is None
        assert body.name
    names = {body.name for body in seen}
    # IAU spellings, including the ones Astropy's boundary table gets wrong.
    iau_spellings = {"Boötes", "Chamaeleon", "Ophiuchus", "Piscis Austrinus"}
    assert {"Orion", "Ursa Major", "Crux", "Serpens"} | iau_spellings <= names


def test_circumpolar_constellation_is_visible_without_rising_or_setting():
    # Ursa Minor's Centroid sits near declination +77, so from Tromso (69.65 N) it never sets.
    sky = compute_night_sky(*TROMSO, "Europe/Oslo", date(2026, 12, 22))

    ursa_minor = visible_body(sky, "constellation:umi")
    assert ursa_minor.name == "Ursa Minor"
    assert ursa_minor.peak_altitude_degrees > 60
    assert ursa_minor.rises_at is None
    assert ursa_minor.sets_at is None


def test_constellation_that_never_rises_is_absent():
    # Crux and Octans have Centroids near declinations -60 and -85. From Tromso (69.65 N),
    # nothing south of -20.35 ever clears the horizon.
    sky = compute_night_sky(*TROMSO, "Europe/Oslo", date(2026, 12, 22))

    assert "constellation:cru" not in visible_ids(sky)
    assert "constellation:oct" not in visible_ids(sky)


def test_visible_constellation_carries_its_positional_fields():
    # Early November from New York: Orion rises in the late evening and stands high in the south
    # before dawn. Its Centroid (declination about +5) can climb to about 54 degrees here.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))

    orion = visible_body(sky, "constellation:ori")
    assert orion.name == "Orion"
    assert orion.object_type == "constellation"
    assert 40 < orion.peak_altitude_degrees < 55
    assert 0 <= orion.azimuth_at_peak_degrees < 360
    window = sky.viewing_window
    assert orion.rises_at is not None and window.starts_at < orion.rises_at < window.ends_at
    assert orion.sets_at is not None and orion.sets_at > window.ends_at


def category_2_highlight(sky):
    return highlight_in(sky, "constellation")


@pytest.mark.parametrize(
    ("location", "timezone", "night"),
    [
        pytest.param(NEW_YORK, "America/New_York", date(2026, 11, 5), id="new-york-autumn"),
        pytest.param(SYDNEY, "Australia/Sydney", date(2026, 6, 21), id="sydney-winter"),
        pytest.param(TROMSO, "Europe/Oslo", date(2026, 12, 22), id="tromso-polar-night"),
    ],
)
def test_category_2_is_the_visible_constellation_with_the_highest_peak_altitude(
    location, timezone, night
):
    sky = compute_night_sky(*location, timezone, night)

    highest = max(constellations(sky), key=lambda body: body.peak_altitude_degrees)
    assert category_2_highlight(sky) == highest


def bright_stars(sky) -> list:
    return [body for body in sky.visible_objects if body.object_type == "bright_star"]


def test_bright_stars_are_in_catalog_with_their_v_magnitudes():
    # As with the constellations, the two polar nights between them show the whole sky.
    north = compute_night_sky(90.0, 0.0, "Etc/UTC", date(2026, 12, 21))
    south = compute_night_sky(-90.0, 0.0, "Etc/UTC", date(2026, 6, 21))
    seen = {body.id: body for body in bright_stars(north) + bright_stars(south)}

    # Every IAU-named star at V <= 2.50: about 90 of them.
    assert 85 <= len(seen) <= 95
    for body in seen.values():
        assert body.id.startswith("bright_star:")
        assert body.category == "featured"
        assert body.name
        assert body.magnitude is not None and body.magnitude <= 2.50
    assert -1.5 < seen["bright_star:sirius"].magnitude < -1.4
    assert seen["bright_star:sirius"].name == "Sirius"
    assert seen["bright_star:rigil_kentaurus"].name == "Rigil Kentaurus"
    # Names the WGSN approved after HYG v4.1 was published.
    assert seen["bright_star:tiansi"].name == "Tiansi"
    assert seen["bright_star:uridim"].name == "Uridim"
    # ε Boo A is Izar; its fainter companion, Pulcherrima, shares its HIP number.
    assert seen["bright_star:izar"].name == "Izar"
    assert "bright_star:pulcherrima" not in seen


def test_visible_bright_star_carries_its_positional_fields():
    # Early November from New York: Sirius rises around midnight and is climbing toward the
    # meridian at dawn. At declination -16.7 it can reach at most 32.6 degrees here.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))

    sirius = visible_body(sky, "bright_star:sirius")
    assert sirius.object_type == "bright_star"
    assert sirius.category == "featured"
    assert 20 < sirius.peak_altitude_degrees < 33
    assert 90 < sirius.azimuth_at_peak_degrees < 270
    assert sirius.magnitude == pytest.approx(-1.44)
    window = sky.viewing_window
    assert sirius.rises_at is not None and window.starts_at < sirius.rises_at < window.ends_at
    assert sirius.sets_at is not None and sirius.sets_at > window.ends_at


def test_bright_star_that_never_rises_is_absent():
    # Canopus sits at declination -52.7, so from New York (40.7 N) it never clears the horizon.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))

    assert "bright_star:canopus" not in visible_ids(sky)


def category_3_highlight(sky):
    return highlight_in(sky, "featured")


def test_brightest_visible_star_is_the_category_3_highlight_even_when_lower_than_others():
    # 2026-11-05 from New York: Sirius, the brightest star in the sky, rises before dawn, while
    # Capella passes almost overhead.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))
    sirius, capella = (visible_body(sky, f"bright_star:{key}") for key in ("sirius", "capella"))
    assert capella.peak_altitude_degrees > sirius.peak_altitude_degrees

    assert category_3_highlight(sky).id == "bright_star:sirius"


@pytest.mark.parametrize(
    ("location", "timezone", "night"),
    [
        pytest.param(NEW_YORK, "America/New_York", date(2026, 6, 21), id="new-york-summer"),
        pytest.param(SYDNEY, "Australia/Sydney", date(2026, 6, 21), id="sydney-winter"),
        pytest.param(TROMSO, "Europe/Oslo", date(2026, 12, 22), id="tromso-polar-night"),
    ],
)
def test_category_3_is_the_brightest_visible_standing_body(location, timezone, night):
    sky = compute_night_sky(*location, timezone, night)

    featured = [body for body in sky.visible_objects if body.category == "featured"]
    brightest = min(featured, key=lambda body: body.magnitude)
    assert category_3_highlight(sky) == brightest


def only_featured(*ids: str) -> Catalog:
    """The real catalog, with Category 3 narrowed to the given standing bodies, in that order."""
    featured = {body.id: body for body in CATALOG.featured}
    return replace(CATALOG, featured=tuple(featured[body_id] for body_id in ids))


@pytest.mark.parametrize(
    "ids",
    [("bright_star:deneb", "bright_star:mimosa"), ("bright_star:mimosa", "bright_star:deneb")],
)
def test_peak_altitude_breaks_a_magnitude_tie_in_category_3(ids):
    # Deneb and Mimosa share V = 1.25. No real night leaves two equally bright stars as the
    # brightest Visible ones: Polaris, Capella or Canopus is always Visible to outshine a tied pair.
    # So this narrows Category 3 to the pair. From Sydney in June, Mimosa (in the Southern Cross)
    # stands high in the south while Deneb only skims the northern horizon before dawn.
    sky = compute_night_sky(*SYDNEY, "Australia/Sydney", date(2026, 6, 21), only_featured(*ids))
    deneb, mimosa = (visible_body(sky, f"bright_star:{key}") for key in ("deneb", "mimosa"))
    assert deneb.magnitude == mimosa.magnitude
    assert mimosa.peak_altitude_degrees > deneb.peak_altitude_degrees

    assert category_3_highlight(sky).id == "bright_star:mimosa"


def test_category_3_is_omitted_when_no_candidate_is_visible():
    # Mimosa (declination -59.7) never rises from Tromso, though planets and constellations do.
    sky = compute_night_sky(
        *TROMSO, "Europe/Oslo", date(2026, 12, 22), only_featured("bright_star:mimosa")
    )

    assert bright_stars(sky) == []
    assert [body.category for body in sky.highlights] == ["planet_moon", "constellation"]


def dsos(sky) -> list:
    return [body for body in sky.visible_objects if body.object_type == "dso"]


def test_all_110_messier_dsos_are_in_catalog_with_magnitudes():
    # As with the constellations, the two polar nights between them show the whole sky.
    north = compute_night_sky(90.0, 0.0, "Etc/UTC", date(2026, 12, 21))
    south = compute_night_sky(-90.0, 0.0, "Etc/UTC", date(2026, 6, 21))
    seen = {body.id: body for body in dsos(north) + dsos(south)}

    assert set(seen) == {f"dso:m{number}" for number in range(1, 111)}
    for body in seen.values():
        assert body.category == "featured"
        assert body.name
        assert body.magnitude is not None
    assert seen["dso:m31"].name == "Andromeda Galaxy"
    assert seen["dso:m45"].name == "Pleiades"
    assert seen["dso:m40"].context["type"] == "double star"
    # A DSO with no common name goes by its Messier number.
    assert seen["dso:m92"].name == "M92"
    # OpenNGC follows Messier's own retraction of M102; StarCast takes the Spindle Galaxy.
    assert seen["dso:m102"].name == "Spindle Galaxy"
    assert seen["dso:m102"].context["designation"] == "NGC 5866"
    # OpenNGC has no magnitude for M22; the override table supplies SEDS's.
    assert seen["dso:m22"].magnitude == pytest.approx(5.1)


def test_visible_dso_carries_its_positional_fields_and_catalog_context():
    # Early November from New York, the Andromeda Galaxy passes almost overhead in the evening.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))

    andromeda = visible_body(sky, "dso:m31")
    assert andromeda.object_type == "dso"
    assert andromeda.category == "featured"
    assert andromeda.name == "Andromeda Galaxy"
    assert andromeda.peak_altitude_degrees > 80
    assert andromeda.magnitude == pytest.approx(3.44)
    assert andromeda.context == {
        "messier": "M31",
        "designation": "NGC 224",
        "type": "galaxy",
        "constellation": "Andromeda",
        "size_arcminutes": pytest.approx(177.83),
    }


def test_dso_that_never_rises_is_absent():
    # Ptolemy's Cluster (M7) sits at declination -34.8, so from Tromso (69.65 N) it never rises.
    sky = compute_night_sky(*TROMSO, "Europe/Oslo", date(2026, 12, 22))

    assert "dso:m7" not in visible_ids(sky)


@pytest.mark.parametrize(
    "ids", [("dso:m45", "bright_star:mirfak"), ("bright_star:mirfak", "dso:m45")]
)
def test_bright_dso_outranks_a_fainter_bright_star_in_category_3(ids):
    # 2026-11-05 from New York: Mirfak (V 1.79) passes higher than the Pleiades (V 1.20), but the
    # Category 3 ranking is the same for every standing body, and the brighter one wins.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5), only_featured(*ids))
    pleiades, mirfak = (visible_body(sky, body_id) for body_id in ("dso:m45", "bright_star:mirfak"))
    assert mirfak.peak_altitude_degrees > pleiades.peak_altitude_degrees
    assert pleiades.magnitude < mirfak.magnitude

    assert category_3_highlight(sky).id == "dso:m45"


def test_highlights_from_all_three_categories_appear_together_in_category_order():
    sky = compute_night_sky(*NEW_YORK, "America/New_York", date(2026, 11, 5))

    assert [body.category for body in sky.highlights] == [
        "planet_moon",
        "constellation",
        "featured",
    ]


NAMED_COMET_KEYS = {
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
# 2020-07-20 from New York: Comet NEOWISE, two weeks past perihelion and nearing its closest
# approach to Earth, hangs low in the north-west after dusk below the Big Dipper.
NEOWISE_NIGHT = date(2020, 7, 20)


def comets(sky) -> list:
    return [body for body in sky.visible_objects if body.object_type == "comet"]


def test_all_11_named_comets_are_in_catalog_as_featured_bodies():
    named = [body for body in CATALOG.featured if body.object_type == "comet"]

    assert {body.id for body in named} == {f"comet:{key}" for key in NAMED_COMET_KEYS}
    assert {body.category for body in named} == {"featured"}
    names = {body.name for body in named}
    assert {"Halley's Comet", "Comet Hale-Bopp", "Comet NEOWISE"} <= names


def test_bright_comet_is_visible_with_its_computed_magnitude():
    sky = compute_night_sky(*NEW_YORK, "America/New_York", NEOWISE_NIGHT)

    neowise = visible_body(sky, "comet:neowise")
    assert neowise.category == "featured"
    assert neowise.name == "Comet NEOWISE"
    # Observers put it near magnitude 3 that week, an easy naked-eye sight.
    assert 2.0 < neowise.magnitude < 4.5
    # Low in the north-west at dusk, before it sets for the night.
    assert 5 < neowise.peak_altitude_degrees < 25
    assert 270 < neowise.azimuth_at_peak_degrees < 360
    assert neowise.sets_at is not None
    assert neowise.context["designation"] == "C/2020 F3"
    assert neowise.context["perihelion_date"] == "2020-07-05"
    # Every other Named Comet is far from the Sun and far too faint.
    assert [body.id for body in comets(sky)] == ["comet:neowise"]


def neowise_altitude_at_dusk(night: date) -> float:
    """NEOWISE's altitude from New York as the night's Viewing Window opens, computed from the
    pinned elements independently of the engine."""
    with PINNED_COMET_ELEMENTS.open("rb") as file:
        rows = mpc.load_comets_dataframe(file).set_index("designation", drop=False)
    timescale = load.timescale(builtin=True)
    ephemeris = Loader(str(data_dir()), verbose=False)("de440s.bsp")
    neowise = ephemeris["sun"] + mpc.comet_orbit(rows.loc["C/2020 F3 (NEOWISE)"], timescale, GM_SUN)
    dusk = compute_night_sky(*NEW_YORK, "America/New_York", night).viewing_window.starts_at
    observer = ephemeris["earth"] + wgs84.latlon(*NEW_YORK)
    moment = timescale.from_datetime(dusk)
    return observer.at(moment).observe(neowise).apparent().altaz()[0].degrees


def test_comet_fainter_than_magnitude_6_is_not_visible_even_above_the_horizon():
    # 2020-08-20: NEOWISE still stands above the western horizon at dusk, but six weeks past
    # perihelion it has faded to around magnitude 8, beyond the naked eye.
    night = date(2020, 8, 20)
    assert neowise_altitude_at_dusk(night) > 5

    sky = compute_night_sky(*NEW_YORK, "America/New_York", night, only_featured("comet:neowise"))

    assert comets(sky) == []
    assert category_3_highlight(sky) is None


@pytest.mark.parametrize("ids", [("comet:neowise", "dso:m13"), ("dso:m13", "comet:neowise")])
def test_bright_comet_outranks_a_fainter_dso_in_category_3(ids):
    # On NEOWISE's night the Hercules Cluster (V 5.8) passes almost overhead while the comet
    # stays low, but brightness ranks first.
    sky = compute_night_sky(*NEW_YORK, "America/New_York", NEOWISE_NIGHT, only_featured(*ids))
    neowise, hercules = (visible_body(sky, body_id) for body_id in ("comet:neowise", "dso:m13"))
    assert hercules.peak_altitude_degrees > neowise.peak_altitude_degrees

    assert category_3_highlight(sky).id == "comet:neowise"


def test_missing_comet_elements_omit_the_comets_and_the_night_still_computes(monkeypatch, tmp_path):
    monkeypatch.setenv(PINNED_ELEMENTS_ENV, str(tmp_path / "missing.txt"))

    sky = compute_night_sky(*NEW_YORK, "America/New_York", NEOWISE_NIGHT)

    assert comets(sky) == []
    assert [body.category for body in sky.highlights] == [
        "planet_moon",
        "constellation",
        "featured",
    ]
