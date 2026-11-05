"""The Narrator: turns the night's Highlights into the prose of a Cosmic Report."""

import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any, Protocol

from anthropic import Anthropic
from pydantic import BaseModel

# Structured output enforces the JSON shape because the current Sonnet rejects forced tool_choice
# with a 400. It rejects sampling parameters too, so sampling stays at the model's default.
MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 1024
SERVER_SIDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"

BANNED_PHRASES = (
    "twinkling",
    "gaze upon the heavens",
    "gaze skyward",
    "celestial dance",
    "cosmic ballet",
    "shining bright",
)

SYSTEM_PROMPT = f"""\
You write StarCast's Cosmic Report: a short, personal report on what is really in one observer's
sky tonight, told by a friend who knows astronomy and still finds it wonderful.

The user message is a JSON array of 0 to 3 Highlights, the bodies or events chosen for tonight.
Each has raw fields: id, category, object_type, name, peak_altitude_degrees,
azimuth_at_peak_degrees, rises_at, sets_at, magnitude and event.

Write one headline and one card per Highlight.

Voice: conversational, with the occasional poetic flourish, always grounded in real astronomy.
For constellations and named stars, a light touch of mythology or cultural lore adds wonder;
draw it from your own knowledge.

Length: the headline is one punchy sentence about the most striking thing in tonight's sky. Each
card has a short mini_headline and a paragraph of 2 to 4 sentences.

Numbers: never put exact figures in your prose, such as degrees of altitude or magnitude values.
Turn them into qualitative language, like "climbs high overhead" or "hangs low near the horizon".

Events: when a Highlight's event field is not null, centre its paragraph on the event itself,
meaning what is happening between the bodies or the peak of the shower, rather than describing
the object as if the event were not occurring.

Banned phrases, which must never appear: {", ".join(f'"{phrase}"' for phrase in BANNED_PHRASES)}.

Each card's id must be copied exactly from the Highlight it narrates. Only write about the
Highlights you are given.

If the array is empty, it is a quiet night: write a headline suited to a night with nothing to
feature, return an empty cards array, and do not invent a body or event to fill the gap."""

NARRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "mini_headline": {"type": "string"},
                    "paragraph": {"type": "string"},
                },
                "required": ["id", "mini_headline", "paragraph"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["headline", "cards"],
    "additionalProperties": False,
}


class NarrationCard(BaseModel):
    id: str
    mini_headline: str
    paragraph: str


class Narration(BaseModel):
    headline: str
    cards: list[NarrationCard]


class NarrationError(Exception):
    """Claude finished without producing a usable narration."""


class Narrator(Protocol):
    def narrate(self, highlights: Sequence[Mapping[str, Any]]) -> Narration: ...


class ClaudeNarrator:
    def __init__(self) -> None:
        # Retrying is the endpoint's job, and the spec allows it only once.
        self._client = Anthropic(max_retries=0)

    def narrate(self, highlights: Sequence[Mapping[str, Any]]) -> Narration:
        response = self._client.beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(list(highlights))}],
            output_config={"format": {"type": "json_schema", "schema": NARRATION_SCHEMA}},
            # Sonnet thinks by default. Off saves tokens, and thinking counts against MAX_TOKENS.
            thinking={"type": "between_tools"},
            betas=[SERVER_SIDE_FALLBACK_BETA],
            fallbacks="default",
        )
        if response.stop_reason != "end_turn":
            raise NarrationError(f"Claude stopped early: {response.stop_reason}")
        text = next(block.text for block in response.content if block.type == "text")
        return Narration.model_validate_json(text)


@lru_cache(maxsize=1)
def get_narrator() -> Narrator:
    return ClaudeNarrator()
