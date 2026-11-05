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
