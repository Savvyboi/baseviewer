# Imagery source and comparison diagnostics

Implemented 17 October 2026. Offline verification and the single approved Gobabeb
real-source check passed. [Live evidence](evidence/gobabeb-diagnostics-2026-10-17.json)
retains the complete source record, provenance and publication checks.

The original Gobabeb artifact has no radar comparison and a clipped red display
channel. It cannot explain whether radar was absent from the catalog or excluded by
source filters. Park Fire also has an optical appearance difference with no qualifying
patch. These are separate unresolved scientific questions, not established detector
errors. This increment retains the measurements needed to investigate them without
changing production rules, reference labels or original previews.

## Request and outputs

`--imagery-diagnostics` is off by default on `run` and `review-case`. The manual
**Validation acceptance** workflow exposes an equally optional `imagery_diagnostics`
input. It affects only the selected isolated case. No scheduling or monitoring
workflow input was added.

When an approved investigation is ready, the local form is:

```text
sentinel-monitor review-case --case gobabeb-quiet-reference --imagery-diagnostics
```

This is a **new live analysis with extra compute**, not an offline reconstruction.
It was executed exactly once after specific approval for PR #16 and this diagnostic run.
A saved PNG cannot recover reflectance that its display stretch clipped.

The result record's `source_diagnostics` contains:

- Separate baseline/target counts of catalog granules intersecting the AOI and dates.
  Radar counts then follow the unchanged cumulative cascade: IW, contains VV, contains
  VH. Exclusion counts describe the first failed filter, not independent totals.
- At most ten source examples per excluded stage/window, sorted by source index,
  with IDs, acquisition days, mode, polarizations, platform and orbit/pass. Exact
  counts and explicit truncation flags accompany these examples. The six radar
  stage/window lists therefore retain at most sixty examples.
- Complete eligible source IDs, distinct baseline dates and target datatake counts
  per production orbit/pass group. `eligible_metadata_complete` becomes true only
  after the ordinary bounded source metadata request succeeds. Its configured
  source limit is unchanged. `metadata_eligible` means enough baseline dates to
  attempt a comparison; it does not certify pixel coverage or successful execution.

Counts are granules/slices, not independent observations or valid pixels. A source
footprint intersecting the AOI does not guarantee full coverage. Empty eligible
metadata stays empty and produces no fabricated radar negative. Baseline-only groups
and target groups with too few baseline days are retained explicitly.

Each evaluated comparison's `imagery_diagnostics` contains grid-cell counts for
prepared target validity, baseline eligibility (minimum daily observations per cell),
common validity, threshold crossings before patch filtering and surviving patch cells.
These describe combined production masks; they do not attribute rejection separately
to SCL, clouds, terrain, incidence angle or backscatter. A metadata-insufficient
comparison instead saves `not_evaluated_reason` without inventing pixel measurements.

Optical comparisons with common valid cells also retain B2/B3/B4/B8 baseline and
target reflectance distributions (count, mean, min/max, p5/median/p95), the production
mean absolute four-band difference distribution and RGB fractions at/beyond the fixed
stretch endpoints. Percentiles use Earth Engine reducer defaults and are not uncertainty estimates.
These are **prepared reflectance on common valid cells**, not raw
unmasked source radiometry or whole-scene statistics. Endpoint fractions refer to
analysis cells, not resized/quantized PNG pixels. The stretch remains B4/B3/B2,
0-0.3, gamma 1.2. Zero common cells skip optical distributions with an explicit reason.

Insufficient-coverage comparisons may have diagnostic threshold/patch counts on their
valid subset. Their scientific status remains insufficient, they receive no previews,
and these subset counts are not accepted change detections. The existing signed radar
diagnostics remain separately controlled by `--radar-diagnostics`.

Outputs persist in the ordinary record and isolated report's history/latest JSON.
No review observations are read or included. This phase does not alter the review UI.

## Request bounds and failure handling

The option adds one bounded metadata request per sensor. Each comparison with enough
baseline metadata adds one request containing a three-band mask sum and, for optical
comparisons with common cells, a 21-band distribution reduction. These use the same
fixed CRS/transform and explicit band-pixel budget; no best-effort coarsening is used.
Existing bounded request retries apply. Request counts are not EECU estimates.

A diagnostic failure is sanitized, saved beside available measurements and added to
the record's partial errors. Usable detections and preview generation continue. The
CLI returns exit code 2, and the next invocation retries instead of silently reusing
incomplete evidence. Enabling the option upgrades older cached records with the same
science key; it does not change detection identity, thresholds, masks or preprocessing.

## Verification and next bounded science check

Offline tests serialize real EE graphs with synthetic service responses. They check
exact non-interference with the ordinary comparison graph and output, bounded source
examples, grouping/datatakes, empty and unmatched radar sources, insufficient coverage,
zero common cells, diagnostic failures, cache upgrade/retry and JSON persistence.
These tests establish client construction and handling; they do not establish EE
server execution, imagery accuracy, a radar quiet control or corrected display detail.

The [single approved Gobabeb run](https://github.com/Savvyboi/baseviewer/actions/runs/39046789742)
passed on merged main at `30f4c79d174e51db08a7fd4d9bc553d359f72e5c` with unchanged
frozen AOI/dates/settings. Both sensor source inventories and the optical comparison
diagnostics completed without errors. The artifact digest matches the downloaded ZIP.
The original science comparison and all three PNGs are identical to the prior run.
The existing civilian pilot was preserved with its original record identities.

Radar has zero AOI-intersecting `COPERNICUS/S1_GRD` granules in both baseline and target
windows, before IW/VV/VH filtering. No filter rejected any source. This identifies a
catalog-availability gap for the exact collection/AOI/windows; it does not explain
acquisition policy or establish any radar negative. Gobabeb cannot supply the missing
radar quiet control for these dates.

Optical has 400/400 target, baseline-eligible and common valid cells, zero raw threshold
crossings and zero patch survivors. Mean absolute four-band difference ranges from
0.000675 to 0.006025 (mean 0.002947125), below the unchanged strict >0.10 threshold.
All red-band cells exceed the fixed 0.3 display ceiling in both views: baseline B4
0.3226-0.3394 and target B4 0.3220-0.3392. This confirms clipping by the preview stretch;
the measured reflectance is not capped at 0.3. It does not restore the lost display
detail or independently certify every AOI cell as quiet.

The public HTML, latest/history JSON and three public PNG hashes match before/after;
the results ref is unchanged and `MONITOR_ENABLED` remains unset. Runtime 5.699 seconds
is wall time, not EECU usage. No deployment or results-branch write occurred.

The next useful increments are an optional optical review stretch shared across
baseline/target (retaining originals and detector rules), then a civilian radar
quiet/change pair selected from independent dated evidence with eligible matching
sources. Freeze AOIs/windows before detector output, and evaluate validity before
interpreting changes. Prepare code and offline verification first; new live runs or
protected-main merges still need specific approval. No further run is prepared or
approved by the completed Gobabeb invocation alone.

API context: [Sentinel-1 metadata and filtering](https://developers.google.com/earth-engine/guides/sentinel1),
[fixed-grid reductions](https://developers.google.com/earth-engine/apidocs/ee-image-reduceregion),
[visualization parameters](https://developers.google.com/earth-engine/apidocs/ee-image-visualize).
