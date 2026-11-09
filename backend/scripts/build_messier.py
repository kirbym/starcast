# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build the DSO catalog: the 110 Messier objects, M1 to M110.

Run from backend/:  uv run scripts/build_messier.py

Positions (J2000), types, magnitudes and sizes come from OpenNGC (CC BY-SA 4.0), pinned to one
commit. The Messier objects are the rows of its NGC and addendum files with a value in the `M`
column. OpenNGC follows Messier's retraction of M102 with a `Dup` row pointing at M101, so that row
is dropped and M102 is NGC 5866, the Spindle Galaxy, as in most modern lists. Seven clusters have
no V or B magnitude in OpenNGC and take SEDS's value instead. See docs/research/messier-catalog.md.
"""

import csv
import re
import sys
import urllib.request
from pathlib import Path

OPENNGC_COMMIT = "be3cd6c5498806a2fbb2f7e0452ef802dbb02be0"
OPENNGC_URL = (
    "https://raw.githubusercontent.com/mattiaverga/OpenNGC/"
    f"{OPENNGC_COMMIT}/database_files/{{name}}.csv"
)
MESSIER_COUNT = 110

BACKEND = Path(__file__).resolve().parent.parent
DOWNLOADS = BACKEND / ".cache" / "catalog-sources"
CONSTELLATIONS = BACKEND / "app" / "data" / "constellations.csv"
OUTPUT = BACKEND / "app" / "data" / "messier.csv"

# OpenNGC lists M102 as a duplicate of M101; StarCast takes NGC 5866 for it.
M102_SOURCE = "NGC5866"

# Apparent magnitudes for the clusters OpenNGC gives neither a V nor a B magnitude, from
# Wikipedia's List of Messier objects, which follows SEDS.
MAGNITUDE_OVERRIDES = {22: 5.1, 35: 5.3, 62: 6.5, 69: 7.6, 70: 7.9, 71: 8.2, 107: 7.9}

# The name to show where OpenNGC's first common name is not the familiar English one, or where
# it has none for an object that is widely known by one.
COMMON_NAME_OVERRIDES = {
    11: "Wild Duck Cluster",  # OpenNGC lists "Amas de l'Ecu de Sobieski" first.
    17: "Omega Nebula",  # OpenNGC lists "Checkmark Nebula" first.
    24: "Small Sagittarius Star Cloud",  # OpenNGC abbreviates it "Small Sgr Star Cloud".
    42: "Orion Nebula",  # OpenNGC lists "Great Orion Nebula" first.
    44: "Beehive Cluster",  # OpenNGC has "Beehive".
    76: "Little Dumbbell Nebula",  # OpenNGC lists "Barbell Nebula" first.
    102: "Spindle Galaxy",  # OpenNGC gives NGC 5866 no common name.
}

# OpenNGC object types, in words for the Narrator. See NGC_guide.txt in the OpenNGC repository.
TYPES = {
    "G": "galaxy",
    "GCl": "globular cluster",
    "OCl": "open cluster",
    "Cl+N": "star cluster with nebula",
    "Neb": "nebula",
    "HII": "emission nebula",
    "RfN": "reflection nebula",
    "PN": "planetary nebula",
    "SNR": "supernova remnant",
    "*Ass": "star cloud",
    "**": "double star",
    "Other": "asterism",
}

# OpenNGC splits Serpens into its two halves.
SERPENS_HALVES = {"Se1": "Ser", "Se2": "Ser"}


def download(name: str) -> Path:
    """Fetch an OpenNGC file once, keeping it in the git-ignored cache."""
    path = DOWNLOADS / f"openngc-{name}-{OPENNGC_COMMIT[:7]}.csv"
    if not path.exists():
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        url = OPENNGC_URL.format(name=name)
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, path)
    return path


def read_openngc(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file, delimiter=";"))


def constellation_names() -> dict[str, str]:
    with CONSTELLATIONS.open(encoding="utf-8", newline="") as file:
        rows = csv.DictReader(line for line in file if not line.startswith("#"))
        return {row["abbreviation"]: row["name"] for row in rows}


def sexagesimal(value: str) -> float:
    """`05:34:31.97` -> 5.5755..., `-00:49:23.9` -> -0.8233...: hours or degrees as a decimal."""
    sign = -1 if value.startswith("-") else 1
    whole, minutes, seconds = (float(part) for part in value.lstrip("+-").split(":"))
    return sign * (whole + minutes / 60 + seconds / 3600)


def designation(name: str) -> str:
    """`NGC0224` -> `NGC 224`, `IC4715` -> `IC 4715`, `Mel022` -> `Mel 22`; empty for `M040`."""
    match = re.fullmatch(r"(NGC|IC|Mel)0*(\d+)", name)
    return f"{match[1]} {match[2]}" if match else ""


def magnitude(number: int, row: dict[str, str]) -> tuple[str, str]:
    """The object's magnitude and its source: OpenNGC's V, its B, or the override table."""
    if number in MAGNITUDE_OVERRIDES:
        if row["V-Mag"] or row["B-Mag"]:
            sys.exit(f"M{number} has a magnitude in OpenNGC now; drop its override")
        return f"{MAGNITUDE_OVERRIDES[number]:.2f}", "SEDS"
    for band in ("V", "B"):
        if row[f"{band}-Mag"]:
            return f"{float(row[f'{band}-Mag']):.2f}", band
    sys.exit(f"M{number} has no magnitude")


def common_name(number: int, row: dict[str, str]) -> str:
    if number in COMMON_NAME_OVERRIDES:
        return COMMON_NAME_OVERRIDES[number]
    return row["Common names"].split(",")[0].strip()


def size(value: str) -> str:
    return f"{float(value):g}" if value else ""


def main() -> None:
    rows = read_openngc(download("NGC")) + read_openngc(download("addendum"))
    constellations = constellation_names()

    messier: dict[int, dict[str, str]] = {}
    for row in rows:
        if row["Name"] == M102_SOURCE:
            if row["M"]:
                sys.exit(f"{M102_SOURCE} has a Messier number in OpenNGC now; drop the mapping")
            messier[102] = row
        elif row["M"] and row["Type"] != "Dup":
            number = int(row["M"])
            if number in messier:
                sys.exit(f"M{number} appears twice")
            messier[number] = row
    if sorted(messier) != list(range(1, MESSIER_COUNT + 1)):
        sys.exit(f"expected M1 to M{MESSIER_COUNT}, got {len(messier)} objects")

    output = []
    for number, row in sorted(messier.items()):
        if row["Type"] not in TYPES:
            sys.exit(f"M{number} has an unknown OpenNGC type {row['Type']!r}")
        abbreviation = SERPENS_HALVES.get(row["Const"], row["Const"])
        value, source = magnitude(number, row)
        output.append(
            {
                "key": f"m{number}",
                "messier": f"M{number}",
                "designation": designation(row["Name"]),
                "common_name": common_name(number, row),
                "type": TYPES[row["Type"]],
                "ra_hours": f"{sexagesimal(row['RA']):.6f}",
                "dec_degrees": f"{sexagesimal(row['Dec']):.5f}",
                "constellation": constellations[abbreviation],
                "magnitude": value,
                "magnitude_source": source,
                "major_axis_arcmin": size(row["MajAx"]),
                "minor_axis_arcmin": size(row["MinAx"]),
            }
        )

    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        file.write(
            "# The DSOs: the 110 Messier objects, generated by scripts/build_messier.py.\n"
            "# Positions (J2000), types, constellations, magnitudes and sizes (arcminutes): "
            f"OpenNGC (commit {OPENNGC_COMMIT}),\n"
            "# by Mattia Verga, https://github.com/mattiaverga/OpenNGC, licensed CC BY-SA 4.0.\n"
            "# This file is derived from OpenNGC and is shared under the same licence, "
            "https://creativecommons.org/licenses/by-sa/4.0/.\n"
            "# M102 is NGC 5866 (the Spindle Galaxy). magnitude_source is V or B from OpenNGC, "
            "or SEDS (via Wikipedia's\n"
            "# List of Messier objects) for the clusters OpenNGC gives no magnitude.\n"
        )
        writer = csv.DictWriter(file, fieldnames=list(output[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    print(f"wrote {len(output)} DSOs to {OUTPUT}")


if __name__ == "__main__":
    main()
