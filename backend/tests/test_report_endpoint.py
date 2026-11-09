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
# New York on 2026-11-05: Jupiter is the Category 1 Highlight and Andromeda, passing almost
# overhead, the Category 2 Highlight, among other Visible bodies.
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
    [highlight, _constellation] = response.json()["highlights"]
    assert set(highlight) == POSITIONAL_FIELDS | {"mini_headline", "paragraph"}
    assert highlight["id"] == "planet:jupiter"
    assert highlight["category"] == "planet_moon"
    assert highlight["object_type"] == "planet"
    assert highlight["name"] == "Jupiter"
    assert highlight["mini_headline"] == "Jupiter takes the stage"
    assert highlight["paragraph"] == "A story about Jupiter."
    assert highlight["event"] is None
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", highlight["rises_at"])


def test_constellation_highlight_is_narrated_alongside_the_planet(client: TestClient):
    response = client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    assert response.status_code == 200
    [planet, constellation] = response.json()["highlights"]
    assert planet["id"] == "planet:jupiter"
    assert constellation["id"] == "constellation:and"
    assert constellation["category"] == "constellation"
    assert constellation["object_type"] == "constellation"
    assert constellation["name"] == "Andromeda"
    assert constellation["magnitude"] is None
    assert constellation["mini_headline"] == "Andromeda takes the stage"
    assert constellation["paragraph"] == "A story about Andromeda."


def test_highlight_cards_are_merged_by_id_whatever_order_the_narrator_returns_them_in(
    client: TestClient, narrator: FakeNarrator
):
    narrator.cards = [
        NarrationCard(id="constellation:and", mini_headline="The chained princess", paragraph="A."),
        NarrationCard(id="planet:jupiter", mini_headline="The king rises", paragraph="J."),
    ]

    response = client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    assert response.status_code == 200
    mini_headlines = {
        highlight["id"]: highlight["mini_headline"] for highlight in response.json()["highlights"]
    }
    assert mini_headlines == {
        "planet:jupiter": "The king rises",
        "constellation:and": "The chained princess",
    }


def test_narrator_receives_raw_fields_of_each_highlight(client: TestClient, narrator: FakeNarrator):
    client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    assert [received["id"] for received in narrator.received] == [
        "planet:jupiter",
        "constellation:and",
    ]
    for received in narrator.received:
        assert set(received) == POSITIONAL_FIELDS
        assert isinstance(received["rises_at"], str)


def test_every_visible_body_is_listed_with_highlights_included(client: TestClient):
    response = client.post("/api/report", json=JUPITER_NIGHT_REQUEST)

    visible = response.json()["visible_objects"]
    ids = {body["id"] for body in visible}
    assert {"planet:jupiter", "planet:mars", "planet:saturn", "moon:moon"} <= ids
    assert {"constellation:and", "constellation:ori", "constellation:uma"} <= ids
    assert "planet:venus" not in ids
    assert "constellation:cru" not in ids
    for body in visible:
        assert set(body) == POSITIONAL_FIELDS
        expected = "constellation" if body["object_type"] == "constellation" else "planet_moon"
        assert body["category"] == expected


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
