import json
from pathlib import Path

from app.main import app

OPENAPI_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"


def test_committed_openapi_document_matches_the_api():
    # The frontend's types are generated from this file. If this fails, run
    # `uv run scripts/export_openapi.py` from backend/, then `npm run gen:api` from frontend/.
    committed = json.loads(OPENAPI_FILE.read_text(encoding="utf-8"))

    assert committed == app.openapi()


def test_visible_body_category_and_object_type_reach_the_document():
    schemas = app.openapi()["components"]["schemas"]

    visible_body = schemas["VisibleBody"]["properties"]
    assert visible_body["category"]["enum"] == [1, 2, 3]
    assert "named_comet" in visible_body["object_type"]["enum"]
    assert {"mini_headline", "paragraph"} <= set(schemas["HighlightCard"]["properties"])
