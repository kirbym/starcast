import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.narrator import Narration, get_narrator

VALID_REQUEST = {
    "latitude": 40.7167,
    "longitude": -74.0,
    "timezone": "America/New_York",
    "date": "2026-06-21",
    "location_label": None,
}


class FakeNarrator:
    def __init__(self) -> None:
        self.received: list | None = None

    def narrate(self, highlights) -> Narration:
        self.received = list(highlights)
        return Narration(headline="A hush settles over tonight's sky.", cards=[])


@pytest.fixture
def narrator() -> Iterator[FakeNarrator]:
    fake = FakeNarrator()
    app.dependency_overrides[get_narrator] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client(narrator: FakeNarrator) -> TestClient:
    return TestClient(app)


def test_valid_request_returns_a_quiet_night_report(client: TestClient, narrator: FakeNarrator):
    response = client.post("/api/report", json=VALID_REQUEST)

    assert response.status_code == 200
    body = response.json()
    assert body["headline"] == "A hush settles over tonight's sky."
    assert body["highlights"] == []
    assert body["visible_objects"] == []
    assert narrator.received == []
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
