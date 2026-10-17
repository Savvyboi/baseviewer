# Imagery source and comparison diagnostics

Prepared 17 October 2026. Offline verification is complete; real-source execution of
these new diagnostics has not been approved or performed.

The existing Gobabeb artifact has no radar comparison and a clipped red display
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
The command is documented for preparation and was not executed for this change.
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

The prepared next live check is exactly one Gobabeb diagnostic invocation with the
existing frozen AOI/dates/settings and `imagery_diagnostics=true`. It addresses both
the missing-radar inventory and bright-surface display question in the same small case.
Before dispatch it needs approval for the new protected-main merge and new live analysis.
Its artifact-only workflow has no Pages deployment or results-branch write.

After an approved run, retain source counts/exclusions and inspect actual eligibility
before selecting a further radar reference. If no dual-polarization IW target survives,
report that source-filter result; do not relax filters to make a negative. If sources
survive, inspect orbit/baseline eligibility and validity before interpreting changes.
Use optical distributions to assess endpoint clipping without fitting detector
thresholds to this surface. A transport/construction radar control still requires
independent evidence; this desert optical reference cannot establish one by itself.

API context: [Sentinel-1 metadata and filtering](https://developers.google.com/earth-engine/guides/sentinel1),
[fixed-grid reductions](https://developers.google.com/earth-engine/apidocs/ee-image-reduceregion),
[visualization parameters](https://developers.google.com/earth-engine/apidocs/ee-image-visualize).
