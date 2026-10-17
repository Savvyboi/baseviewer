# Private offline review assessment

`sentinel-monitor assess-reviews` joins a local schema-1 review export to an
immutable original report history. It reads local files only and creates an HTML
report plus a JSON assessment in a new ignored private directory. It never reads
browser storage, calls Earth Engine, changes source records, or builds a public site.

```text
sentinel-monitor assess-reviews --history /local/original-report/history.json --reviews /local/review-export.json --private-workspace /local/repository
```

The original report's sibling `assets` directory is used by default. Pass
`--asset-root /local/original-assets` only when the immutable original PNGs were
retained separately. Preview paths must start with `assets/` and resolve inside
that local asset root; URLs, traversal and escaping links are rejected. Missing or
unreadable files stay visible as unavailable previews rather than disappearing
from the science denominator.

Outputs always go under
`.preview-output/private-review-assessment/assessment-<random-id>/` in the chosen
Git checkout. Both actual final and temporary file paths must be ignored by Git.
Redirecting the private directory through a symlink/junction is rejected. There
is no arbitrary `--output`, public-export option, or workflow upload integration.
The command prints a generic success/failure message without identities, choices,
notes, timestamps, hashes, matched counts or aggregate results. Open the new local
`report.html` directly; `assessment.json` contains the same private data and receipt.
Each run uses a new directory and preserves previous reports and source inputs.

These outputs contain actual observations and derived private summaries. Keep them
local. Git ignore and destination restrictions prevent ordinary accidental staging;
they do not prevent someone from manually copying a report or forcing an upload.
Only synthetic fixtures, evaluator code and methodology belong in commits, public
validation evidence, CI artifacts or pull request descriptions. A public status
may say that a private assessment was produced, without its findings or counts.

## Identity and validation

Every match uses the original strings in all eight identity fields:

| Export field | Source history field |
| --- | --- |
| `mode` | `record.mode` |
| `case_id` | `record.validation_case.id` |
| `site_id` | `record.site.id` |
| `analysis_key` | `record.analysis_key` |
| `comparison_id` | `comparison.id` |
| `record_generated_at` | `record.generated_at` |
| `acquisition_date` | `comparison.acquisition_date` |
| `sensor` | `comparison.sensor` |

Object key order does not matter. Timestamp spelling remains part of identity,
even if two strings represent the same instant. When only the record timestamp
differs, the export row is classified as stale; other unmatched identities are
out of report. Neither transfers into a source row. Refreshed diagnostic records
remain distinct even when their measurements and comparison IDs are unchanged.
If both generations are intentionally supplied, they remain separate science rows.
Use the original history for assessment of an original reviewed report.

All source records and export entries are validated before output creation.
Duplicate JSON keys, duplicate source/review identities, unsupported schemas,
malformed identity/date/time values, invalid choices, nonfinite numbers and invalid
Unicode reject the whole operation. Export limits match the browser's 2 MiB,
5,000 entries and 2,000 UTF-16 note units. Unlike the permissive browser importer,
the evaluator requires supported modes/sensors, nonblank identifiers and ISO dates
and timestamps with explicit timezone information. Empty case IDs are allowed for
history without a validation case, but such rows have no review controls.

Science provenance requires saved settings, site, metric grid, UTC windows and
analysis version. Coverage lies in [0,1]; common/changed cells are consistent with
the grid and integral cell counts. Usable comparisons require sufficient metadata
baseline days, qualifying patch size and consistent detector status. Area gets a
broad sanity check of 50–200 m² per changed cell, allowing projected/geodesic area
variation; this does not recompute area or define a detection threshold. Record
status must agree with comparisons and saved errors. Legacy insufficient/error
comparisons may omit changed-cell measurements and retain an unevaluated zero area.
Their status governs interpretation; the zero is never scored as a negative.

## Denominators and interpretation

The denominator is **every comparison in the supplied science history**, including
insufficient data, errors, detector negatives and usable rows awaiting previews.
The export alone is not a denominator: the browser only exports comparisons with
usable status and complete preview paths in reports with review controls.

The report preserves detector status, science values, preview availability,
human-visible appearance and frozen reference context separately. It reports:

- All science rows, usable rows, insufficient rows and errors.
- Review-eligible rows, eligible unreviewed backlog, and usable rows awaiting previews.
- Decisive appearance observations (`reviewed`), inconclusive `unclear` observations,
  and `reviewed_including_unclear` coverage. `unreviewed` includes unavailable science
  rows; use `eligible_unreviewed` for the eligible backlog. A note alone is unreviewed.
- Exact matches, stale/out-of-report entries, and entries matching source rows without
  review controls. Excluded observations do not affect science-row totals.
- Absent sensors and record-level errors separately; an absent sensor is no comparison,
  never a fabricated negative.

Detector × appearance tables describe this retained set only. The command does not
compute accuracy, false-positive rates or confusion matrices. Human observations
are not independently adjudicated labels. Frozen references are preserved but never
promoted to full-AOI or sensor-specific truth. No threshold calibration or model
training follows from the assessment.

Optical RGB omits the NIR detector band, while radar VV imagery omits triggering VH.
Display stretch, clipping, grid spacing versus resolution, masking and baseline
composition can limit appearance judgments. Schema 1 has no display-variant field
or render receipt: hashes identify the retained PNGs read during assessment, without
proving what a person previously saw. Old observations must not be described as
review of a different stretch. Source history, settings/grid, PNG hashes, export
hashes and all review-derived receipts remain in the private report only.

## Small next evaluation and compute gates

The current convenience set cannot establish representative thresholds,
false-positive rates or quiet/change radar accuracy. Further work should follow
these gates with unchanged settings and civilian examples:

| Gate | Offline preparation and evidence needed | Proceed only when |
| --- | --- | --- |
| Independent reference | Freeze a small set of dated construction/change and plausible quiet AOIs/windows before inspecting detector output. Document full-AOI spatial/temporal support, sensor relevance, exclusions and selection provenance. Point optical stability or a pre-event date cannot certify radar/whole-AOI quietness. | References support the proposed claim; uncertainty and unsupported cells remain explicit. |
| Comparability | Record source/orbit/platform, land cover, AOI/grid size, baseline/target dates, coverage expectations and likely display limits. Retain insufficient and missing-sensor cases. | Cases can answer a bounded feasibility question without implying representative sampling. |
| Specific live approval | Prepare exact frozen case hashes, ref, artifact-only workflow inputs, source/preview/diagnostic requests, retry limits and workload tags. | The human approves that exact new request. Offline preparation is not dispatch approval. |
| Independent adjudication | Preserve original render identities. Keep appearance review separate from independently sourced reference truth, with unresolved cases left unclear/unlabeled. | A reference supports each scored spatial/temporal unit and sensor. |
| Compute measurement | Obtain measured EECU usage by workload tag, including both sensors, baselines, summaries, previews, diagnostics, retries and failures. Record context and uncertainty for extrapolation. | Measured compute supports a stated bounded next stage; elapsed seconds are not EECU. |
| Expansion/publication | Retain the separate failed-analysis publication acceptance gate and manual deployment review. | Specific approval covers a main merge, deployment or schedule/site expansion. |

No benchmark, new live request, deployment or schedule expansion is performed by
this command or authorized by this plan. See [validation status](validation.md)
and [human review](human-review.md) for the retained science limitations.
