import os

import pytest

from app.narrator import BANNED_PHRASES, SYSTEM_PROMPT, ClaudeNarrator, Narration


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
