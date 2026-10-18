# Sentinel-2 review analysis scope

Prepared 18 October 2026 (Europe/Helsinki). This engine increment supports a bounded
human review feed. Automated flags are triage; human appearance observations are
not certified ground truth. Formal accuracy calibration is not a prerequisite for
a bounded review pilot, and this change makes no object/vehicle count or detection
accuracy claim.

## Explicit sensor selection

`sentinel-monitor run --sensors {both,optical,radar}` and
`sentinel-monitor review-case --sensors {both,optical,radar}` default to `both`.
The manual **Validation acceptance** workflow exposes the same `sensors` choice
for `check=imagery`, defaulting to `both`. Numeric acceptance remains the tiny
synthetic two-sensor check. Production settings, active sites, monitoring schedules
and the production workflow's default sensor scope are unchanged.

New analysis records save `requested_sensors` as a canonical list: `["optical",
"radar"]`, `["optical"]` or `["radar"]`. Legacy records with no field mean both.
Only exact canonical lists are valid saved scope: explicit `null`, strings, reversed
lists, duplicates and unknown/mixed sensors are invalid, not legacy. A malformed
cache scope is recomputed with fresh provenance; record readers reject it. API calls
may still omit scope or use `None` to select both.
Run summaries save the invocation scope and each site's record scope; isolated
`validation-case.json` also retains it. Missing comparison/area data for a requested
sensor still means unavailable or failed analysis. An omitted sensor was intentionally
unrequested and supplies no negative detection or coverage evidence. Unrequested
sensor areas and overlap stay JSON `null`; no placeholder comparisons are created.
Source diagnostics include only requested sensors.

Optical-only analysis never builds the Sentinel-1 source collection, source inventory,
terrain mask or prepared radar graph. Radar-only similarly skips Sentinel-2 and Cloud
Score+ collections. Area summaries reduce only available masks, with overlap computed
only when both masks exist. The optical bands, SCL/Cloud Score+ masking, fixed 10 m
grid, rolling 28-day baseline, minimum observations/coverage, reflectance threshold
and connected-patch math are unchanged. Sentinel-2 B2/B3/B4/B8 remain 10 m source
bands, and a larger preview does not add ground detail. Insufficient coverage and
service/render failures remain visible in records.

The CLI rejects explicit `--radar-diagnostics` with optical-only scope and
`--optical-review-stretch` with radar-only scope before authentication or analysis.
`run --optical-review-stretch` still requires `--review-previews`; demo mode still
rejects live review/diagnostic options. `review-case` automatically requests radar
diagnostics only if radar is selected, avoiding a conflict in optical-only runs.
Demo mode uses the same selected scope with explicitly synthetic imagery; controlled
radar/optical failure scenarios affect only a requested matching sensor.

## Identity and retained records

Historical both-sensor science signatures are byte-for-byte unchanged: sensor scope
is added to signature input only for single-sensor analysis. Optical-only, radar-only
and both therefore cannot share a science key, comparison ID or cache file. Cache
reuse also validates saved scope, treating absent legacy scope as both. Canonical
programmatic order is optical then radar; unknown, duplicate and empty scopes reject.

A new analysis writes a fresh `generated_at`, including refreshes and frozen-case
runs. Existing eight-field review identity remains unchanged. Fixed/shared display
switching within one record preserves that identity; a new single-sensor science key
and generation timestamp cannot inherit old reviews. The frozen-case harness only
annotates its exact current science key and scope. Existing pilot records, original
PNGs and private review files are not inputs to this implementation or its tests.

## Concrete live proposal — not executed

After the engine and report changes are reviewed and specifically approved, one
artifact-only **Validation acceptance** invocation could exercise real-source shared
optical rendering at the frozen Gobabeb reference:

- Ref: the reviewed merged main commit, recorded before dispatch.
- Inputs: `check=imagery`, `case_id=gobabeb-quiet-reference`, `sensors=optical`,
  `imagery_diagnostics=true`, `optical_review_stretch=true`.
- AOI: the existing 200 m square at latitude -23.60153, longitude 15.12589.
- Target UTC window: `[2022-07-11, 2022-07-18)`; baseline:
  `[2022-06-13, 2022-07-11)`.
- Current unchanged settings yield optical-only science key `becbd4accdce33da8fa5`;
  historical both scope yields `be8931092c4c027d838c`. Recompute against the exact
  reviewed commit if settings change.
- Equivalent local command: `sentinel-monitor review-case --case
  gobabeb-quiet-reference --sensors optical --imagery-diagnostics
  --optical-review-stretch` (with the existing authorized EE project).
- Save fresh records and fixed/shared PNG triples in an isolated artifact bundle.
  Verify requested scope, no radar diagnostics/collections, null radar and overlap,
  unchanged detector math, reported coverage and source IDs, fresh review identity,
  and shared display range/endpoint information. Preserve old pilots and reviews.

This proposal needs fresh optical catalog/comparison work and extra diagnostics and
render requests. It has not run and is not included in general continue authorization.
No merge, live Earth Engine request, deployment, results-branch write or monitoring
expansion was performed for this increment. The coordinator owns the separate local
bundle built from retained Park Fire/Gobabeb imagery; this work does not duplicate it.

## Offline verification

All 266 offline tests and 9 subtests pass, including 64 new scope checks; Ruff lint
and format checks pass. Synthetic tests cover frozen historical signatures, scope/cache separation, legacy
both-cache reuse, fresh refresh identity, selected-sensor graph construction and
null unavailable areas, source inventory/terrain exclusion, incompatible flags,
review-case forwarding and controlled demo failures. These checks establish engine
isolation and provenance behavior, not satellite accuracy or live service success.
