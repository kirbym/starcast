import os
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.astronomy import compute_night_sky
from app.narrator import Narrator, get_narrator
from app.schemas import ReportRequest, ReportResponse

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
    narration = narrator.narrate(sky.highlights)
    return ReportResponse(
        headline=narration.headline,
        viewing_window=sky.viewing_window,
        highlights=sky.highlights,
        visible_objects=sky.visible_objects,
    )
