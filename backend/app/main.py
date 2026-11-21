import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import fields
from datetime import datetime
from time import sleep
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.astronomy import compute_night_sky
from app.narrator import Narration, NarrationError, Narrator, get_narrator
from app.place import get_now, place_local_date, place_timezone
from app.schemas import HighlightCard, ReportRequest, ReportResponse
from app.sky import Highlight, VisibleBody

# A failed narration gets one more try, after this short wait.
NARRATION_RETRY_DELAY_SECONDS = 1.0

logger = logging.getLogger(__name__)

app = FastAPI(title="StarCast API")


def _error(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"statusCode": status_code, "type": error_type, "message": message}},
    )


# Registered before CORS so that CORS wraps it: an exception handler for Exception would run
# outside every middleware, and the browser could not read a 500 without CORS headers.
@app.middleware("http")
async def internal_error(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unexpected error handling %s %s", request.method, request.url.path)
        return _error(500, "internal_error", "Something went wrong on our side.")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("CORS_ORIGIN", "http://localhost:5173")],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


# The fields the user chose. A request rejected only for the rest (the date or the label) is
# `invalid_request`: the place itself is fine, and the frontend keeps it.
_LOCATION_FIELDS = {"latitude", "longitude"}


@app.exception_handler(RequestValidationError)
def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    problems = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'][1:]) or 'body'}: {error['msg']}"
        for error in errors
    )
    location_at_fault = any(
        len(error["loc"]) > 1 and error["loc"][1] in _LOCATION_FIELDS for error in errors
    )
    return _error(400, "invalid_location" if location_at_fault else "invalid_request", problems)


@app.exception_handler(NarrationError)
def narration_failed(_request: Request, exc: NarrationError) -> JSONResponse:
    return _error(502, "narration_failed", str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/report")
def create_report(
    report_request: ReportRequest,
    narrator: Annotated[Narrator, Depends(get_narrator)],
    now: Annotated[datetime, Depends(get_now)],
) -> ReportResponse:
    # The night is the place's own: its timezone, and its date, not the requester's.
    timezone = place_timezone(report_request.latitude, report_request.longitude)
    local_date = report_request.date or place_local_date(timezone, now)
    sky = compute_night_sky(report_request.latitude, report_request.longitude, timezone, local_date)
    try:
        headline, cards = _narrate(narrator, sky.highlights)
    except NarrationError as first_failure:
        logger.warning("Narration failed, retrying once: %s", first_failure)
        sleep(NARRATION_RETRY_DELAY_SECONDS)
        headline, cards = _narrate(narrator, sky.highlights)
    return ReportResponse(
        timezone=timezone,
        date=local_date,
        headline=headline,
        viewing_window=sky.viewing_window,
        highlights=cards,
    )


def _narrate(narrator: Narrator, highlights: list[Highlight]) -> tuple[str, list[HighlightCard]]:
    """One narration attempt: the Headline, and a Highlight Card for each Highlight."""
    narration = narrator.narrate(highlights)
    return narration.headline, _merge_cards([highlight.body for highlight in highlights], narration)


def _merge_cards(highlights: list[VisibleBody], narration: Narration) -> list[HighlightCard]:
    """Attach each card to the Highlight with its id, so prose never lands on the wrong body.

    Every Highlight must get exactly one card, and every card must belong to a Highlight.
    """
    cards = {card.id: card for card in narration.cards}
    highlight_ids = [highlight.id for highlight in highlights]
    if len(narration.cards) != len(highlights) or set(cards) != set(highlight_ids):
        raise NarrationError(
            f"card ids {[card.id for card in narration.cards]} do not match Highlights "
            f"{highlight_ids}"
        )
    return [
        HighlightCard(
            **{field.name: getattr(highlight, field.name) for field in fields(highlight)},
            mini_headline=cards[highlight.id].mini_headline,
            paragraph=cards[highlight.id].paragraph,
        )
        for highlight in highlights
    ]
