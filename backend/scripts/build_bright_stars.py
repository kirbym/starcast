# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build the Bright Star catalog: every IAU-named star at V <= 2.50.

Run from backend/:  uv run scripts/build_bright_stars.py

Positions, magnitudes, spectral types, B-V colours and distances come from the HYG Database v4.1
(CC BY-SA 4.0), pinned to one commit. Proper names are the IAU Working Group on Star Names (WGSN)
approvals, matched on Hipparcos number, because HYG lags some of them. They are read from
cyschneck/iau-star-names (MIT), a machine-readable mirror of the WGSN list kept current with new
approvals and also pinned to one commit. The WGSN's own IAU-CSN text file stops at 2022. A star
with no IAU-approved name is left out. See docs/research/bright-stars-catalog.md.
"""

import csv
import math
import sys
import unicodedata
import urllib.request
from pathlib import Path

HYG_COMMIT = "e4fd9c95381c6b5f34e465259cb4d2e1a7ff2e09"
HYG_URL = (
    "https://raw.githubusercontent.com/astronexus/HYG-Database/"
    f"{HYG_COMMIT}/hyg/CURRENT/hygdata_v41.csv"
)
IAU_NAMES_COMMIT = "8bb9c7414e045675ab89490287f5785cdafc8372"
IAU_NAMES_URL = (
    "https://raw.githubusercontent.com/cyschneck/iau-star-names/"
    f"{IAU_NAMES_COMMIT}/iau_proper_stars.csv"
)
MAGNITUDE_LIMIT = 2.50
PARSECS_TO_LIGHT_YEARS = 3.26156
# HYG's placeholder distance for a star with no usable parallax.
UNKNOWN_DISTANCE_PARSECS = 100_000

BACKEND = Path(__file__).resolve().parent.parent
DOWNLOADS = BACKEND / ".cache" / "catalog-sources"
CONSTELLATIONS = BACKEND / "app" / "data" / "constellations.csv"
OUTPUT = BACKEND / "app" / "data" / "bright_stars.csv"

GREEK = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε", "Zet": "ζ", "Eta": "η",
    "The": "θ", "Iot": "ι", "Kap": "κ", "Lam": "λ", "Mu": "μ", "Nu": "ν", "Xi": "ξ",
    "Omi": "ο", "Pi": "π", "Rho": "ρ", "Sig": "σ", "Tau": "τ", "Ups": "υ", "Phi": "φ",
    "Chi": "χ", "Psi": "ψ", "Ome": "ω",
}  # fmt: skip


def download(url: str, name: str) -> Path:
    """Fetch a source file once, keeping it in the git-ignored cache."""
    path = DOWNLOADS / name
    if not path.exists():
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, path)
    return path


def iau_names_by_hip(path: Path) -> dict[int, str]:
    """Hipparcos number -> IAU-approved proper name, for every named star with a HIP number."""
    with path.open(encoding="utf-8", newline="") as file:
        return {
            int(row["HIP"]): row["Proper Names"].strip()
            for row in csv.DictReader(file)
            if row["HIP"].strip().isdigit()
        }


def constellation_names() -> dict[str, str]:
    with CONSTELLATIONS.open(encoding="utf-8", newline="") as file:
        rows = csv.DictReader(line for line in file if not line.startswith("#"))
        return {row["abbreviation"]: row["name"] for row in rows}


def catalog_key(name: str) -> str:
    """`Rigil Kentaurus` -> `rigil_kentaurus`, dropping any diacritics."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return ascii_name.lower().replace(" ", "_").replace("-", "_")


def three_significant_figures(value: float) -> str:
    """`8.6114` -> `8.61`, `2615.3` -> `2620`: parallax distances carry no more precision."""
    return f"{round(value, 2 - math.floor(math.log10(value))):g}"


def bayer_designation(row: dict[str, str]) -> str:
    """HYG's `Alp`/`Kap-1` and Flamsteed fields as a conventional designation, like `α CMa`."""
    if row["bayer"]:
        letter, _, index = row["bayer"].partition("-")
        return f"{GREEK[letter]}{index} {row['con']}"
    if row["flam"]:
        return f"{row['flam']} {row['con']}"
    return ""


def main() -> None:
    hyg = download(HYG_URL, f"hygdata_v41-{HYG_COMMIT[:7]}.csv")
    iau = iau_names_by_hip(download(IAU_NAMES_URL, f"iau_proper_stars-{IAU_NAMES_COMMIT[:7]}.csv"))
    constellations = constellation_names()

    rows = []
    unnamed = []
    with hyg.open(encoding="utf-8", newline="") as file:
        for star in csv.DictReader(file):
            # The Sun, and companions HYG lists apart from their primary, have no HIP number.
            if not star["hip"] or float(star["mag"]) > MAGNITUDE_LIMIT:
                continue
            hip = int(star["hip"])
            if hip not in iau:
                unnamed.append(f"{bayer_designation(star)} (HIP {hip})")
                continue
            name = iau[hip]
            parsecs = float(star["dist"])
            rows.append(
                {
                    "key": catalog_key(name),
                    "name": name,
                    "bayer": bayer_designation(star),
                    "constellation": constellations[star["con"]],
                    "ra_hours": f"{float(star['ra']):.6f}",
                    "dec_degrees": f"{float(star['dec']):.5f}",
                    "magnitude": f"{float(star['mag']):.2f}",
                    "spectral_type": star["spect"],
                    "color_index": f"{float(star['ci']):.3f}" if star["ci"] else "",
                    "distance_light_years": (
                        three_significant_figures(parsecs * PARSECS_TO_LIGHT_YEARS)
                        if parsecs < UNKNOWN_DISTANCE_PARSECS
                        else ""
                    ),
                    "hip": hip,
                }
            )
    rows.sort(key=lambda row: (float(row["magnitude"]), row["key"]))
    if len({row["key"] for row in rows}) != len(rows):
        sys.exit("two stars share a catalog key")

    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        file.write(
            "# The Bright Stars: every IAU-named star at V <= 2.50, generated by "
            "scripts/build_bright_stars.py.\n"
            "# Positions (J2000), V magnitudes, spectral types, B-V colours and distances: "
            f"HYG Database v4.1 (commit {HYG_COMMIT[:7]}),\n"
            "# by David Nash, https://github.com/astronexus/HYG-Database, licensed CC BY-SA 4.0.\n"
            "# This file is derived from HYG and is shared under the same licence, "
            "https://creativecommons.org/licenses/by-sa/4.0/.\n"
            "# Proper names: IAU Working Group on Star Names, "
            "https://www.iau.org/public/themes/naming_stars/,\n"
            "# as mirrored by https://github.com/cyschneck/iau-star-names "
            f"(commit {IAU_NAMES_COMMIT[:7]}).\n"
        )
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} Bright Stars to {OUTPUT}")
    for star in unnamed:
        print(f"  left out, no IAU name: {star}")


if __name__ == "__main__":
    main()
