# Optional paired optical review rendering

Prepared 17 October 2026 (Europe/Helsinki). Offline and synthetic browser validation
only. No additional live catalog, analysis or rendering request has been made.

Bright surfaces can exceed the fixed RGB maximum of 0.3. The saved PNGs have already
lost values at their display endpoints, so changing a saved PNG cannot restore that
reflectance. This option renders an additional view from prepared Earth Engine
reflectance. It does not change source selection, preprocessing, thresholds, patch
rules, scientific results, analysis keys or comparison IDs.

## Explicit request and isolation

`--optical-review-stretch` is off by default. `run` requires it together with
`--review-previews`; synthetic demo mode rejects it. `review-case` already requests
review previews and forwards the new option. The manual **Validation acceptance**
workflow exposes `optical_review_stretch=false` by default, for artifact-only frozen
imagery cases. Monitoring and scheduling have no new input.

The following is a proposed live command, **not an executed validation**:

```text
sentinel-monitor review-case --case gobabeb-quiet-reference --optical-review-stretch --imagery-diagnostics --results results-optical-shared-v1 --output site-optical-shared-v1
```

Use new results/output directories. The original pilot, fixed PNGs and browser reviews
remain at their existing paths. New live work still needs specific approval.

## One range shared by dates and colour bands

For each usable optical comparison, prepared baseline and target RGB reflectance
(B4/B3/B2) are restricted to the identical production common-valid mask. One bounded
fixed-grid reduction obtains counts, extrema, 5th/95th percentiles and support at the
fixed stretch endpoints. It uses 18 input bands, the existing CRS/transform, explicit
band-pixel budget and no best-effort coarsening. Percentiles use Earth Engine reducer
defaults; they may use its histogram approximation.

The deterministic policy `optical-shared-v1` sets:

- `lo = min(p05)` across the six baseline/target RGB band distributions.
- `hi = max(p95)` across those same distributions.
- One scalar `lo`/`hi` for every RGB band and both dates, with unchanged gamma 1.2.

This is an **envelope of per-view band quantiles**, not a pooled percentile. A scalar
mapping avoids independently rescaling each date or white-balancing each band. It
retains comparative colour/channel relationships under one mapping. Outlier tails
may still clip, and a wide range may leave subtle texture faint. Brightness cannot be
compared across cases because each pair has its own range. No new ground resolution,
object identification, count accuracy or recovered Gobabeb detail is established.

Both alternate dates are masked to the common cells used to select the range. The
orange overlay uses the unchanged connected-patch mask. The fixed originals retain
their existing display/masks and B4/B3/B2 0–0.3, gamma 1.2 settings.

## Assets, metadata and review context

Original `comparison.previews` and `assets/<comparison_id>/{before,after,overlay}.png`
keep their existing meaning. The additional triple is saved at
`assets/<comparison_id>/optical-review/{before,after,overlay}.png`. Alternate writes
never target original paths. All three downloads must be valid PNGs and all writes
must succeed before the triple is advertised. A failed write can leave unadvertised
alternate files; no partial triple becomes a review display.

`comparison.optical_review` records schema/policy versions, method, quantiles, scope,
common-cell count, six finite distributions, fixed endpoint support, actual applied
bounds/gamma/bands, status and alternate paths or a sanitized failure/unavailability
reason. Record and frozen-case manifests retain the requested flag. History/latest
JSON include rendering metadata and never include browser-local observations.

Isolated review reports keep fixed images and original links, add clearly named
shared baseline/target/overlay controls and static links accessible without JavaScript,
and explain range provenance. Fixed and alternate PNG endpoint checks are measured
separately, excluding transparent pixels and the orange overlay. A missing, invalid
or wholly transparent baseline/target makes the alternate check incomplete rather
than a negative endpoint finding. An endpoint notice means at least 95% of opaque
PNG pixels are at one channel endpoint; its absence is not proof of visible detail.

Switching displays within one record uses the existing eight-field comparison review
identity and does not alter notes or decisions. The review is of that paired comparison;
notes can identify which display supports the observation. A fresh analysis/render run
gets a fresh `generated_at`, so earlier records' reviews are not silently transferred.
No display-only augmentation of an old analysis timestamp is performed.

## Failure and cache behavior

Insufficient baseline days, zero common cells and insufficient common coverage skip
extra render work with explicit unavailable metadata. A finite, internally consistent
range of width at most 1e-12 is unavailable as degenerate; it is not amplified.

Missing/non-finite distributions, inconsistent counts/order/endpoint fractions,
statistics request errors, thumbnail/download errors, invalid PNGs and storage failures
are retryable **display errors**. Fixed previews and detector measurements remain
available. These errors do not enter scientific `location_status()` inputs; the record
has a partial error, the invocation returns 2, and `run-summary.json` lists
`optical_review_errors`. Bounded request retries and URL/token redaction still apply.

An old cache without this requested policy upgrades through normal fresh analysis,
not mutation under an old review timestamp. Cache reuse checks schema/policy/method,
scope, quantiles, stored finite statistics against the applied range/gamma/bands,
fixed clipping support, comparison-specific alternate paths and three locally valid
PNGs. Missing/corrupt files and incomplete/error metadata retry. Documented insufficient
or verified degenerate outcomes can be reused; malformed statistics cannot masquerade
as terminal unavailable evidence. `review-case` retains its existing explicit refresh.

The option adds one bounded reduction and three thumbnail creations/downloads per
usable optical comparison, on top of ordinary analysis and fixed previews. This is
additional EE compute/rendering, not an EECU estimate. No large ML stack is introduced.

## Offline evidence and exact next live proposal

[QA evidence](evidence/optical-review-rendering-2026-10-17.json) records real serialized EE
graph checks with synthetic service/image responses, original-output non-interference,
failure/cache checks and temporary-browser desktop/mobile verification. All review
observations used in QA are synthetic and remain in ignored local artifacts.

If separately approved after review/merge, dispatch **one** Validation acceptance run
on the specifically approved merged source SHA, with `check=imagery`,
`case_id=gobabeb-quiet-reference`, `imagery_diagnostics=true`,
`optical_review_stretch=true`. Its new job workspace retains a fresh record and both
triples as artifacts; it has no Pages deployment or results-branch write. Do not
reuse or rebuild the existing pilot. No dispatch or protected-main write is included
in this preparation.

Check the real applied range and clipping support, common-cell counts, source IDs,
unchanged detector outputs, both image triples and errors; inspect alternate detail
without claiming higher resolution or quiet ground truth. Compare original hashes to
the frozen source artifact where source acquisitions match, and record any discrepancy
rather than treating synthetic QA as proof of server rendering. This would validate
the new rendering path on one case; it would not certify construction/transport
accuracy, radar controls or representative EECU consumption.
