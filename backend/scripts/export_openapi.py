"""Export the API's OpenAPI document, the source of the frontend's generated types.

Run from backend/:  uv run scripts/export_openapi.py

Then, from frontend/:  npm run gen:api

The backend's dataclasses and request/response models are the one declaration of the shapes on
the wire. This writes them to frontend/src/api/openapi.json, which `npm run gen:api` turns into
frontend/src/api/schema.gen.ts. A backend test fails when openapi.json is stale, and a frontend
test fails when schema.gen.ts is.
"""

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
OPENAPI_FILE = BACKEND.parent / "frontend" / "src" / "api" / "openapi.json"

sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402


def main() -> None:
    OPENAPI_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_FILE.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OPENAPI_FILE}")


if __name__ == "__main__":
    main()
