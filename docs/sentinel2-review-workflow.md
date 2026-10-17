# Sentinel-2 human review workflow

Updated 18 October 2026 (Europe/Helsinki).

The bounded pilot uses Sentinel-2 imagery as a human review feed. Automated
`possible_change` and `no_change_detected` are screening results. Neither result
certifies visible surface change, a quiet site, a cause, object identity or vehicle
counts. Human appearance observations remain observations, not certified ground
truth. Statistical calibration is future evaluation work, not a prerequisite for
trying this bounded review workflow.

## Review an acquisition

1. Check the requested sensor scope and target/baseline windows. Start with the
   baseline and target images, source acquisition days, common valid coverage,
   cloud/mask context, resolution and display notices. The 28-day baseline is a
   composite, not a single photograph. The RGB source bands have 10 m resolution;
   an enlarged PNG adds no detail.
2. Compare the original baseline/target PNGs. If a shared optical range is present,
   its fixed paired mapping is an additional display option, with its own limits.
   RGB appearance omits NIR from the four-band screening signal. Use the overlay
   as a cue rather than a determination. Source IDs and unchanged thresholds
   remain in analysis details and downloadable history JSON.
3. Review every usable acquisition, including `no_change_detected`. Choose likely
   visible change, no obvious visible change, or unclear, and describe observable
   appearance and uncertainty. A note alone leaves the comparison unreviewed.
4. Keep insufficient-data comparisons and errors in check history. Usable rows
   with missing/unreadable original PNGs stay **Awaiting previews**, have no review
   controls and are excluded from export until their previews are available.
   Other available original images and the science measurements remain visible.
   None of these availability gaps becomes a negative observation.
5. Export notes to keep a local copy. Restore fills only empty entries matching
   the exact eight-field identity. Existing choices, notes and resets remain.
   Browser storage can fail; page-state export remains available. No review
   service or network write is involved. Keep actual reviews and every derived
   assessment private, outside commits, uploads and public evidence.

## Sensor scope contract

The sensor-selection engine increment supplies `--sensors {both,optical,radar}`
(default `both`) on `run` and `review-case`, and a manual validation input. This
report increment consumes its canonical `requested_sensors` record field:

| Record field | Requested scope | Missing comparisons |
| --- | --- | --- |
| `["optical"]` | Optical only | Missing optical is a gap; radar is not requested |
| `["radar"]` | Radar only | Missing radar is a gap; optical is not requested |
| `["optical", "radar"]` | Both | Either missing sensor is a gap |
| Field absent | Both, for legacy compatibility | Either missing sensor is a gap |

The report displays requested/usable scope separately. A sensor that was not
requested and cross-sensor overlap that was not requested are labelled accordingly,
never as a failure, zero area, or detector negative. The private assessment's
`absent_sensors` means requested sensors with no comparisons; intentional omissions
appear separately as `not_requested_sensors`. Every existing science comparison,
including insufficient data/errors, remains in assessment denominators. Malformed
scope or a comparison outside declared scope is rejected rather than reclassified.

Retained historical records without the field stay historically **both**. Rebuilding
HTML never rewrites them or adds scope to their downloaded source JSON. An optical-only
engine run must use a distinct science identity/cache. Review identity remains mode,
case, site, science key, comparison ID, record-generation timestamp, acquisition date
and sensor. Switching displays within one record preserves observations. A refreshed
record gets a fresh timestamp and cannot inherit older notes, even with the same
acquisition or science key. Do not relabel retained records or migrate reviews.

## Evaluation and remaining gates

Review readiness means images and their source/coverage/display limits can be
inspected, all usable negatives stay available, missing data stay visible, and local
observations can be kept without changing science. It does not establish accuracy,
false-positive rates, count accuracy or representative construction/transport
performance. Formal evaluation later needs independent adjudicated reference truth,
representative examples and explicit denominators. No threshold is tuned to these
examples, and no new ML stack or radar benchmark is required for this optical pilot.

This change is offline code plus synthetic QA. It requests no imagery, catalog,
Earth Engine computation or new source rendering. Live compute/render requests,
protected-main merge, deployment and monitoring expansion retain their separate
approval gates. Production defaults, active sites and schedules are unchanged.
The coordinator's separate retained optical bundle can use this renderer without
changing the old pilot, original PNGs or historical record identities.

## Reproduce synthetic QA

From this worktree, with its `src` on `PYTHONPATH`, run:

```text
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python tests/test_sentinel2_review.py .preview-output/sentinel2-workflow-qa
node tests/sentinel2-review.browser.cjs .preview-output/sentinel2-workflow-qa
```

The browser runner needs Playwright (`PLAYWRIGHT_MODULE` can identify an installed
module) and Chromium/Chrome (`CHROMIUM_EXECUTABLE` can identify an installed binary).
It serves only generated synthetic files on a temporary loopback port and uses fresh
headless contexts, never the user's browser/storage or pilot server. Disposable
screenshots and the synthetic check receipt stay under ignored `.preview-output`.

Verification: 219 offline tests and nine subtests passed, as did lint/format checks.
Synthetic desktop/mobile/no-JavaScript and keyboard checks passed; screenshots were
visually inspected. Browser checks verified detector-negative queue inclusion,
awaiting previews, intentional sensor omission versus legacy missing radar, exact
eight-field export/restore, unchanged notes/timestamps across image switching,
refreshed-record exclusion, blocked-storage export, and no network writes. A bounded
Luna copy audit found no actionable wording issue; browser behavior was checked by
the primary implementer. No actual reviews or private assessments were accessed.
