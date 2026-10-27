# Messier Catalog Source for StarCast

**Researched:** 2026-10-27
**Purpose:** Find a freely usable, machine-readable source of J2000 positions, magnitudes and types for the 110 Messier DSOs, which Skyfield has no built-in catalog for (see `astronomy-library-selection.md`, requirement 5).

---

## Recommendation

**Use OpenNGC** ([mattiaverga/OpenNGC](https://github.com/mattiaverga/OpenNGC)), filtered on its `M` column, and bundle the result as a static data file loaded at startup. Each entry becomes a Skyfield `Star(ra_hours=…, dec_degrees=…)`.

- **License:** CC-BY-SA-4.0 per the GitHub repo. Some VO mirrors list CC BY-SA 3.0; cite the repo. This is the same share-alike family as the HYG bright-star data already chosen in `bright-stars-catalog.md`, so it adds no new license obligation. Attribution is required.
- **Maintained:** last commit 2026-10-18.
- **Format:** semicolon-separated CSVs in `database_files/`. `NGC.csv` holds NGC/IC objects; `addendum.csv` holds objects outside NGC/IC.
- **Positions:** `RA` as `HH:MM:SS.SS` and `Dec` as `±DD:MM:SS.SS`, both J2000. This matches the bright-star catalog's epoch.

## Fields to keep

| OpenNGC column | StarCast use |
|---|---|
| `M` | Messier number → catalog key (`dso:m31`) |
| `Name` | NGC/IC designation, for narration context |
| `Common names` | Display name when present (e.g. "Andromeda Galaxy"), otherwise "M31" |
| `Type` | `G` galaxy, `GCl`/`OCl` cluster, `PN`/`EmN`/`SNR`/`HII` nebula, etc. Narration context |
| `RA`, `Dec` | Centroid for the Visibility check |
| `Const` | Constellation, for narration context |
| `V-Mag` (fall back to `B-Mag`) | `magnitude` in the API, and Category 3 brightness ranking |
| `MajAx`, `MinAx` | Apparent size, optional narration context |

## Coverage check (run against `master`, 2026-10-27)

Filtering both CSVs on `M` gives **110 rows covering M1–M110 with one exception**:

- **M40** (a double star, `**`) and **M45** (Pleiades, listed as `Mel022`) have no NGC/IC designation and live only in `addendum.csv`. Load both files.
- **M24** is `IC4715`, typed `*Ass` (Small Sagittarius Star Cloud). Keep it.
- **M73** is `NGC6994`, typed `Other` (an asterism). Keep it.
- **M102 is missing as a distinct object.** OpenNGC records an `M102` row typed `Dup` that points at M101 (NGC 5457), following Méchain's own retraction. Most modern lists, SEDS and Wikipedia's included, identify M102 with **NGC 5866 (the Spindle Galaxy)**, which is in `NGC.csv` with no `M` value. **Decision: drop the `Dup` row and map M102 → NGC 5866.** That keeps the catalog at 110 distinct objects and matches what users will find elsewhere.

### Missing magnitudes

Seven clusters have neither `V-Mag` nor `B-Mag` in OpenNGC. Category 3 ranks by brightness, so each needs a value. Use this override table, from [Wikipedia's List of Messier objects](https://en.wikipedia.org/wiki/List_of_Messier_objects), which follows SEDS:

| Messier | NGC | Type | Apparent magnitude |
|---|---|---|---|
| M22 | NGC 6656 | GCl | 5.1 |
| M35 | NGC 2168 | OCl | 5.3 |
| M62 | NGC 6266 | GCl | 6.5 |
| M69 | NGC 6637 | GCl | 7.6 |
| M70 | NGC 6681 | GCl | 7.9 |
| M71 | NGC 6838 | GCl | 8.2 |
| M107 | NGC 6171 | GCl | 7.9 |

## Build approach

Generate the bundled file once with a small script that does the following:
1. Download both CSVs from a pinned OpenNGC commit.
2. Filter on `M`.
3. Drop `Dup` rows.
4. Add NGC 5866 as M102.
5. Apply the magnitude overrides.
6. Write the trimmed fields.

Commit the script and its output, recording the commit SHA and the CC-BY-SA attribution in the output's header. There is no runtime network dependency, the same policy as the meteor shower calendar.

## Alternatives considered

- **HEASARC `messier` table** ([link](https://heasarc.gsfc.nasa.gov/W3Browse/all/messier.html)): authoritative, but has only 109 objects (omits M102 as spurious) and fewer fields. Useful for cross-checking positions.
- **SEDS Messier pages**: the de facto reference for M102 and magnitudes, but HTML only with no stated data license. Used only as the secondary source for the override table above.
- **SIMBAD via `SkyCoord.from_name()`**: a network call per object at runtime. Rejected for the same reason as live meteor feeds.

## Sources

- OpenNGC repository and `NGC_guide.txt` (field definitions): https://github.com/mattiaverga/OpenNGC
- HEASARC Messier catalog: https://heasarc.gsfc.nasa.gov/W3Browse/all/messier.html
- Wikipedia, List of Messier objects: https://en.wikipedia.org/wiki/List_of_Messier_objects
