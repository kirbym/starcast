import os
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.astronomy import compute_night_sky
from app.narrator import Narration, NarrationError, Narrator, get_narrator
from app.schemas import Highlight, ReportRequest, ReportResponse, SkyObject

app = FastAPI(title="StarCast API")
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
    return JSONResponse(
        status_code=400,
        content={"error": {"statusCode": 400, "type": "invalid_location", "message": problems}},
    )


@app.exception_handler(NarrationError)
def narration_failed(_request: Request, exc: NarrationError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"error": {"statusCode": 502, "type": "narration_failed", "message": str(exc)}},
    )


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
    narration = narrator.narrate(
        [
            {**highlight.model_dump(mode="json"), "context": body.context}
            for highlight, body in zip(highlights, sky.highlights, strict=True)
        ]
    )
    return ReportResponse(
        headline=narration.headline,
        viewing_window=sky.viewing_window,
        highlights=_merge_cards(highlights, narration),
        visible_objects=[SkyObject.model_validate(body) for body in sky.visible_objects],
    )


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
