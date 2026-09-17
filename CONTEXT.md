# StarCast

A web app that computes which celestial bodies are accurately positioned in the sky for a given location and night, then produces an AI-written "cosmic weather report" — one headline and up to three highlight cards grounded in real astronomy.

## Language

### Sky & Observation

**Viewing Window**:
The span of a given night during which meaningful observation is possible — from the end of evening astronomical twilight to the start of morning astronomical twilight. All positional calculations use the peak altitude an object reaches within this window.
_Avoid_: "tonight", "dark hours", "observing window"

**In Catalog**:
A celestial body that StarCast knows about and can compute a position for. Being in the catalog says nothing about whether the body is above the horizon on a given night.
_Avoid_: "supported", "tracked", "available"

**Visible**:
A catalog body whose center point (or centroid, for extended objects) reaches a positive altitude at some moment during the Viewing Window for the observer's location. Visibility is a binary per-night determination; it does not imply naked-eye detectability or any minimum brightness threshold.
_Avoid_: "up", "observable", "detectable"

**Peak Altitude**:
The maximum altitude (degrees above the horizon) an object reaches during the Viewing Window. Used for ranking candidates within a category and surfaced in the detail layer.
_Avoid_: "maximum elevation", "culmination altitude"

**Centroid**:
The catalog RA/Dec coordinate used to represent an extended object (constellation, nebula, galaxy) as a single point for horizon checks. A body is Visible if its centroid reaches positive altitude during the Viewing Window.
_Avoid_: "center", "reference point"

### Highlights & Narration

**Highlight**:
A single celestial body (or Significant Event) selected as one of up to three featured subjects in the Cosmic Report for a given night. There is at most one Highlight per Category.
_Avoid_: "feature", "pick", "selection"

**Category**:
One of three fixed slots that structure Highlight selection: (1) Planet or Moon, (2) Constellation, (3) Bright Star / Comet / Nebula / Galaxy / Significant Event. A Category is omitted from the report if no qualifying Visible body exists for it that night.
_Avoid_: "slot", "type", "group"

**Significant Event**:
A time-sensitive astronomical occurrence detected for the current night: a conjunction (two eligible bodies within 2.0° of each other, both Visible at closest approach), a planetary opposition (within 1 day of exact opposition), or a meteor shower within 2 days of its predicted peak with ZHR ≥ 20. A Significant Event takes priority over a standing catalog body when filling Category 3; if more than one qualifies the same night, only one is used.
_Avoid_: "special event", "astronomical event", "rare event"

**Visual Priority**:
The ranking used to select one Highlight from multiple Visible candidates within the same Category. For planets: outer gas giants rank above inner rocky planets; the Moon is treated as a wildcard and may be elevated. Ties are broken by Peak Altitude.
_Avoid_: "importance", "ranking score", "priority score"

**Cosmic Report**:
The complete AI-generated output for one observer-location/night pair: one overall Headline plus up to three Highlight Cards.
_Avoid_: "weather report", "narration", "output", "result"

**Headline**:
A single punchy sentence that captures the most striking thing about the night's sky. The opening element of the Cosmic Report, visible without expanding any card.
_Avoid_: "title", "lede", "summary"

**Highlight Card**:
One entry in the Cosmic Report corresponding to one Highlight. Contains a mini-headline and a 2–4 sentence paragraph written in a conversational tone with poetic flourishes.
_Avoid_: "card", "entry", "story", "highlight story"

### Catalog Objects

**Planet**:
Any of the eight solar-system planets (Mercury through Neptune). Treated as a Category 1 candidate.
_Avoid_: "solar body", "planet candidate"

**Moon**:
Earth's natural satellite. Treated as a Category 1 candidate and may override a Planet via Visual Priority depending on its phase and prominence that night.
_Avoid_: "lunar body", "the Moon" (use just "Moon" in code/copy)

**Named Constellation**:
One of the 88 IAU-recognized constellations, represented in the catalog by its centroid RA/Dec. Treated as a Category 2 candidate.
_Avoid_: "star pattern", "asterism" (asterisms are not Named Constellations)

**Bright Star**:
A named star (beyond the solar system) included in the catalog by virtue of its common name and cultural significance. Treated as a Category 3 candidate.
_Avoid_: "star", "fixed star", "background star"

**DSO (Deep-Sky Object)**:
A non-stellar, non-solar-system object in the Messier catalog (M1–M110). Includes nebulae, galaxies, and star clusters. Treated as a Category 3 candidate.
_Avoid_: "deep sky", "Messier object", "extended object" (use DSO)

**Named Comet**:
A comet with an established proper name (e.g., Halley, Hale-Bopp) that appears in the catalog. Treated as a Category 3 candidate.
_Avoid_: "comet", "periodic comet" (unnamed periodic comets are not in the catalog)

### UI

**Casual Layer**:
The default view of the Cosmic Report: the Headline and up to three Highlight Cards. No positional data is shown.
_Avoid_: "summary view", "simple view", "top-level view"

**Detail Layer**:
The expanded view accessible per Highlight Card that surfaces positional and observational data: altitude, azimuth, rise/set times, magnitude, and a full list of all Visible objects for the night.
_Avoid_: "advanced view", "expanded view", "data view"
