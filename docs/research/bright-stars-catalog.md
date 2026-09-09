# Bright Stars Catalog — Research Findings

**Research date:** 2026-09-09  
**Purpose:** Determine the optimal named-star catalog for StarCast's "Bright Stars" highlight category.

---

## 1. How Many Stars Is Practical?

### IAU WGSN total count

As of mid-2026, the IAU Working Group on Star Names (WGSN) has approved **approximately 605 proper names** for stars.
Source: [star-facts.com — Complete List of IAU-Approved Star Names](https://www.star-facts.com/star-names/)

These 605 names span a magnitude range of roughly **−1.46 (Sirius) to ~21 (Flying Saucer)**, meaning most approved names belong to faint stars that have no interest for naked-eye observation.

### Magnitude cutoffs and practical counts

Using the full list of brightest stars from Wikipedia's [List of brightest stars](https://en.wikipedia.org/wiki/List_of_brightest_stars) cross-referenced against WGSN names:

| Magnitude cutoff | Approx. star count | Notes |
|---|---|---|
| V < 1.0 | ~10 | The "first magnitude" giants — Sirius to Betelgeuse |
| V < 2.0 | ~30 | All famous naked-eye showstoppers |
| V < 2.5 | ~50 | Good "highlights" range, culturally well-known |
| V < 3.0 | ~93 | Every star in the table below has an IAU name |
| V < 4.0 | ~200+ | Getting into less culturally notable territory |
| V < 6.5 | 9,110 | Full Yale Bright Star Catalog — too many for narration |

**Recommendation: Magnitude V < 2.50, approximately 50 stars.**

Rationale:
- Stars brighter than V = 2.50 are the stars non-astronomers actually know by name (Orion's Belt, the Dippers, Southern Cross, etc.).
- Every one of these has an IAU-approved proper name.
- The set is large enough to provide interesting highlights across the full celestial sphere but small enough that each star has genuine cultural/narrative weight.
- 50 stars gives good sky coverage: observers in the northern hemisphere will typically have 20–30 accessible on any given night; southern hemisphere observers, similar.
- PyEphem ships with 94 built-in bright stars, suggesting this is an accepted convention for "bright star" apps. Source: [PyPI — ephem](https://pypi.org/project/ephem/)

A secondary catalog of V < 3.5 (~120 stars) could be kept in reserve for nights when the top 50 yield few highlights (e.g., observer at mid-latitudes in summer when the Milky Way core is up).

---

## 2. Best Freely-Available Data Source

### Sources evaluated

#### 2a. IAU Catalog of Star Names (IAU-CSN)

- **URL:** https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt (maintained by Eric Mamajek, who chairs WGSN)
- **Format:** Fixed-width text, 16 columns
- **Fields:** Proper name (ASCII + diacritics), Bayer/Flamsteed designation, IAU constellation (3-letter), component, WDS designation, V magnitude (Johnson V or Gaia G), photometric band, HIP number, HD number, RA J2000 (degrees), Dec J2000 (degrees), approval date, notes
- **License:** Public domain / IAU (no explicit restriction; official IAU data)
- **Stars:** ~605 as of mid-2026
- **Magnitude range:** −1.46 to ~21
- **Verdict:** **Authoritative for proper names and IAU constellation assignments**, but the file mixes bright showstoppers with faint exoplanet-host stars. Needs a magnitude filter. RA/Dec are in decimal degrees (ICRS, J2000) — directly usable in Skyfield/Astropy.

#### 2b. Yale Bright Star Catalog, 5th edition (BSC5)

- **URL:** http://tdc-www.harvard.edu/catalogs/bsc5.html (Harvard CfA) / https://heasarc.gsfc.nasa.gov/W3Browse/star-catalog/bsc5p.html (NASA HEASARC)
- **Format:** Binary (fixed 32-byte records); ASCII supplement also available
- **Fields:** HR number, B1950 + J2000 coordinates, galactic coordinates, UBVRI photometry, spectral type, proper motion, parallax, radial velocity, rotational velocity, double-star data, variability data
- **License:** Public domain (government/academic data)
- **Stars:** 9,110 objects; complete to V = 6.5
- **Verdict:** Comprehensive and authoritative for photometric data, but the binary format is inconvenient for Python without a parser library. The BSC5 does **not** carry IAU-approved proper names — it uses older Harvard designations. Not ideal as a primary source.

#### 2c. HYG Database v4.1

- **URL:** https://astronexus.com/projects/hyg (GitHub: astronexus/HYG-Database)
- **Format:** CSV (`hyg_v41.csv`), 25+ columns
- **Fields:** `id, hip, hd, hr, gl, bf, ra, dec, proper, dist, pmra, pmdec, rv, mag, absmag, spect, ci, x, y, z, vx, vy, vz, rarad, decrad, pmrarad, pmdecrad, bayer, flam, con, comp, comp_primary, base, lum, var, var_min, var_max`
- **License:** Creative Commons Attribution-ShareAlike 4.0
- **Stars:** ~120,000 (Hipparcos + Yale + Gliese union)
- **Verdict:** **Best all-in-one source for Python apps.** CSV loads directly into Pandas. Includes `proper` (common/proper name), `con` (IAU constellation abbreviation), `spect` (spectral type), `ci` (color index B-V), `dist` (distance in parsecs), and all coordinates in J2000. Filter by `mag < 2.5` to get the desired subset. Proper names are sourced primarily from Hipparcos and may lag IAU WGSN by a few names, but for the V < 2.5 set all major proper names are present.

#### 2d. cyschneck/iau-star-names (GitHub)

- **URL:** https://github.com/cyschneck/iau-star-names
- **Format:** Two CSVs: `iau_proper_stars.csv` (names + etymology + approval date) and `stars_with_data.csv` (coordinates + magnitude)
- **License:** Not stated (community project; data sourced from IAU)
- **Updated:** Weekly, most recently July 2026
- **Verdict:** Useful as a supplement for IAU-canonical proper names and etymologies, but not suitable as the primary data source (split across two files, no single authoritative source, uncertain license).

### Recommendation

**Use HYG v4.1 as the primary catalog** (easy CSV load, all fields in one file, CC-BY-SA 4.0 license) **cross-referenced with the IAU-CSN text file** (authoritative for proper names where HYG lags).

Workflow:
1. Download `hyg_v41.csv` from the [HYG GitHub repository](https://github.com/astronexus/HYG-Database/tree/main/hyg/CURRENT).
2. Filter rows where `mag <= 2.5` (or chosen cutoff) and `proper` is not empty.
3. Spot-check any star whose `proper` name differs from the IAU-CSN list and apply corrections.
4. Bake the resulting ~50-star subset into a static JSON file in the StarCast repo — no runtime catalog loading needed.

---

## 3. Required Data Fields Per Star

### Minimum required

| Field | Source column (HYG) | Notes |
|---|---|---|
| Proper name | `proper` | IAU-approved; cross-check with IAU-CSN |
| Bayer designation | `bayer` + `flam` + `con` | e.g., "α CMa" |
| RA J2000 (hours) | `ra` | Already in decimal hours in HYG |
| Dec J2000 (degrees) | `dec` | Already in decimal degrees |
| Apparent magnitude V | `mag` | Johnson V (or Gaia G for a few) |
| IAU constellation (3-letter) | `con` | e.g., "CMa" |

### Strongly recommended for narration

| Field | Source column (HYG) | Notes |
|---|---|---|
| Spectral type | `spect` | Enables color description ("blue-white giant") |
| B-V color index | `ci` | `ci < 0` = blue; `ci ~0.6` = Sun-like yellow; `ci > 1.0` = orange/red |
| Distance (parsecs) | `dist` | Multiply by 3.2616 for light-years |
| Absolute magnitude | `absmag` | Useful for luminosity context |
| Hipparcos number | `hip` | Cross-reference key |
| HR number | `hr` | Yale BSC5 cross-reference |

### Optional / nice-to-have

| Field | Source | Notes |
|---|---|---|
| Etymology / cultural origin | IAU-CSN notes / cyschneck repo | Enriches AI narration |
| Variable type | `var` in HYG | e.g., Betelgeuse is semi-regular |
| Proper motion | `pmra`, `pmdec` | Not needed for visibility, interesting for narrative |

---

## 4. Sample Data Table — Top 10 Stars (All Recommended Fields)

Data from [Wikipedia: List of brightest stars](https://en.wikipedia.org/wiki/List_of_brightest_stars) and IAU-CSN.

| Rank | Proper Name | Bayer | Con | RA J2000 (°) | Dec J2000 (°) | Mag V | Spect | B-V | Dist (ly) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Sirius | α CMa | CMa | 101.287 | −16.716 | −1.46 | A0mA1 Va | 0.00 | 8.6 | Brightest star in the sky |
| 2 | Canopus | α Car | Car | 95.988 | −52.696 | −0.74 | A9 II | 0.15 | 310 | Brightest in southern sky |
| 3 | Rigil Kentaurus | α Cen | Cen | 219.902 | −60.834 | −0.27 | G2V+K1V | 0.71 | 4.34 | Nearest star system to Sun |
| 4 | Arcturus | α Boo | Boo | 213.915 | +19.182 | −0.05 | K1.5 III | 1.23 | 37 | Brightest northern star |
| 5 | Vega | α Lyr | Lyr | 279.235 | +38.784 | +0.03 | A0 Va | 0.00 | 25 | Former north pole star |
| 6 | Capella | α Aur | Aur | 79.172 | +45.998 | +0.08 | K0+G1 III | 0.80 | 43 | Spectroscopic binary |
| 7 | Rigel | β Ori | Ori | 78.634 | −8.202 | +0.13 | B8 Ia | −0.03 | 860 | Blue supergiant |
| 8 | Procyon | α CMi | CMi | 114.825 | +5.225 | +0.34 | F5 IV-V | 0.42 | 11 | Has white dwarf companion |
| 9 | Achernar | α Eri | Eri | 24.429 | −57.237 | +0.46 | B3 Vpe | −0.16 | 140 | Fastest-spinning bright star |
| 10 | Betelgeuse | α Ori | Ori | 88.793 | +7.407 | +0.50 | M1-M2 Ia | 1.85 | 640 | Red supergiant, variable |

> **RA/Dec source:** IAU-CSN file at https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt (ICRS J2000, epoch 2000.0). Values rounded to 3 decimal places in degrees.

---

## 5. Recommended Catalog Subset — Stars with V < 2.50

Based on data from [Wikipedia: List of brightest stars](https://en.wikipedia.org/wiki/List_of_brightest_stars), here are all 93 IAU-named stars brighter than V = 2.50, the recommended full catalog:

| Rank | Proper Name | Bayer | Con | Mag V | Spect | Dist (ly) |
|---|---|---|---|---|---|---|
| 1 | Sirius | α CMa | CMa | −1.46 | A0mA1 Va | 8.6 |
| 2 | Canopus | α Car | Car | −0.74 | A9 II | 310 |
| 3 | Rigil Kentaurus | α Cen | Cen | −0.27 | G2V/K1V | 4.34 |
| 4 | Arcturus | α Boo | Boo | −0.05 | K1.5 III | 37 |
| 5 | Vega | α Lyr | Lyr | 0.03 | A0 Va | 25 |
| 6 | Capella | α Aur | Aur | 0.08 | K0+G1 III | 43 |
| 7 | Rigel | β Ori | Ori | 0.13 | B8 Ia | 860 |
| 8 | Procyon | α CMi | CMi | 0.34 | F5 IV-V | 11 |
| 9 | Achernar | α Eri | Eri | 0.46 | B3 Vpe | 140 |
| 10 | Betelgeuse | α Ori | Ori | 0.50 | M1-M2 Ia | 640 |
| 11 | Hadar | β Cen | Cen | 0.61 | B1 III | 390 |
| 12 | Altair | α Aql | Aql | 0.76 | A7 V | 17 |
| 13 | Acrux | α Cru | Cru | 0.76 | B0.5+B1 IV-V | 320 |
| 14 | Aldebaran | α Tau | Tau | 0.86 | K5 III | 65 |
| 15 | Antares | α Sco | Sco | 0.96 | M1.5 Iab | 550 |
| 16 | Spica | α Vir | Vir | 0.97 | B1 III-IV | 250 |
| 17 | Pollux | β Gem | Gem | 1.14 | K0 III | 34 |
| 18 | Fomalhaut | α PsA | PsA | 1.16 | A3 V | 25 |
| 19 | Deneb | α Cyg | Cyg | 1.25 | A2 Ia | 2,600 |
| 20 | Mimosa | β Cru | Cru | 1.25 | B0.5 III | 280 |
| 21 | Regulus | α Leo | Leo | 1.39 | B8 IVn | 79 |
| 22 | Adhara | ε CMa | CMa | 1.50 | B2 II | 430 |
| 23 | Castor | α Gem | Gem | 1.58 | A1 V+Am | 51 |
| 24 | Shaula | λ Sco | Sco | 1.63 | B2 IV | 570 |
| 25 | Gacrux | γ Cru | Cru | 1.64 | M3.5 III | 89 |
| 26 | Bellatrix | γ Ori | Ori | 1.64 | B2 III | 250 |
| 27 | Elnath | β Tau | Tau | 1.65 | B7 III | 130 |
| 28 | Miaplacidus | β Car | Car | 1.69 | A1 III | 110 |
| 29 | Alnilam | ε Ori | Ori | 1.69 | B0 Ia | 1,180 |
| 30 | Alnair | α Gru | Gru | 1.74 | B6 V | 100 |
| 31 | Alnitak | ζ Ori | Ori | 1.77 | O9.5 Iab | 1,300 |
| 32 | Alioth | ε UMa | UMa | 1.77 | A1 III-IVp | 83 |
| 33 | Dubhe | α UMa | UMa | 1.79 | K0 III | 120 |
| 34 | Mirfak | α Per | Per | 1.82 | F5 Ib | 510 |
| 35 | Wezen | δ CMa | CMa | 1.82 | F8 Ia | 1,800 |
| 36 | Regor | γ Vel | Vel | 1.83 | WC8+O7.5III | 840 |
| 37 | Sargas | θ Sco | Sco | 1.84 | F0 II | 330 |
| 38 | Kaus Australis | ε Sgr | Sgr | 1.85 | B9.5 III | 140 |
| 39 | Avior | ε Car | Car | 1.86 | K3 III | 600 |
| 40 | Alkaid | η UMa | UMa | 1.86 | B3 V | 100 |
| 41 | Menkalinan | β Aur | Aur | 1.90 | A1mIV+A1mIV | 80 |
| 42 | Atria | α TrA | TrA | 1.91 | K2 IIb-IIIa | 390 |
| 43 | Alhena | γ Gem | Gem | 1.92 | A1.5 IV+ | 100 |
| 44 | Peacock | α Pav | Pav | 1.94 | B3 V | 180 |
| 45 | Alsephina | δ Vel | Vel | 1.96 | A1 Va(n) | 80 |
| 46 | Mirzam | β CMa | CMa | 1.98 | B1 II-III | 500 |
| 47 | Polaris | α UMi | UMi | 1.98 | F7 Ib | 430 |
| 48 | Alphard | α Hya | Hya | 2.00 | K3 II-III | 180 |
| 49 | Hamal | α Ari | Ari | 2.00 | K1 IIIb | 66 |
| 50 | Diphda | β Cet | Cet | 2.02 | K0 III | 96 |
| 51 | Mizar | ζ UMa | UMa | 2.04 | A2 Vp+Am | 83 |
| 52 | Nunki | σ Sgr | Sgr | 2.05 | B2.5 V | 230 |
| 53 | Menkent | θ Cen | Cen | 2.06 | K0 III | 59 |
| 54 | Alpheratz | α And | And | 2.06 | B8 IVpMnHg | 97 |
| 55 | Mirach | β And | And | 2.07 | M0 III | 200 |
| 56 | Rasalhague | α Oph | Oph | 2.07 | A5IVnn | 47 |
| 57 | Algieba | γ Leo | Leo | 2.08 | K0 III | 130 |
| 58 | Kochab | β UMi | UMi | 2.08 | K4 III | 130 |
| 59 | Saiph | κ Ori | Ori | 2.09 | B0.5 Ia | 650 |
| 60 | Denebola | β Leo | Leo | 2.11 | A3 Va | 36 |
| 61 | Algol | β Per | Per | 2.12 | B8 V | 93 |
| 62 | Tiaki | β Gru | Gru | 2.15 | M5 III | 170 |
| 63 | Muhlifain | γ Cen | Cen | 2.17 | A0 III | 130 |
| 64 | Aspidiske | ι Car | Car | 2.21 | A9 Ib | 690 |
| 65 | Suhail | λ Vel | Vel | 2.21 | K4 Ib | 570 |
| 66 | Alphecca | α CrB | CrB | 2.23 | A0 V | 75 |
| 67 | Mintaka | δ Ori | Ori | 2.23 | O9.5 II | 900 |
| 68 | Sadr | γ Cyg | Cyg | 2.23 | F8 Iab | 1,500 |
| 69 | Eltanin | γ Dra | Dra | 2.23 | K5 III | 150 |
| 70 | Schedar | α Cas | Cas | 2.24 | K0 IIIa | 230 |
| 71 | Naos | ζ Pup | Pup | 2.25 | O4 If(n)p | 1,080 |
| 72 | Almach | γ And | And | 2.26 | K3 IIb | 350 |
| 73 | Caph | β Cas | Cas | 2.28 | F2 III | 54 |
| 74 | Izar | ε Boo | Boo | 2.29 | K0 II-III | 202 |
| 75 | Uridim | α Lup | Lup | 2.30 | B1.5 III | 550 |
| 76 | (unnamed) | ε Cen | Cen | 2.30 | B1 III | 380 |
| 77 | Dschubba | δ Sco | Sco | 2.31 | B0.3 IV | 400 |
| 78 | Larawag | ε Sco | Sco | 2.31 | K1 III | 65 |
| 79 | (unnamed) | η Cen | Cen | 2.35 | B1.5 Vne | 310 |
| 80 | Merak | β UMa | UMa | 2.37 | A1 IVps | 79 |
| 81 | Ankaa | α Phe | Phe | 2.38 | K0.5 IIIb | 77 |
| 82 | Girtab | κ Sco | Sco | 2.39 | B1.5 III | 460 |
| 83 | Enif | ε Peg | Peg | 2.40 | K2 Ib | 670 |
| 84 | Scheat | β Peg | Peg | 2.42 | M2.5 II-IIIe | 200 |
| 85 | Sabik | η Oph | Oph | 2.43 | A1 IV | 88 |
| 86 | Phecda | γ UMa | UMa | 2.44 | A0 Ve | 83 |
| 87 | Aludra | η CMa | CMa | 2.45 | B5 Ia | 2,000 |
| 88 | Alderamin | α Cep | Cep | 2.46 | A8Vn | 49 |
| 89 | Markeb | κ Vel | Vel | 2.46 | B2 IV | 540 |
| 90 | Tiansi | γ Cas | Cas | 2.47 | B0.5 IVe | 610 |
| 91 | Markab | α Peg | Peg | 2.48 | A0 IV | 140 |
| 92 | Aljanah | ε Cyg | Cyg | 2.48 | K0 III-IV | 72 |
| 93 | Acrab | β Sco | Sco | 2.50 | B0.5 IV-V | 404 |

> Note: Rows 76 and 79 (ε Cen, η Cen) do not have IAU proper names as of mid-2026 and should be excluded from the narration catalog. Effective named-star count at V < 2.50 is **~91**.

---

## 6. Final Recommendation

### Catalog

**HYG Database v4.1** — primary source  
- Download: `hyg/CURRENT/hyg_v41.csv` from https://github.com/astronexus/HYG-Database  
- License: CC-BY-SA 4.0 (attribution required)  
- Filter: `mag <= 2.5` AND `proper != ''` → approximately 91 stars  

**IAU-CSN text file** — authoritative cross-reference for proper names  
- URL: https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt  
- Use to verify/correct proper names where HYG lags WGSN approvals  

### Magnitude cutoff

**V ≤ 2.50** — approximately 91 IAU-named stars

This is the recommended cutoff because:
1. Every star at this brightness is naked-eye visible from any dark site; they are the stars that defined human constellation-lore across cultures.
2. The IAU WGSN has approved proper names for virtually all of them.
3. The subset is large enough to guarantee highlights for any observer location and season, yet small enough that the AI narrator can develop distinct, memorable narratives for each.
4. V = 2.50 is close to the traditional "second magnitude" boundary — a natural astronomical division.

### Fields to include in the baked-in JSON

```json
{
  "proper_name": "Sirius",
  "bayer": "α CMa",
  "constellation": "CMa",
  "ra_j2000_deg": 101.287,
  "dec_j2000_deg": -16.716,
  "mag_v": -1.46,
  "spectral_type": "A0mA1 Va",
  "bv_color": 0.00,
  "distance_ly": 8.6,
  "hip": 32349,
  "hr": 2491
}
```

The `ra_j2000_deg` and `dec_j2000_deg` fields are in ICRS J2000 decimal degrees, matching the IAU-CSN coordinate system and directly usable with [Skyfield](https://rhodesmill.org/skyfield/stars.html)'s `Star(ra_hours=..., dec_degrees=...)` constructor (convert degrees to hours by dividing RA by 15).

### Python loading sketch

```python
import pandas as pd

df = pd.read_csv("hyg_v41.csv")
bright_named = df[(df["mag"] <= 2.5) & (df["proper"].notna()) & (df["proper"] != "")]
bright_named = bright_named[[
    "proper", "bayer", "con", "ra", "dec",
    "mag", "spect", "ci", "dist", "hip", "hr"
]].copy()
bright_named["distance_ly"] = bright_named["dist"] * 3.2616
bright_named.to_json("bright_stars.json", orient="records", indent=2)
```

---

## Sources

- [IAU Catalog of Star Names (IAU-CSN)](https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt) — Eric Mamajek / IAU WGSN, primary star name authority
- [IAU: Naming Stars](https://www.iau.org/public/themes/naming_stars/) — IAU public page on WGSN
- [IAU Working Group on Star Names — Wikipedia](https://en.wikipedia.org/wiki/IAU_Working_Group_on_Star_Names)
- [List of brightest stars — Wikipedia](https://en.wikipedia.org/wiki/List_of_brightest_stars) — source for magnitude/spectral type/distance table
- [Bright Star Catalogue — Wikipedia](https://en.wikipedia.org/wiki/Bright_Star_Catalogue) — Yale BSC5 overview
- [BSC5P at NASA HEASARC](https://heasarc.gsfc.nasa.gov/W3Browse/star-catalog/bsc5p.html) — BSC5 field reference
- [HYG Database — Astronomy Nexus](https://astronexus.com/projects/hyg) — primary recommended data source
- [HYG Database GitHub — astronexus/HYG-Database](https://github.com/astronexus/HYG-Database/tree/main/hyg) — CSV download
- [cyschneck/iau-star-names on GitHub](https://github.com/cyschneck/iau-star-names) — community IAU name tracker, updated weekly
- [Skyfield: Stars and Distant Objects](https://rhodesmill.org/skyfield/stars.html) — Python visibility calculation library
- [PyPI: ephem](https://pypi.org/project/ephem/) — notes 94 built-in bright stars, confirming this magnitude range is conventional
- [star-facts.com: Complete IAU Star Names](https://www.star-facts.com/star-names/) — total count of 605 approved names
- [exopla.net: IAU-CSN catalog](https://exopla.net/star-names/modern-iau-star-names/) — interactive WGSN catalog with CSV export
