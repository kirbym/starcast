import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.narrator import Narration, NarrationCard, get_narrator

VALID_REQUEST = {
    "latitude": 40.7167,
    "longitude": -74.0,
    "timezone": "America/New_York",
    "date": "2026-06-21",
    "location_label": None,
}
# Tromso at midsummer has no astronomical darkness, so nothing is Visible.
QUIET_NIGHT_REQUEST = {
    "latitude": 69.65,
    "longitude": 18.96,
    "timezone": "Europe/Oslo",
    "date": "2026-06-21",
    "location_label": None,
}
# New York on 2026-11-05: Jupiter is the Category 1 Highlight, Andromeda, passing almost
# overhead, the Category 2 Highlight, and Sirius, rising before dawn, the Category 3 Highlight,
# among other Visible bodies.
JUPITER_NIGHT_REQUEST = {**VALID_REQUEST, "date": "2026-11-05"}


class FakeNarrator:
    """Writes one card per Highlight it is given, echoing each id, unless told what to return."""

    def __init__(self) -> None:
        self.received: list | None = None
        self.cards: list[NarrationCard] | None = None

    def narrate(self, highlights) -> Narration:
        self.received = list(highlights)
        cards = self.cards
        if cards is None:
            cards = [
                NarrationCard(
                    id=highlight["id"],
                    mini_headline=f"{highlight['name']} takes the stage",
                    paragraph=f"A story about {highlight['name']}.",
                )
                for highlight in self.received
            ]
        return Narration(headline="A hush settles over tonight's sky.", cards=cards)


@pytest.fixture
def narrator() -> Iterator[FakeNarrator]:
    fake = FakeNarrator()
    app.dependency_overrides[get_narrator] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client(narrator: FakeNarrator) -> TestClient:
    return TestClient(app)


def test_quiet_night_returns_a_headline_and_no_bodies(client: TestClient, narrator: FakeNarrator):
    response = client.post("/api/report", json=QUIET_NIGHT_REQUEST)

    assert response.status_code == 200
    body = response.json()
    assert body["headline"] == "A hush settles over tonight's sky."
    assert body["highlights"] == []
    assert body["visible_objects"] == []
    assert narrator.received == []


def test_viewing_window_is_returned_in_utc(client: TestClient):
    response = client.post("/api/report", json=VALID_REQUEST)

    assert response.status_code == 200
    body = response.json()
    # USNO publishes 02:37 and 07:19 UTC for this night.
    assert re.fullmatch(r"2026-06-22T02:3[678]:\d\dZ", body["viewing_window"]["starts_at"])
    assert re.fullmatch(r"2026-06-22T07:(18|19|20):\d\dZ", body["viewing_window"]["ends_at"])


@pytest.mark.parametrize(
    "bad_fields",
    [
        pytest.param({"latitude": 90.1}, id="latitude-too-high"),
        pytest.param({"latitude": -90.1}, id="latitude-too-low"),
        pytest.param({"latitude": "north"}, id="latitude-not-a-number"),
        pytest.param({"latitude": None}, id="latitude-null"),
        pytest.param({"longitude": 180.1}, id="longitude-too-high"),
        pytest.param({"longitude": -180.1}, id="longitude-too-low"),
        pytest.param({"timezone": "Mars/Olympus_Mons"}, id="timezone-unknown"),
        pytest.param({"timezone": "America"}, id="timezone-is-a-directory"),
        pytest.param({"timezone": "../secrets"}, id="timezone-path-traversal"),
        pytest.param({"date": "2026-13-01"}, id="date-impossible-month"),
        pytest.param({"date": "2026-02-30"}, id="date-impossible-day"),
        pytest.param({"date": "21/06/2026"}, id="date-wrong-format"),
        pytest.param({"date": "20260621"}, id="date-compact-iso"),
        pytest.param({"date": "2026-06-21T00:00:00"}, id="date-with-time"),
        pytest.param({"date": 1781000000}, id="date-timestamp"),
        pytest.param({"date": "1700-01-01"}, id="date-before-ephemeris"),
        pytest.param({"date": "2300-01-01"}, id="date-after-ephemeris"),
    ],
)
def test_invalid_location_returns_400_error_envelope(
    client: TestClient, narrator: FakeNarrator, bad_fields: dict
):
    response = client.post("/api/report", json={**VALID_REQUEST, **bad_fields})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["statusCode"] == 400
    assert error["type"] == "invalid_location"
    assert error["message"]
    assert narrator.received is None


