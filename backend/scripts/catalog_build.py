"""What the catalog build scripts share: where they put things, fetching their pinned sources, and
writing a generated catalog file.

Imported by the build_*.py scripts beside it (a script's own directory is on its import path), so it
uses only the standard library.
"""

import csv
import urllib.request
from collections.abc import Sequence
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DATA = BACKEND / "app" / "data"
# Git-ignored: the pinned source files, downloaded once.
DOWNLOADS = BACKEND / ".cache" / "catalog-sources"
CONSTELLATIONS = DATA / "constellations.csv"


def download(url: str, name: str) -> Path:
    """Fetch a pinned source file once, keeping it in the cache as `name`."""
    path = DOWNLOADS / name
    if not path.exists():
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, path)
    return path


def read_catalog(path: Path) -> list[dict[str, str]]:
    """The rows of a generated catalog file, past its `#` comment lines."""
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(line for line in file if not line.startswith("#")))


def constellation_names() -> dict[str, str]:
    """Each Named Constellation's full name, by its IAU abbreviation (`CMa` -> `Canis Major`)."""
    return {row["abbreviation"]: row["name"] for row in read_catalog(CONSTELLATIONS)}


def write_catalog(path: Path, comments: Sequence[str], rows: Sequence[dict], what: str) -> None:
    """Write a generated catalog: each comment as a `# ` line (its provenance and licence), then
    the rows as CSV, with the header taken from the first row's keys."""
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        file.writelines(f"# {comment}\n" for comment in comments)
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} {what} to {path}")
