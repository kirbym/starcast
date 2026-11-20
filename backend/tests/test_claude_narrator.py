import json
import os
from datetime import UTC, datetime
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.narrator import (
    BANNED_PHRASES,
    HIGHLIGHT_FIELDS,
    SERVER_SIDE_FALLBACK_BETA,
    SYSTEM_PROMPT,
    ClaudeNarrator,
    Narration,
    NarrationError,
)
from app.sky import Highlight, SignificantEvent, VisibleBody


class FakeClient:
    """Stands in for the Anthropic client: each create() returns or raises what it is given."""

    def __init__(self, outcome) -> None:
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._outcome = outcome
        self.request: dict | None = None

    def _create(self, **kwargs):
        self.request = kwargs
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _reply(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)]
    )


_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def test_parses_a_schema_valid_reply():
    narrator = ClaudeNarrator(client=FakeClient(_reply('{"headline": "Hush.", "cards": []}')))

    assert narrator.narrate([]) == Narration(headline="Hush.", cards=[])


@pytest.mark.parametrize(
    "outcome",
    [
        pytest.param(anthropic.APIConnectionError(request=_REQUEST), id="unreachable"),
        pytest.param(
            anthropic.InternalServerError(
                "overloaded", response=httpx.Response(529, request=_REQUEST), body=None
            ),
            id="overloaded",
        ),
        pytest.param(_reply('{"headline": "Hush."}'), id="missing-cards"),
        pytest.param(_reply("not json"), id="not-json"),
        pytest.param(_reply('{"headline": "Hu', stop_reason="max_tokens"), id="cut-off"),
        pytest.param(SimpleNamespace(stop_reason="end_turn", content=[]), id="no-text"),
    ],
)
def test_a_failed_call_or_unusable_reply_is_a_narration_error(outcome):
    narrator = ClaudeNarrator(client=FakeClient(outcome))

    with pytest.raises(NarrationError):
        narrator.narrate([])


def test_asks_for_thinking_off_with_a_server_side_fallback():
    # "between_tools" is how this Sonnet turns thinking off ("disabled" is a 400), and it is
    # a 400 above effort "high". See docs/adr/0001-narrator-server-side-fallback.md.
    client = FakeClient(_reply('{"headline": "Hush.", "cards": []}'))

    ClaudeNarrator(client).narrate([])

    assert client.request["thinking"] == {"type": "between_tools"}
    assert client.request["output_config"].get("effort", "high") in {"low", "medium", "high"}
    assert client.request["fallbacks"] == "default"
    assert SERVER_SIDE_FALLBACK_BETA in client.request["betas"]


def test_every_banned_phrase_reaches_the_system_prompt():
    assert BANNED_PHRASES
    for phrase in BANNED_PHRASES:
        assert f'"{phrase}"' in SYSTEM_PROMPT


JUPITER = VisibleBody(
    id="planet:jupiter",
    category=1,
    object_type="planet",
    name="Jupiter",
    peak_altitude_degrees=54.8,
    azimuth_at_peak_degrees=132.2,
    rises_at=datetime(2026, 11, 6, 4, 51, 49, tzinfo=UTC),
    sets_at=datetime(2026, 11, 6, 18, 30, 12, tzinfo=UTC),
    magnitude=-2.03,
)


def test_sends_each_highlights_raw_fields_and_context_as_json():
    client = FakeClient(_reply('{"headline": "Hush.", "cards": []}'))
    conjunction = VisibleBody(
        id="significant_event:conjunction_jupiter_saturn",
        category=3,
        object_type="significant_event",
        name="Jupiter and Saturn in conjunction",
        peak_altitude_degrees=12.0,
        azimuth_at_peak_degrees=230.0,
        rises_at=None,
        sets_at=None,
        magnitude=None,
        event=SignificantEvent(
            event_type="conjunction",
            peak_time=datetime(2020, 12, 21, 22, 0, tzinfo=UTC),
            related_object_names=("Jupiter", "Saturn"),
        ),
    )

    ClaudeNarrator(client).narrate(
        [Highlight(JUPITER), Highlight(conjunction, {"separation_degrees": 0.1})]
    )

    sent = json.loads(client.request["messages"][0]["content"])
    assert [tuple(highlight) for highlight in sent] == [HIGHLIGHT_FIELDS, HIGHLIGHT_FIELDS]
    jupiter, event = sent
    assert jupiter["rises_at"] == "2026-11-06T04:51:49Z"
    assert jupiter["context"] is None
    assert event["event"] == {
        "event_type": "conjunction",
        "peak_time": "2020-12-21T22:00:00Z",
        "related_object_names": ["Jupiter", "Saturn"],
    }
    assert event["context"] == {"separation_degrees": 0.1}


def test_system_prompt_names_every_raw_field():
    for field in HIGHLIGHT_FIELDS:
        assert field in SYSTEM_PROMPT


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="calls the real Claude API; needs a key"
)
def test_real_claude_narrator_returns_schema_valid_quiet_night():
    narration = ClaudeNarrator().narrate([])

    assert isinstance(narration, Narration)
    assert narration.headline.strip()
    assert narration.cards == []


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="calls the real Claude API; needs a key"
)
def test_real_claude_narrator_echoes_the_highlight_id_on_its_card():
    narration = ClaudeNarrator().narrate([Highlight(JUPITER)])

    assert [card.id for card in narration.cards] == ["planet:jupiter"]
    assert narration.cards[0].mini_headline.strip()
    assert narration.cards[0].paragraph.strip()