def test_missing_field_returns_400_error_envelope(client: TestClient):
    request = {key: value for key, value in VALID_REQUEST.items() if key != "timezone"}

    response = client.post("/api/report", json=request)

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_location"


def test_malformed_json_returns_400_error_envelope(client: TestClient):
    response = client.post(
        "/api/report", content="{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_location"


def test_browser_on_the_frontend_origin_may_post_a_report(client: TestClient):
    response = client.options(
        "/api/report",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


POSITIONAL_FIELDS = {
    "id",
    "category",
    "object_type",
    "name",
    "peak_altitude_degrees",
    "azimuth_at_peak_degrees",
    "rises_at",
    "sets_at",
    "magnitude",
    "event",
}


def test_highlight_carries_its_narrated_card_and_positional_fields(client: TestClient):
    response = client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    assert response.status_code == 200
    [highlight, _constellation, _star] = response.json()["highlights"]
    assert set(highlight) == POSITIONAL_FIELDS | {"mini_headline", "paragraph"}
    assert highlight["id"] == "planet:jupiter"
    assert highlight["category"] == "planet_moon"
    assert highlight["object_type"] == "planet"
    assert highlight["name"] == "Jupiter"
    assert highlight["mini_headline"] == "Jupiter takes the stage"
    assert highlight["paragraph"] == "A story about Jupiter."
    assert highlight["event"] is None
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", highlight["rises_at"])


def test_one_highlight_card_per_category_is_narrated_in_category_order(client: TestClient):
    response = client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    assert response.status_code == 200
    [planet, constellation, star] = response.json()["highlights"]
    assert planet["id"] == "planet:jupiter"
    assert constellation["id"] == "constellation:and"
    assert constellation["category"] == "constellation"
    assert constellation["object_type"] == "constellation"
    assert constellation["name"] == "Andromeda"
    assert constellation["magnitude"] is None
    assert constellation["mini_headline"] == "Andromeda takes the stage"
    assert constellation["paragraph"] == "A story about Andromeda."
    assert set(star) == POSITIONAL_FIELDS | {"mini_headline", "paragraph"}
    assert star["id"] == "bright_star:sirius"
    assert star["category"] == "featured"
    assert star["object_type"] == "bright_star"
    assert star["name"] == "Sirius"
    assert star["magnitude"] == pytest.approx(-1.44)
    assert star["mini_headline"] == "Sirius takes the stage"
    assert star["paragraph"] == "A story about Sirius."


def test_highlight_cards_are_merged_by_id_whatever_order_the_narrator_returns_them_in(
    client: TestClient, narrator: FakeNarrator
):
    narrator.cards = [
        NarrationCard(id="bright_star:sirius", mini_headline="The Dog Star", paragraph="S."),
        NarrationCard(id="constellation:and", mini_headline="The chained princess", paragraph="A."),
        NarrationCard(id="planet:jupiter", mini_headline="The king rises", paragraph="J."),
    ]

    response = client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    assert response.status_code == 200
    mini_headlines = [
        (highlight["id"], highlight["mini_headline"]) for highlight in response.json()["highlights"]
    ]
    assert mini_headlines == [
        ("planet:jupiter", "The king rises"),
        ("constellation:and", "The chained princess"),
        ("bright_star:sirius", "The Dog Star"),
    ]


def test_narrator_receives_raw_fields_of_each_highlight(client: TestClient, narrator: FakeNarrator):
    client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    assert [received["id"] for received in narrator.received] == [
        "planet:jupiter",
        "constellation:and",
        "bright_star:sirius",
    ]
    for received in narrator.received:
        assert set(received) == POSITIONAL_FIELDS | {"context"}
        assert isinstance(received["rises_at"], str)


def test_narrator_receives_a_bright_stars_catalog_facts_as_context(
    client: TestClient, narrator: FakeNarrator
):
    client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    planet, constellation, star = narrator.received
    assert planet["context"] is None
    assert constellation["context"] is None
    context = star["context"]
    assert context["bayer_designation"] == "α CMa"
    assert context["constellation"] == "Canis Major"
    assert context["spectral_type"].startswith("A0")
    assert context["color_index_b_v"] == pytest.approx(0.0, abs=0.05)
    assert 8 < context["distance_light_years"] < 9


def test_every_visible_body_is_listed_with_highlights_included(client: TestClient):
    response = client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    visible = response.json()["visible_objects"]
    ids = {body["id"] for body in visible}
    assert {"planet:jupiter", "planet:mars", "planet:saturn", "moon:moon"} <= ids
    assert {"constellation:and", "constellation:ori", "constellation:uma"} <= ids
    assert {"bright_star:sirius", "bright_star:capella", "bright_star:polaris"} <= ids
    assert {"dso:m31", "dso:m45", "dso:m42"} <= ids
    assert "planet:venus" not in ids
    assert "constellation:cru" not in ids
    assert "bright_star:canopus" not in ids
    categories = {
        "planet": "planet_moon",
        "moon": "planet_moon",
        "constellation": "constellation",
        "bright_star": "featured",
        "comet": "featured",
        "dso": "featured",
    }
    for body in visible:
        assert set(body) == POSITIONAL_FIELDS
        assert body["category"] == categories[body["object_type"]]
    sirius = next(body for body in visible if body["id"] == "bright_star:sirius")
    assert sirius["magnitude"] == pytest.approx(-1.44)
    assert sirius["peak_altitude_degrees"] > 0


def test_bright_named_comet_is_listed_with_its_computed_magnitude(client: TestClient):
    # 2020-07-20 from New York: Comet NEOWISE hangs low in the north-west after dusk.
    response = client.post("/api/report", json={**VALID_REQUEST, "date": "2020-07-20"})

    assert response.status_code == 200
    comets = [body for body in response.json()["visible_objects"] if body["object_type"] == "comet"]
    assert [comet["id"] for comet in comets] == ["comet:neowise"]
    assert comets[0]["category"] == "featured"
    assert comets[0]["name"] == "Comet NEOWISE"
    assert comets[0]["magnitude"] < 6.0


# New York on 2020-12-21: the great conjunction of Jupiter and Saturn, low in the south-west.
GREAT_CONJUNCTION_REQUEST = {**VALID_REQUEST, "date": "2020-12-21"}


def test_conjunction_highlight_carries_its_event_with_a_stable_id(client: TestClient):
    first = client.post("/api/report", json=GREAT_CONJUNCTION_REQUEST)
    again = client.post("/api/report", json=GREAT_CONJUNCTION_REQUEST)

    assert first.status_code == 200
    event_highlight = first.json()["highlights"][-1]
    assert set(event_highlight) == POSITIONAL_FIELDS | {"mini_headline", "paragraph"}
    assert event_highlight["id"] == "significant_event:conjunction_jupiter_saturn"
    assert again.json()["highlights"][-1]["id"] == event_highlight["id"]
    assert event_highlight["category"] == "featured"
    assert event_highlight["object_type"] == "significant_event"
    assert event_highlight["name"] == "Jupiter and Saturn in conjunction"
    assert event_highlight["mini_headline"] == "Jupiter and Saturn in conjunction takes the stage"
    event = event_highlight["event"]
    assert set(event) == {"event_type", "peak_time", "related_object_names"}
    assert event["event_type"] == "conjunction"
    assert re.fullmatch(r"2020-12-21T\d\d:\d\d:\d\dZ", event["peak_time"])
    assert event["related_object_names"] == ["Jupiter", "Saturn"]


def test_narrator_receives_the_conjunction_event_and_its_separation(
    client: TestClient, narrator: FakeNarrator
):
    client.post("/api/report", json=GREAT_CONJUNCTION_REQUEST)

    received = narrator.received[-1]
    assert received["id"] == "significant_event:conjunction_jupiter_saturn"
    assert received["event"]["event_type"] == "conjunction"
    assert received["event"]["related_object_names"] == ["Jupiter", "Saturn"]
    assert isinstance(received["event"]["peak_time"], str)
    assert received["context"]["separation_degrees"] == pytest.approx(0.10, abs=0.01)


def test_conjunction_is_a_highlight_but_not_a_visible_object(client: TestClient):
    response = client.post("/api/report", json=GREAT_CONJUNCTION_REQUEST)

    visible = response.json()["visible_objects"]
    assert {"planet:jupiter", "planet:saturn"} <= {body["id"] for body in visible}
    assert all(body["event"] is None for body in visible)


# New York on 2020-10-13: Mars reaches opposition that evening.
MARS_OPPOSITION_REQUEST = {**VALID_REQUEST, "date": "2020-10-13"}


def test_opposition_highlight_carries_its_event(client: TestClient):
    response = client.post("/api/report", json=MARS_OPPOSITION_REQUEST)

    assert response.status_code == 200
    event_highlight = response.json()["highlights"][-1]
    assert set(event_highlight) == POSITIONAL_FIELDS | {"mini_headline", "paragraph"}
    assert event_highlight["id"] == "significant_event:opposition_mars"
    assert event_highlight["category"] == "featured"
    assert event_highlight["object_type"] == "significant_event"
    assert event_highlight["name"] == "Mars at opposition"
    event = event_highlight["event"]
    assert event["event_type"] == "opposition"
    assert re.fullmatch(r"2020-10-1[34]T\d\d:\d\d:\d\dZ", event["peak_time"])
    assert event["related_object_names"] == ["Mars"]


def test_narrator_receives_the_opposition_event_and_its_exact_moment(
    client: TestClient, narrator: FakeNarrator
):
    client.post("/api/report", json=MARS_OPPOSITION_REQUEST)

    received = narrator.received[-1]
    assert received["id"] == "significant_event:opposition_mars"
    assert received["event"]["event_type"] == "opposition"
    assert received["context"]["opposition_time"].startswith("2020-10-13T23:2")


# New York on 2026-08-12: the Perseids peak.
PERSEIDS_REQUEST = {**VALID_REQUEST, "date": "2026-08-12"}


def test_meteor_shower_highlight_carries_its_event(client: TestClient):
    response = client.post("/api/report", json=PERSEIDS_REQUEST)

    assert response.status_code == 200
    event_highlight = response.json()["highlights"][-1]
    assert set(event_highlight) == POSITIONAL_FIELDS | {"mini_headline", "paragraph"}
    assert event_highlight["id"] == "significant_event:meteor_shower_per"
    assert event_highlight["category"] == "featured"
    assert event_highlight["object_type"] == "significant_event"
    assert event_highlight["name"] == "Perseids meteor shower"
    assert event_highlight["magnitude"] is None
    event = event_highlight["event"]
    assert event["event_type"] == "meteor_shower"
    assert re.fullmatch(r"2026-08-1[23]T\d\d:\d\d:\d\dZ", event["peak_time"])
    assert event["related_object_names"] == ["Perseus"]


def test_narrator_receives_the_meteor_shower_and_its_catalog_facts(
    client: TestClient, narrator: FakeNarrator
):
    client.post("/api/report", json=PERSEIDS_REQUEST)

    received = narrator.received[-1]
    assert received["id"] == "significant_event:meteor_shower_per"
    assert received["event"]["event_type"] == "meteor_shower"
    assert received["context"]["zhr"] == 100
    assert received["context"]["peak_date"] == "2026-08-12"
    assert received["context"]["parent_body"] == "109P/Swift-Tuttle"


@pytest.mark.parametrize(
    "cards",
    [
        pytest.param([], id="card-missing"),
        pytest.param(
            [NarrationCard(id="planet:mars", mini_headline="Mars!", paragraph="Red.")],
            id="card-for-a-body-that-is-not-a-highlight",
        ),
        pytest.param(
            [
                NarrationCard(id="planet:jupiter", mini_headline="Jupiter!", paragraph="Big."),
                NarrationCard(id="planet:mars", mini_headline="Mars!", paragraph="Red."),
            ],
            id="extra-unknown-card",
        ),
    ],
)
def test_narration_whose_card_ids_do_not_match_the_highlights_is_a_narration_failure(
    client: TestClient, narrator: FakeNarrator, cards: list[NarrationCard]
):
    narrator.cards = cards

    response = client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["statusCode"] == 502
    assert error["type"] == "narration_failed"
    assert "Mars!" not in response.text
