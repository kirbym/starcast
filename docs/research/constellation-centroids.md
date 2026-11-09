# Constellation Centroid Source for StarCast

**Researched:** 2026-11-09
**Purpose:** Give each of the 88 Named Constellations a J2000 Centroid for the Visibility check (#22). Astropy's `get_constellation()` maps a position to a constellation, but publishes no centroids, and no other library StarCast uses does either.

---

## Recommendation

**Derive the Centroids from the official IAU boundaries with a committed, reproducible script, and bundle the result as a static data file loaded at startup.**

- **Boundary source:** the IAU constellation boundaries (Delporte, 1930), as digitised by Roman (1987, CDS catalogue VI/42) and shipped inside Astropy as the data behind `get_constellation()`. This is the same boundary set the spec already names for constellation lookup (#2).
- **License:** Astropy is BSD-3-Clause and ships the boundary table as package data. The table is CDS catalogue VI/42; CDS asks users to cite the original authors, which this note and the data file header do. The boundaries are an IAU definition, i.e. factual coordinates, and the derived Centroids are StarCast's own computed output.
- **Script:** `backend/scripts/build_constellation_centroids.py`. It is a PEP 723 script that pins `astropy==8.0.2` and `numpy==2.5.4`. Run it from `backend/` with `uv run scripts/build_constellation_centroids.py`. Astropy is needed only to regenerate the file, so it is **not** a runtime dependency.
- **Output:** `backend/app/data/constellations.csv`, with the columns `key, abbreviation, name, ra_hours, dec_degrees, area_square_degrees`. Positions are J2000 (ICRS), the same epoch as the bright-star and Messier data.

## How the Centroids are produced

1. Cover the celestial sphere with a Fibonacci lattice of 2,000,000 points. The lattice is equal-area, so each point stands for the same patch of sky, about 0.02 sq deg.
2. Label each point with its constellation using `get_constellation()`. Astropy precesses each ICRS point to B1875, the boundaries' native epoch, before looking it up.
3. For each constellation, sum its points' unit vectors and normalise the sum. That vector is the area-weighted Centroid of the constellation on the sphere, converted back to RA/Dec.

Averaging unit vectors, not RA and Dec numbers, keeps the result correct across RA 0h/24h (Andromeda, Pisces, Pegasus) and around the poles (Octans, Ursa Minor, Cepheus).

**Precision.** Even Crux, the smallest constellation, has about 3,300 sample points, so sampling error is far below 0.1°. That is small next to the 5-minute sampling of the Viewing Window and to the size of any constellation.

## Validation (run 2026-11-09)

- Exactly 88 constellations come out. The script exits non-zero otherwise.
- The sampled areas match the official IAU areas for every constellation spot-checked: Hydra 1303, Virgo 1295, Ursa Major 1280, Octans 291, Ursa Minor 256, Crux 68.
- 87 of 88 Centroids fall inside their own constellation's boundary. The exception is **Serpens**: it is split into Serpens Caput and Serpens Cauda on either side of Ophiuchus, so its Centroid falls between them, in Hercules (RA 16.50h, Dec +4.8). The IAU counts Serpens as one constellation, and StarCast keeps one Centroid for it. For a horizon check this is harmless, because both halves sit at similar declinations.
- No Centroid lies within 2° of the celestial equator. The nearest is Aquila at +2.1°.

## Conventions

- **Catalog key:** the IAU three-letter abbreviation, lowercased. Ids look like `constellation:uma` and `constellation:ori`. The abbreviation is the IAU's own stable identifier, and the CSV keeps its canonical capitalisation (`UMa`) next to the key.
- **Name:** Astropy's name, corrected to the IAU spelling where it differs: `Bootes` → `Boötes`, plus three Astropy misspellings, `Chamaleon` → `Chamaeleon`, `Ophiucus` → `Ophiuchus` and `Pisces Austrinus` → `Piscis Austrinus`. Astropy's table also pads `Crux ` with a trailing space, which the script strips.
- **Magnitude:** none. A Named Constellation has `magnitude: null` in the API.

## Alternatives considered

- **Wikipedia constellation infoboxes** (RA/Dec per constellation): CC BY-SA, but the infobox values have no single stated method. Some are label positions and some are boundary midpoints, so they are not reproducible.
- **Stellarium `constellations_boundaries.dat`** (GPL): the same Delporte boundaries, but using it means writing a spherical-polygon centroid routine and taking on a GPL data dependency, with no gain over Astropy's copy.
- **d3-celestial `constellations.json`** (BSD): it has hand-placed label positions, not centroids. Those are fine for drawing a map, but they are not a definition StarCast can cite.
- **Boundary-vertex average** (mean of polygon corners from VizieR VI/49): simpler, but biased toward whichever edges have more vertices. An area-weighted Centroid is a faithful single point for the whole constellation.

## Sources

- Delporte, E. (1930), *Délimitation scientifique des constellations*, IAU.
- Roman, N. G. (1987), "Identification of a Constellation from a Position", PASP 99, 695. CDS catalogue VI/42: https://cdsarc.cds.unistra.fr/viz-bin/cat/VI/42
- Astropy `get_constellation()`: https://docs.astropy.org/en/stable/api/astropy.coordinates.get_constellation.html
- IAU constellation list and areas: https://www.iau.org/public/themes/constellations/
