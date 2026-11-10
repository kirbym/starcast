import os
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.narrator import (
    BANNED_PHRASES,
    SYSTEM_PROMPT,
    ClaudeNarrator,
    Narration,
    NarrationError,
)


class FakeClient:
    """Stands in for the Anthropic client: each create() returns or raises what it is given."""

    def __init__(self, outcome) -> None:
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._outcome = outcome

    def _create(self, **_kwargs):
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


def test_every_banned_phrase_reaches_the_system_prompt():
    assert BANNED_PHRASES
    for phrase in BANNED_PHRASES:
        assert f'"{phrase}"' in SYSTEM_PROMPT


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
    jupiter = {
        "id": "planet:jupiter",
        "category": "planet_moon",
        "object_type": "planet",
        "name": "Jupiter",
        "peak_altitude_degrees": 54.8,
        "azimuth_at_peak_degrees": 132.2,
        "rises_at": "2026-11-06T04:51:49Z",
        "sets_at": "2026-11-06T18:30:12Z",
        "magnitude": -2.03,
        "event": None,
    }

    narration = ClaudeNarrator().narrate([jupiter])

    assert [card.id for card in narration.cards] == ["planet:jupiter"]
    assert narration.cards[0].mini_headline.strip()
    assert narration.cards[0].paragraph.strip()
