import pytest

from app import place


class NothingFound:
    def timezone_at(self, *, lat: float, lng: float) -> None:
        return None


@pytest.mark.parametrize(
    ("longitude", "timezone"),
    [(0.0, "Etc/GMT"), (-140.0, "Etc/GMT+9"), (139.7, "Etc/GMT-9"), (-180.0, "Etc/GMT+12")],
)
def test_a_point_with_no_timezone_found_gets_its_longitudes_nautical_zone(
    monkeypatch: pytest.MonkeyPatch, longitude: float, timezone: str
):
    monkeypatch.setattr(place, "_finder", NothingFound)

    assert place.place_timezone(0.0, longitude) == timezone
