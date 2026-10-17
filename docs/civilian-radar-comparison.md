# Civilian radar comparison preparation

Prepared 17 October 2026, before any detector output for these cases. This is a
bounded demolition/change candidate and an **unverified reference candidate**. It
does not complete quiet/change discrimination. No Earth Engine catalog, analysis,
rendering or workflow dispatch was requested.

## Frozen selection

The civilian A66 Salzbachtal bridge in Wiesbaden was demolished on 6 November 2021
around noon local CET (approximately 11:00 UTC), according to the
[demolition contractor](https://www.reisch-sprengtechnik.de/referenz_sprengung-salzbachtalbruecke-wiesbaden.html).
The [operator project page](https://www.autobahn.de/planen-bauen/projekt/neubau-salzbachtalbruecke)
lists independently dated July 2 intact/closed, November 6 demolition and November
16 cleanup galleries. Those gallery images were not independently inspected.
The [joint authority statement of October 29](https://www.presseportal.de/blaulicht/pm/43562/5059986)
explicitly dates site photographs to October 27. These anchors fix selection
independently of detector response; they do not label all cells as changed or quiet.

Both cases use a 500 m square centered at **50.0522688, 8.25507195**. The center is
the midpoint of union bounds for OSM bridge polygons 499938151 version 19 and
1229149143 version 6. These are rebuilt bridge geometry dated October 2, 2025,
used only as a locator, not a surveyed 2021 footprint. The south polygon itself
warns that the rebuilt bridge is wider. [Locator metadata](evidence/salzbachtal-locator-2026-10-17.json)
retains node coordinates, way versions, attribution and response hashes.

The production snapped grid is EPSG:32632, bounds
`[446420, 5544460, 446920, 5544960]`, transform
`[10, 0, 446420, 0, -10, 5544960]`: 50 x 50 cells at 10 m spacing.
The transformed corners, exact catalog queries and source footprints are retained.

| Case | Baseline UTC, inclusive start / exclusive end | Target UTC, inclusive start / exclusive end | Interpretation |
| --- | --- | --- | --- |
| `salzbachtal-demolition` | Oct 9 - Nov 6, 2021 | Nov 6 - Nov 13, 2021 | Demolition-associated change candidate; staging and cleanup may contribute |
| `salzbachtal-pre-demolition` | Sep 25 - Oct 23, 2021 | Oct 23 - Oct 30, 2021 | Same-AOI reference candidate anchored by the authority-dated Oct 27 photographs; quiet truth unavailable |

Both labels remain **unreviewed**, with `quiet_ground_truth=false` (not established). Preparation can
already affect the event baseline. Starting the target at November 6 preserves a
baseline ending before the event day, but a November 6 morning acquisition would
precede demolition. The complete saved public inventory contains **no November 6
acquisition**. All three event targets are after November 6. The offline replay
annotates timing without removing a production-eligible source; an approved EE run
must check its actual source times again rather than silently drop unexpected IDs.

The case harness retains the approximate event reference and its uncertainty in each
record. Every actual optical and radar comparison receives a **before**, **after**,
**straddling** or **unknown** timing annotation from its saved acquisition timestamps.
These appear beside images, in the queue and in check history, including insufficient
comparisons. Missing/invalid/equal-to-reference timestamps stay unknown. Before,
straddling and unknown comparisons explicitly warn against post-event interpretation.
The annotation uses source start times: full exposure intervals are not available,
and an after-reference annotation alone cannot establish event effects. It does not
remove sources, alter detector statuses or change review identities.

## Independently verified public acquisition metadata

[Saved public inventory](../validation/salzbachtal-s1-catalog.json) records 24
original ASF Sentinel-1 GRD products for the snapped grid and union
`[2021-09-25T00:00:00Z, 2021-11-13T00:00:00Z)`. Copernicus STAC independently returns
24 COG counterparts matching acquisition identity through the datatake filename
field, mode, orbit/pass, platform and polarizations. Their trailing checksums differ:
this is not exact product-byte or processing equivalence. Both queries use limit
200, return below that limit and have no next-page link. All four grid corners lie
inside each recorded footprint. This is footprint metadata, not valid-cell coverage.

| Case | Relative orbit / pass | Target acquisitions UTC | Distinct baseline days |
| --- | --- | --- | ---: |
| Demolition | 15 / ascending | Nov 10 17:16:26 | 5 |
| Demolition | 66 / descending | Nov 8 05:33:49 | 5 |
| Demolition | 139 / descending | Nov 7 05:42:45 | 4 |
| Pre-demolition | 15 / ascending | Oct 23 17:15:57; Oct 29 17:16:26 | 4 |
| Pre-demolition | 66 / descending | Oct 27 05:33:49 | 5 |
| Pre-demolition | 139 / descending | Oct 26 05:42:46 | 5 |

The snapshot keeps every exact original product ID, UTC start/stop, absolute and
relative orbit, pass, platform, mode, VV/VH, integer datatake, footprint, counterpart
ID and query/retrieval provenance. Raw-response SHA-256 hashes are retained; raw
responses stay local because their asset links are unnecessary for this evidence.
Query URLs are public metadata requests that can be repeated without EE credentials.
API semantics follow [ASF documentation](https://docs.asf.alaska.edu/api/keywords/)
and [Copernicus STAC documentation](https://documentation.dataspace.copernicus.eu/APIs/STAC.html).

Replay without a network request:

```text
python -m sentinel_monitor.catalog_audit --case-file validation/cases.json --catalog validation/salzbachtal-s1-catalog.json --settings settings.yaml
```

[Saved replay](evidence/salzbachtal-eligibility-2026-10-17.json) uses the existing
production orbit/pass grouping, datatake acquisition key and distinct-UTC-day
baseline helper. All six group/window combinations are metadata-eligible under
unchanged IW + VV + VH and minimum two baseline-day rules. Every baseline mixes
Sentinel-1A/B, as production grouping currently permits; matching orbit/pass alone
cannot remove platform/processing uncertainty. Duplicate slices do not supply a
second day. The replay rejects incomplete/truncated evidence, mismatched grid/date
coverage and inconsistent product metadata. Empty groups do not create negatives.

This is **public-catalog availability verification**, not verification of
`COPERNICUS/S1_GRD` ingestion. Actual EE IDs, pixel masks, incidence angle, terrain,
backscatter validity, at least two valid daily baseline samples per cell and 70%
common valid coverage remain unverified. All production settings are frozen in
[selection evidence](evidence/salzbachtal-selection-2026-10-17.json), including strict
3 dB VV-or-VH difference, nine connected cells and 10 m smoothing. No threshold,
AOI, date, source exclusion or model was fitted to a detector output.

## Quiet-reference evidence gate

The [environmental authority report, printed pages 8-10](https://rp-darmstadt.hessen.de/sites/rp-darmstadt.hessen.de/files/2022-07/rp-journal-arbeitsschutz-umwelt_2022-07.pdf)
documents soil/sand fallbeds, retaining walls, scaffolding and plant interventions.
Its limited post-event asset inspections cannot certify unchanged surroundings.
The adjacent wastewater plant therefore does not supply a defensible quiet control.
The earlier same-AOI case also includes a period of known demolition preparation.

One further bounded lead was checked: DLR's published Sentinel-1 calibration field.
The [2024 transponder paper](https://elib.dlr.de/198833/1/eusar2024_sraab_v10_uploaded.pdf)
supports point-target operation through 2022; the
[2018 methods paper](https://elib.dlr.de/115839/1/Schmidt-et-al_OPEN-ACCESS_2018-03-09_radiometric_accuracy_and_stability_of_sentinel1a_determined_using_point_targets.pdf)
measures isolated responses with background clutter removed. Our inference is that
these sources cannot establish quietness of an entire compact land AOI. No extra
fixture or acquisition search was made for that rejected lead.

The exact missing evidence is independently dated imagery/property evidence
bracketing the reference acquisitions over the **entire AOI**, showing absence of
material surface works during both reference intervals, or an applicable
distributed-target stability study with explicit AOI and dates. Human acquisition
review remains necessary. Neither pre-event timing, asset survival, a detector
negative nor calibration-target stability fills this gap. Do not score either
candidate as a verified quiet case or calculate false-positive/accuracy claims.

## Reviewable next live actions, not executed

After separate approval for the protected-main merge and new paid live analysis,
the smallest execution of this two-case candidate design is **two serial manual
Validation acceptance dispatches** on the exact approved merged commit:

1. `ref=main`, `check=imagery`, `case_id=salzbachtal-demolition`, `imagery_diagnostics=true`.
2. `ref=main`, `check=imagery`, `case_id=salzbachtal-pre-demolition`, `imagery_diagnostics=true`.

The existing harness also enables signed radar diagnostics and review previews,
and processes both sensors under production rules. There is no radar-only dispatch
in this preparation. Capture returned EE inventory, orbit groups, all target times,
validity diagnostics and unchanged original imagery; stop and report missing or
unexpected acquisitions instead of adapting the frozen design. Even successful
runs would not supply the missing independent quiet truth.

Each invocation stays at one 500 m site, with no Pages deployment or results-branch
write. Active sites, scheduling, the existing local pilot and private review data
are outside this preparation. A live dispatch, main merge and publication are not
part of the draft PR's authorization.

## Offline verification

All 105 offline tests, lint/format checks, configuration validation and exact replay
comparison passed. Temporary Chrome contexts checked desktop/mobile layouts and
JavaScript-disabled access with synthetic data only. Both sensors display all four
timing classes, including history for insufficient comparisons, with no external
requests or network writes. Desktop/mobile screenshots were visually inspected.
[QA evidence](evidence/salzbachtal-qa-2026-10-17.json) retains the checks and hashes.
Prior frozen case values, detector/preprocessing code, production settings, active
sites, monitor workflow and review identity/notes JavaScript are unchanged.
