from pathlib import Path

import pytest

from app.comets import PINNED_ELEMENTS_ENV

# The 11 Named Comets' rows from the MPC's AllCometEls.txt, downloaded 2026-11-09 from
# https://www.minorplanetcenter.net/iau/MPCORB/AllCometEls.txt. Pinned so no test fetches them.
PINNED_COMET_ELEMENTS = Path(__file__).parent / "fixtures" / "comet_elements.txt"


@pytest.fixture(autouse=True)
def pinned_comet_elements(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(PINNED_ELEMENTS_ENV, str(PINNED_COMET_ELEMENTS))
    return PINNED_COMET_ELEMENTS
