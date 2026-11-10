import logging
import os
from collections.abc import Awaitable, Callable
from time import sleep
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.astronomy import compute_night_sky
from app.narrator import Narration, NarrationError, Narrator, get_narrator
from app.schemas import Highlight, ReportRequest, ReportResponse, SkyObject

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


@app.exception_handler(RequestValidationError)
def invalid_location(_request: Request, exc: RequestValidationError) -> JSONResponse:
    problems = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'][1:]) or 'body'}: {error['msg']}"
        for error in exc.errors()
    )
    return _error(400, "invalid_location", problems)


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
) -> ReportResponse:
    sky = compute_night_sky(
        report_request.latitude,
        report_request.longitude,
        report_request.timezone,
        report_request.date,
    )
    highlights = [SkyObject.model_validate(body) for body in sky.highlights]
    narrated_highlights = [
        {**highlight.model_dump(mode="json"), "context": body.context}
        for highlight, body in zip(highlights, sky.highlights, strict=True)
    ]
    try:
        headline, cards = _narrate(narrator, narrated_highlights, highlights)
    except NarrationError as first_failure:
        logger.warning("Narration failed, retrying once: %s", first_failure)
        sleep(NARRATION_RETRY_DELAY_SECONDS)
        headline, cards = _narrate(narrator, narrated_highlights, highlights)
    return ReportResponse(
        headline=headline,
        viewing_window=sky.viewing_window,
        highlights=cards,
        visible_objects=[SkyObject.model_validate(body) for body in sky.visible_objects],
    )


def _narrate(
    narrator: Narrator, narrated_highlights: list[dict], highlights: list[SkyObject]
) -> tuple[str, list[Highlight]]:
    """One narration attempt: the Headline, and the Highlights with their cards attached."""
    narration = narrator.narrate(narrated_highlights)
    return narration.headline, _merge_cards(highlights, narration)


def _merge_cards(highlights: list[SkyObject], narration: Narration) -> list[Highlight]:
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
        Highlight(
            **highlight.model_dump(),
            mini_headline=cards[highlight.id].mini_headline,
            paragraph=cards[highlight.id].paragraph,
        )
        for highlight in highlights
    ]
