# Sentinel-2 civilian human-review pilot

Frozen 18 October 2026 (Europe/Helsinki), before detector output or satellite-pixel inspection.

One useful civilian review candidate is prepared: **genoa-morandi-east-demolition**,
the remaining eastern Morandi viaduct in Genoa. The city records the demolition
on [28 June 2019 at 09:37 local time](https://smart.comune.genova.it/comunicati-stampa-articoli/lex-ponte-morandi-demolito-con-pi%C3%B9-di-cinquecento-chili-di-esplosivo)
and [identifies eastern piers 10 and 11](https://smart.comune.genova.it/articoli/ponte-morandi-abbattute-le-pile-10-e-11).
This is a transport redevelopment example for human before/after review. Automated
flags provide triage; human appearance observations do not become certified ground
truth. Formal accuracy calibration and a certified quiet pair are not prerequisites
for this bounded pilot.

## Frozen inputs and location

| Input | Value |
| --- | --- |
| Manifest | `validation/sentinel2-cases.json` (separate from existing cases) |
| Case | `genoa-morandi-east-demolition` |
| Centre | 44.4248 N, 8.8910 E |
| Width | 500 m; 50 x 50 analysis cells at 10 m spacing |
| Grid | EPSG:32632; bounds [491070, 4918810, 491570, 4919310] m |
| Baseline, UTC | [2019-05-31, 2019-06-28) |
| Target, UTC | [2019-06-28, 2019-07-05) |
| Event reference | 2019-06-28T07:37:00Z (minute precision) |
| Sensor requested for proposed run | Optical only, explicitly `--sensors optical` |
| Provisional label | Documented demolition candidate; unreviewed |

The centre is an analyst-selected contextual point, using the
[official evacuation map](https://www.commissario.ricostruzione.genova.it/sites/default/files/upload/aree%20evacuazione_26giugno19.png)
and [Via Walter Fillak street geometry](https://www.openstreetmap.org/way/110707992).
The 500 m square covers the eastern landward works and railway/urban context, with
possible narrow river-edge overlap on the west. It is predominantly land, rather
than a water scene. The map does not survey the demolition footprint. Current
street geometry supplies a location cross-check, not 2019 surface truth.
[Locator evidence](evidence/sentinel2-locator-2026-10-18.json) preserves the map URL/hash,
OSM query, way version/coordinates, exact grid and geographic corners. OSM attribution:
[OpenStreetMap contributors, ODbL](https://www.openstreetmap.org/copyright).

The unchanged rolling 28-day baseline includes demolition preparation, nearby works
and reconstruction already underway. July 1 can show rubble, cleanup, shadows or
other surface differences. Neither interval is labelled quiet. No thresholds,
mask, patch size, AOI or dates were adjusted to fit a detector response.

## Public catalog preparation

An exact-grid polygon query of the public Copernicus Data Space Ecosystem L2A
catalog returned seven SAFE products: six baseline acquisition days and one target
day, all in tile T32TMQ, relative orbit 65. The complete response reports seven
results and no continuation link. A separate bounded source/catalog check returned
the same product identities using a slightly enclosing box.

| UTC acquisition day | Role | Scene cloud percentage |
| --- | --- | ---: |
| 2019-06-01 | Baseline | 4.09 |
| 2019-06-06 | Baseline | 67.60 |
| 2019-06-11 | Baseline | 88.09 |
| 2019-06-16 | Baseline | 14.91 |
| 2019-06-21 | Baseline | 92.24 |
| 2019-06-26 | Baseline | 0.03 |
| 2019-07-01 | Target, after demolition | 1.76 |

These percentages describe catalog scenes, **not AOI valid coverage**. The replay
applies no scene-cloud cutoff because production uses SCL classes 4/5 and Cloud
Score+ per pixel. Six catalog baseline days do not guarantee two valid observations
at every cell, the required 70% common coverage, or EE ingestion. CDSE ContentDate
is a product sensing reference; its identical start/end fields are not an exposure
duration. Tile timestamps from other catalogs have different semantics. Original
and reprocessed products, overlapping tiles and platforms do not create extra UTC
acquisition days.

The shortlist was limited to two candidates. Tropicana Las Vegas demolition was
independently confirmed, but its frozen event week had only two baseline dates
and a roughly 40% scene-cloud target. The clearer next acquisition left only one
baseline day under the unchanged rolling window. Genoa was chosen from independent
event evidence and catalog metadata before any detector output.

Retained evidence:

- [Exact catalog query and completeness](evidence/sentinel2-catalog-query-2026-10-18.json).
- [Complete public CDSE response](evidence/sentinel2-cdse-2019-genoa.json).
- [Normalized product IDs, times, footprints and cloud metadata](../validation/sentinel2-optical-catalog.json).
- [Offline eligibility replay](evidence/sentinel2-eligibility-2026-10-18.json).
- [Selection and exact LF SHA-256 hashes](evidence/sentinel2-selection-2026-10-18.json).

The manifest's exact UTF-8/LF SHA-256 is
`62ca8ffd2c873176950aaf146b956f9230098bddd33287e2bce0ab7f3f7c36cb`.
Public metadata was read; no satellite raster was downloaded, no EE analysis or
render was requested, and no private review data was accessed.

## Reproduce offline

From the repository root, with this checkout's source on the Python import path:

```console
python -m sentinel_monitor.optical_catalog_audit --case-file validation/sentinel2-cases.json --catalog validation/sentinel2-optical-catalog.json
python -m pytest tests/test_optical_catalog_audit.py
```

The first command emits the saved eligibility JSON without authentication, catalog
requests or EE initialization. It checks the recorded grid/window coverage, product
identities, UTC boundaries, source bound and distinct baseline days. Spatial catalog
filtering is trusted from the retained query; this replay does not remeasure pixels.

## One proposed live action, not executed

After sensor-selection integration and specific approval for an exact merged commit:

```console
sentinel-monitor review-case --case genoa-morandi-east-demolition --case-file validation/sentinel2-cases.json --sensors optical --imagery-diagnostics --optical-review-stretch --results results-sentinel2-pilot --output site-sentinel2-pilot
```

`review-case` requests previews for every usable comparison, including negatives.
Diagnostics are justified here by the currently unknown ingestion, masks and common
coverage. Paired shared-stretch previews support human comparison and expose display
limitations without changing detection. Both options add bounded EE work/render
requests, included in the proposed single-run approval scope. Source eligibility,
per-cell validity, any preview failures and actual PNG dimensions must remain visible.
Insufficient comparisons remain in history and are not scored as negatives.

The manual Validation acceptance mapping adds only this known case to its choices
and uses `--case-file validation/sentinel2-cases.json` for that ID. Its proposed inputs
are `check=imagery`, `case_id=genoa-morandi-east-demolition`, `sensors=optical`,
`imagery_diagnostics=true`, `optical_review_stretch=true`. The `sensors` CLI/workflow
input is owned by the separate engine increment and must be integrated before live
use; this case-preparation branch alone does not supply it.

A fresh analysis must have a fresh record-generation timestamp and an optical-only
science/cache identity. Legacy records remain immutable, and existing private
observations must not carry into this new report. Human review can record no obvious
change or unclear appearance. This single example cannot establish object/vehicle
counts, construction boundaries, false-positive rates or calibrated field accuracy.
Real EE coverage and rendering are pending; they do not block offline preparation.
Monitoring, existing pilots and publication are outside this proposed action.
