# Validation status

Recorded 16 October 2026 (Europe/Helsinki).

The published one-site prototype and its analysis/publication plumbing work. It remains an experimental detector: reliable ground-change discrimination, representative EECU consumption and the real failed-analysis deployment path are still unproven. The Park Fire review below adds a concrete optical appearance/detection discrepancy; it does not establish product readiness.

## Verified

- 58 offline checks pass, including UTC windows, metric grids, sensor/orbit isolation, coverage rules, saved history, error diagnostics, reduction limits, optional radar diagnostics, validation fixture construction, isolated imagery cases, review-preview caching and controlled HTTP publication bundles.
- The [initial one-site live run](https://github.com/Savvyboi/baseviewer/actions/runs/38824576055) passed for Engels air base, with exclusive end date `2026-10-12` and publishing disabled.
- Workload Identity Federation and the monitoring service account performed server-side comparisons and created PNG previews after the thumbnail-creation permission was granted.
- The [first Pages deployment](https://github.com/Savvyboi/baseviewer/actions/runs/38825866484) passed. The [public prototype](https://savvyboi.github.io/baseviewer/) and all three PNG previews plus both JSON links returned HTTP 200. Publication reused the completed live record without requesting an analysis refresh.
- Three additional historical weeks passed on main at `31766607b32ecdd58fa43db82a0ab98b19c025fb`. Their deployment jobs were skipped; the public homepage was not replaced.
- The results branch holds four distinct site/window records and 24 valid 400 x 400 PNGs. Repeated refreshes replace a matching record without duplicating it. File paths, source acquisitions, workload tags and PNG SHA-256 hashes are preserved in [the evidence manifest](evidence/engels-2026-10-16.json), pinned to results commit `375fbf91cacacfd663b630063acc090a347298e8`.

## Historical imagery investigation

The same 2 km tile uses `EPSG:32638` and a fixed 10 m grid. All live runs used the original settings, including radar VV or VH difference greater than 3 dB and at least nine connected cells. Each radar comparison had exactly two baseline acquisition days. All source IDs in these five radar comparisons identify Sentinel-1D; these examples therefore do not indicate cross-platform mixing.

| Week ending (exclusive UTC) | Radar acquisition | Descending relative orbit | Common valid coverage | Flagged area | Valid cells flagged |
| --- | --- | --- | --- | --- | --- |
| [2026-09-21](https://github.com/Savvyboi/baseviewer/actions/runs/38828228902) | 2026-09-14 | 152 | 94.5% | 2.496 km² | 66.0% |
| 2026-09-21 | 2026-09-19 | 50 | 91.1% | 2.299 km² | 63.0% |
| [2026-09-28](https://github.com/Savvyboi/baseviewer/actions/runs/38828608011) | 2026-09-26 | 152 | 96.4% | 0.760 km² | 19.7% |
| [2026-10-05](https://github.com/Savvyboi/baseviewer/actions/runs/38828234456) | 2026-10-01 | 50 | 91.3% | 2.616 km² | 71.6% |
| [2026-10-12](https://github.com/Savvyboi/baseviewer/actions/runs/38824576055) | 2026-10-08 | 152 | 88.5% | 2.969 km² | 83.8% |

Before, after and overlay PNGs for all five radar comparisons were visually reviewed. Several overlays cover broad portions of the tile; the September 26 response is more scattered. The large October 8 response is therefore not an isolated result. These are signal differences, not established ground changes or inferred causes. No radar quiet control was established.

Optical results across the four weeks comprise three candidates (approximately 3,902 m² on September 20, 6,004 m² on September 23 and 1,601 m² on September 27), two usable comparisons without threshold crossings, and nine insufficient-data comparisons. The September 20 candidate's RGB previews were visually reviewed; much of the tile looks similar, with a small qualifying patch. This is not independent confirmation of change. A detector-negative comparison is not sufficient evidence to label a whole week quiet.

Radar previews display VV only, although either VV or VH can trigger a candidate. Live diagnostics now establish signed shifts and polarization support; the imagery and diagnostics still cannot distinguish environmental variation from processing artefacts or establish a cause. The baseline contains only two daily observations. Earth Engine documents its [Sentinel-1 preprocessing and heterogeneous collection](https://developers.google.com/earth-engine/guides/sentinel1); matching orbit/pass alone does not establish scientific accuracy.

## Optional radar diagnostics

`sentinel-monitor run --radar-diagnostics --end-date 2026-10-12 --results results-validation --output site-validation` requests an additional bounded Earth Engine reduction for each radar comparison with common valid cells.

The diagnostic JSON records VV and VH separately: baseline and target backscatter distributions, signed target-minus-baseline differences, daily baseline range, fractions above +3 dB and below −3 dB, baseline-range exceedance, and fractions crossing the threshold in either/both polarizations. All use common valid cells before connected-patch filtering. Mean and percentile summaries describe the signal; they are not confidence estimates. Percentiles use Earth Engine reducer defaults.

The flag is off by default, is available as a manual workflow input and adds compute when selected. It does not change thresholds, masks, statuses or science keys. Requesting diagnostics upgrades an older completed record instead of silently reusing one without diagnostics. Diagnostic request failures retain usable detections, surface a partial error and are retried by a later run. Synthetic mode rejects this flag.

**Live execution verified:** after PR #5 merged, all four reviewed weeks passed with diagnostics enabled and publishing disabled on main at `6168b3ab03ca9ed1838af669fd3daf43c5a7875a`. Deployment was skipped in each run: [October 12](https://github.com/Savvyboi/baseviewer/actions/runs/38829562558), [September 21](https://github.com/Savvyboi/baseviewer/actions/runs/38829697283), [September 28](https://github.com/Savvyboi/baseviewer/actions/runs/38829818257), [October 5](https://github.com/Savvyboi/baseviewer/actions/runs/38829949827).

The [diagnostic evidence](evidence/radar-diagnostics-2026-10-16.json) pins results commit `8714435fea8b875f960d396f0b43d79f7545e22c`, including complete per-band distributions and run metadata. All 19 previous comparison statuses, coverage values, changed-cell counts, areas and source lists remained identical; all 24 PNG SHA-256 hashes also matched. Four distinct site/window records remain. Diagnostic counts match common valid cell counts.

| Radar date | Orbit | Median VV delta | Median VH delta | Raw either-band threshold support | Baseline range >3 dB, VV / VH |
| --- | --- | --- | --- | --- | --- |
| 2026-09-14 | 152 | +2.31 dB | +3.31 dB | 67.1% | 14.9% / 23.8% |
| 2026-09-19 | 50 | −2.19 dB | −2.94 dB | 64.1% | 49.9% / 66.2% |
| 2026-09-26 | 152 | −0.81 dB | −0.94 dB | 23.6% | 39.9% / 53.2% |
| 2026-10-01 | 50 | −2.69 dB | −3.56 dB | 72.4% | 57.5% / 70.7% |
| 2026-10-08 | 152 | −4.07 dB | −5.94 dB | 84.3% | 23.8% / 32.3% |

Signed delta is target minus the existing power-median baseline, expressed in dB after the production speckle averaging. Fractions use common valid cells before patch filtering, so raw threshold support can exceed the final flagged-cell fraction. On October 8, 65.2% of valid VV cells and 77.7% of valid VH cells decreased by more than 3 dB; 59.4% crossed the absolute threshold in both bands. The widespread response is therefore not attributable solely to an unseen VH band. The positive September 14 shift and later negative shifts demonstrate variability across this sample, without identifying its cause.

Several baselines themselves have extensive >3 dB ranges between their two dates (up to 70.7% of valid VH cells in the October 1 comparison). That makes independent quiet/control-area review essential. These measurements characterize the starting detector; they do not establish ground-truth change, justify a new threshold or validate detection accuracy.

## Controlled failure acceptance

`tests/test_publication_acceptance.py` drives the real CLI, persistence and report builder with controlled service outcomes, then serves the generated bundle over local HTTP:

- A usable negative optical result plus a radar error yields location `error`, not an all-clear.
- A candidate plus a radar error preserves the candidate and displays the partial failure.
- A failed preview preserves the candidate measurements and displays an unavailable-preview message.
- HTML, latest/history JSON and every referenced PNG remain accessible and consistent with those outcomes.
- Failed records retry without `--refresh`; successful recovery replaces the matching record, preserves the earlier week and is subsequently cached.

These checks use mocked Earth Engine responses and synthetic test PNGs. They verify local publication bundles and exit code 2 for partial failures. The optional diagnostic table and failure messages were also visually checked in Chrome at 1280 px and 390 px widths; neither layout overflowed the page. The isolated [GitHub acceptance run](https://github.com/Savvyboi/baseviewer/actions/runs/38830785030) passed both sensor-error and preview-error jobs on PR #6. Each observed CLI exit code 2 and a failed analysis step, verified the labelled demo/error record, then uploaded both an ordinary report and a Pages tar artifact. All four artifacts were downloaded and inspected: HTML and JSON retained the demo label, candidate status and error details; each contained all three referenced valid 400 x 400 PNGs (12 verified packaged copies total). [Artifact IDs, hashes and job outcomes](evidence/failure-artifacts-2026-10-16.json) are saved with the source commit. No deployment ran. A controlled failed analysis through the real Pages deploy job remains pending; no synthetic failure was published over the live report.

The [manual failure-artifacts run](https://github.com/Savvyboi/baseviewer/actions/runs/38831934553) also completed exactly as intended after merge: both uploads and the expected-failure verification succeeded, then each matrix job failed at `Surface the controlled failure after artifact upload`. GitHub normalizes the earlier continued-error analysis step's conclusion to success; its `outcome` and exit code 2 were checked by the next step. All four artifacts and 12 packaged PNG copies were downloaded and verified again. [Manual run evidence](evidence/manual-failure-artifacts-2026-10-16.json) includes step conclusions, artifact IDs and hashes. The overall failure is deliberate acceptance behavior, not a broken analysis run. This still does not exercise the real Pages deploy job.

## Live numeric validation harness

`sentinel-monitor validate-live --project baseviewer-511722` evaluates 12 tiny, constant-raster cases on Earth Engine through the production comparison method. Each sensor checks unchanged inputs, a nine-cell square, a single cell that must be removed, a nine-cell diagonal requiring eight-neighbour connectivity, a wholly masked target and only one valid baseline day per pixel despite two metadata dates. The radar unchanged/patch cases also check known signed means, band identities, valid counts and polarization threshold fractions.

The 100 m fixture is 100 cells, with explicit masks and no satellite imagery or preview requests. Output records expected/observed results, individual failures, a unique workload tag and UTC request bounds. A failed check returns exit code 2 and retains the evidence file. This is a server numeric acceptance check, not a quiet/known-change imagery example, preprocessing validation or a compute benchmark.

The new **Validation acceptance** workflow runs synthetic sensor/preview failure packaging on PRs, with no Google authentication or deployment permissions. Both reports carry the demo banner. Its manual `failure-artifacts` option deliberately ends failed after uploading evidence; the PR version succeeds only when the expected CLI failure and error report are observed. Artifact names are separate from the production Pages artifact. The manual `numeric` option runs only on main using the existing Google federation.

**Numeric server execution passed:** all 12 checks succeeded in the [manual main-branch run](https://github.com/Savvyboi/baseviewer/actions/runs/38831920252) at `18fdc7e5ba822ce5c28d10b2db08a044f39ef2cf`. The downloaded [numeric evidence](evidence/numeric-checks-2026-10-16.json) retains every expected/observed result, source commit, artifact hashes, UTC request bounds and workload tag `sentinel-numeric-992b46725b124a99`.

Both sensors reported zero changed cells for identical inputs and one-cell candidates, exactly nine changed cells for square and diagonal patches, and zero common valid coverage with `insufficient_data` for a wholly masked target or only one valid baseline image. The known VV/VH diagnostic values also matched. This validates those comparison calculations on EE servers; the fixture bypasses satellite preprocessing, so it does not validate cloud/terrain masks, speckle behavior or detection accuracy. The approximately five-second interval is wall time, not EECU consumption.

## Independent examples and quiet controls

Two public event cases have dated primary evidence and are shortlisted for later validation, without changing the active site list:

| Case | Proposed target / baseline (UTC, end-exclusive) | Independent evidence | Remaining acceptance work |
| --- | --- | --- | --- |
| Valencia flooding, Spain | Target [2024-10-28, 2024-11-04); baseline [2024-09-30, 2024-10-28) | [NASA Landsat observation on October 30](https://science.nasa.gov/earth/earth-observatory/valencia-floods-153533/) and [ESA/LIST October 31 inundation map with October 19 reference](https://www.esa.int/ESA_Multimedia/Images/2024/11/Sentinel-1_derived_map_of_flood_affected_urban_area_-_Valencia_Spain) | Choose a small AOI intersecting a mapped flood polygon and a nearby dry control; check actual Sentinel source coverage and radar orbit matches. The optical land-only mask may exclude inundated pixels, so insufficient coverage must not be scored as a negative detection. |
| Park Fire, California | Target [2024-07-22, 2024-07-29); baseline [2024-06-24, 2024-07-22) | [NASA's dated July 27 Landsat images](https://science.nasa.gov/earth/earth-observatory/after-the-park-fires-rapid-growth-153122/) | Select a burn-interior AOI and an unburned control from an independent perimeter; inspect smoke, clouds, slope screening and actual source dates. |

The Park Fire pair is now frozen in [validation/cases.json](../validation/cases.json): a 1 km square at CAL FIRE's published reference coordinate, with event week ending July 29 and pre-event week ending July 22, 2024. [CAL FIRE](https://www.fire.ca.gov/incidents/2024/7/24/park-fire/) supplies the reference point and July 24 start; [USGS](https://www.usgs.gov/media/images/landsat-images-park-fire-july-2024) supplies independent dated regional imagery. This selects a reference AOI, not a verified burn-interior polygon. No detector result was used to choose the square. Both labels remain `unreviewed`; the pre-event period is not yet a quiet control.

`sentinel-monitor review-case --case park-fire-event` (or `park-fire-pre-event`) runs one selected case with the unchanged production settings. It saves results and an imagery-review report under separate `results-imagery-review/<case>/` and `site-imagery-review/<case>/` directories, records the frozen inputs/hash and UTC invocation bounds, and requests diagnostics plus previews for every usable comparison. A detector-negative observation therefore has before/after imagery available for inspection. Insufficient-data comparisons still do not generate previews or become negatives. Review flags change presentation/asset requests, not scientific keys or detection rules.

The validation workflow's manual `imagery` option selects exactly one frozen case, uploads an ordinary report artifact and has no deployment job or results-branch write permission. Active `sites.yaml` and `max_sites: 1` are unchanged. Both frozen cases have now executed successfully on main; the review below records a detector/appearance discrepancy and insufficient radar coverage, not accuracy acceptance.

These are candidate validation designs, not completed accuracy checks. Freeze AOIs and labels from independent evidence before examining detector outputs. Include a pre-event week at each AOI and nearby control areas, visually review both dates, and record review provenance and exclusions. Absence of a reported event alone does not establish a quiet control. No event attribution is assigned to Engels candidates.

## Park Fire live imagery review

The [event run](https://github.com/Savvyboi/baseviewer/actions/runs/38834470348) and subsequent [pre-event run](https://github.com/Savvyboi/baseviewer/actions/runs/38834575557) both passed on main at `28b03299b021d7d00a5789b346a6dab8dc536095`. They ran serially with unchanged production settings and the frozen manifest SHA-256 `64dead7deff02af7751ec9680b7f9764b78410bc8cad83569ede2b76b334db37`. Neither workflow deployed or wrote the results branch. [The evidence manifest](evidence/park-fire-imagery-2026-10-16.json) retains run/artifact IDs, archive and individual file hashes, complete source acquisitions, settings, UTC invocation bounds, signed radar diagnostics and visual observations. All nine original 400 x 400 PNGs are retained under [the review image directory](evidence/park-fire-2026-10-16/).

| Case / target acquisition | Sensor / orbit | Baseline days | Common valid coverage | Production result |
| --- | --- | --- | --- | --- |
| Pre-event / July 17 | Optical | 6 | 100.00% | No change detected; 0 qualifying cells |
| Pre-event / July 16 | Radar / 115 descending | 2 | 59.10% | Insufficient data: below 70% coverage |
| Pre-event / July 18 | Radar / 137 ascending | 1 | Not evaluated | Insufficient data: fewer than 2 baseline days |
| Event / July 22 | Optical | 5 | 100.00% | No change detected; 0 qualifying cells |
| Event / July 27 | Optical | 5 | 97.00% | No change detected; 0 qualifying cells |
| Event / July 23 | Radar / 35 ascending | 1 | Not evaluated | Insufficient data: fewer than 2 baseline days |
| Event / July 23 | Radar / 42 descending | 2 | 59.78% | Insufficient data: below 70% coverage |
| Event / July 28 | Radar / 115 descending | 2 | 59.01% | Insufficient data: below 70% coverage |

The optical baseline dates are June 17, June 22, June 27, July 2, July 7 and July 12 for the pre-event case, and June 27, July 2, July 7, July 12 and July 17 for the event case. Each optical acquisition mosaics the two intersecting T10TEK/T10TFK granules rather than counting them as two dates. All radar source IDs identify Sentinel-1A. The records have no service or preview errors and only optical is usable; each location-level `no_change_detected` status therefore has no usable radar corroboration.

Codex visually inspected every original before/after/overlay PNG. This is an agent review of appearance and saved metadata, not a blinded independent analyst or ground-truth certification:

| Optical target | Original previews | Visual finding |
| --- | --- | --- |
| July 17, pre-event | [Before](evidence/park-fire-2026-10-16/park-fire-pre-event/0c40a43ee8516db782feae0e/before.png), [after](evidence/park-fire-2026-10-16/park-fire-pre-event/0c40a43ee8516db782feae0e/after.png), [overlay](evidence/park-fire-2026-10-16/park-fire-pre-event/0c40a43ee8516db782feae0e/overlay.png) | Broadly similar terrain/vegetation appearance at preview resolution; no obvious broad transition. |
| July 22, event window but before fire start | [Before](evidence/park-fire-2026-10-16/park-fire-event/349d9d5ee826baddb31343c3/before.png), [after](evidence/park-fire-2026-10-16/park-fire-event/349d9d5ee826baddb31343c3/after.png), [overlay](evidence/park-fire-2026-10-16/park-fire-event/349d9d5ee826baddb31343c3/overlay.png) | Broadly similar to baseline; this observation cannot test post-fire detection. |
| July 27, after fire start | [Before](evidence/park-fire-2026-10-16/park-fire-event/7164b43ecfd490262dcc76ad/before.png), [after](evidence/park-fire-2026-10-16/park-fire-event/7164b43ecfd490262dcc76ad/after.png), [overlay](evidence/park-fire-2026-10-16/park-fire-event/7164b43ecfd490262dcc76ad/overlay.png) | Broad north/west darkening and a reddish roughly north-south boundary-like feature; southeast remains relatively tan. Zero qualifying cells despite the visible appearance difference. |

All three overlays are byte-identical to their target PNG, consistent with zero detections. The July 27 target has 4,800 transparent display pixels out of 160,000 (3%); the northwest holes are missing display data, not dark ground. The remaining darkening is visible outside those holes. Both other targets and all baseline previews are fully opaque. Display pixels are not independent analysis cells: the fixed metric grid is 100 x 100 cells with 10 m spacing. RGB previews use B4/B3/B2 with fixed 0-0.3 stretch and gamma 1.2; production optical detection uses mean absolute reflectance difference across B2/B3/B4/B8 >0.10 followed by a nine-cell connected-patch filter. A visible RGB transition alone does not identify which numerical stage excluded it. No raw optical difference distribution or qualifying pre-filter mask was measured in these artifacts.

Optical processing retains SCL vegetation/bare-soil classes and Cloud Score+ `cs_cdf >= 0.6`; all three comparisons report full Cloud Score+ screening without fallback. Radar processing screens backscatter, incidence angle and slopes above 15 degrees and requires at least two valid daily baseline observations per cell. The artifacts give combined valid coverage, not a separate attribution of each rejected pixel to terrain, angle, backscatter or baseline validity. No radar previews were generated for the insufficient comparisons, as intended. Their saved `changed_area_m2: 0` must not be interpreted as observed zero radar change; the aggregate radar area is null.

Signed radar diagnostics remain available on the valid subset even when whole-AOI coverage is insufficient:

| Target / orbit | Median VV delta | Median VH delta | Raw either-band / both-band support | Baseline range >3 dB, VV / VH |
| --- | --- | --- | --- | --- |
| July 16 / 115 | -0.03 dB | -0.19 dB | 13.03% / 0.49% | 2.37% / 18.07% |
| July 23 / 42 | +0.10 dB | +0.09 dB | 4.67% / 0.00% | 1.72% / 8.08% |
| July 28 / 115 | -0.28 dB | -0.41 dB | 15.10% / 0.37% | 3.29% / 15.40% |

Diagnostic counts match the 5,910, 5,978 and 5,901 common valid cells respectively. Fractions describe these subsets before patch filtering; they are not accepted radar detections, quiet controls or comparable accuracy scores against Engels.

[CAL FIRE's incident page](https://www.fire.ca.gov/incidents/2024/7/24/park-fire/) confirms the July 24 start and frozen reference coordinate. Its [dated July 27 update](https://www.fire.ca.gov/incidents/2024/7/24/park-fire/updates/1d23c265-853e-413e-a1e8-314b367a210c) supplies incident context, and [USGS](https://www.usgs.gov/media/images/landsat-images-park-fire-july-2024) identifies regional Landsat acquisitions on July 26 and July 27. These establish the regional event and timing, not a dated burn-interior label for every cell of this square. No dated independent AOI burn polygon was established in this review. The original case labels remain `unreviewed` in the frozen manifest and saved artifacts; visual review does not silently promote them to ground truth.

**Acceptance finding:** live case execution, source isolation, diagnostic persistence and negative-result preview packaging passed. Imagery accuracy acceptance remains open. The July 27 visual/numeric discrepancy needs independent dated AOI labels and raw optical difference/mask diagnostics before assessing a false negative or considering calibration. July 17 is a visually similar optical candidate control, not an independently established quiet week; radar supplies no accepted control. This pair adds evidence but does not satisfy the required representative known-change/quiet-control gate. Thresholds, masks, windows, AOI and labels were not changed to fit the results.

Public snapshots taken after the event run and after the completed pair had identical HTML, latest/history JSON and three PNG hashes (six files). The first snapshot preceded the pre-event dispatch; it was not a before-both-runs snapshot. The results ref remained `8714435fea8b875f960d396f0b43d79f7545e22c`, the public analysis key remained `0d938c6c2828198c1593`, and `MONITOR_ENABLED` remained unset. No imagery-review case replaced the public Engels report.

## Compute acceptance before scaling

A representative 20-location, multiweek benchmark remains unmeasured. The four weeks at one 2 km site are not representative of that workload. No EECU total or monthly cost estimate has been established.

For the eventual benchmark, record the site/size/terrain/cloud mix, exact weeks, implementation/settings, UTC request interval and workload tags. Run uncached or explicitly refreshed analyses, including both sensors, baseline work, summaries, previews and bounded retries. Retain Cloud Monitoring exports with metric names, units, interval, filters and raw data. Convert measured EECU-seconds to hours by dividing by 3,600.

Google's [usage-monitoring guide](https://developers.google.com/earth-engine/guides/monitoring_usage) distinguishes successful completed-request compute from in-progress compute, which includes failed requests. Review failure/retry consumption explicitly and avoid double counting those metrics. A deterministic tag can include earlier reruns, so filter by the actual benchmark interval. Diagnostic reductions must be included if they will be enabled in the measured workload. Elapsed runtime is not EECU usage.

Extrapolate to five monthly runs only after measuring the representative sample. Keep the 100 EECU-hour planning target provisional until actual project allowance and measured consumption have been reviewed.

## Publication scope and remaining gates

`sites.yaml` still contains only Engels, `max_sites: 1` is unchanged and `MONITOR_ENABLED` was verified unset. Scheduled monitoring and expansion remain disabled. Historical validation saved records to the results branch with publishing off; the reviewed October 12 prototype remains public.

Before any rollout: complete independent quiet/change imagery review, characterize the broad radar response against those controls, complete the representative EECU review, and exercise the failed-analysis Pages deployment path. Live numeric checks, per-band diagnostic execution, controlled Pages-artifact packaging and frozen real-imagery case execution have passed. The Park Fire review exposed a visible optical transition with zero detections and no usable radar comparisons; it did not pass the imagery accuracy gate. Do not tune to this single site or treat the reference agent plan as approval to enable scheduling or expand the site list.

## Human-review product direction

The user prioritized construction, larger vehicles and concentrations of cars/trucks, with every usable image reviewed by a person. [The implementation/research note](human-review.md) records existing construction, Earth Engine, truck and vessel work, the practical 10 m/patch-size/water-mask limits, and the decision to start with an isolated civilian review workflow. This does not claim object recognition or counts.

Frozen validation reports now have an aligned comparison viewer, browser-local reviewer observations and JSON export. All 58 offline tests, browser persistence/export/isolation checks, desktop/mobile visual review and JavaScript package inclusion passed; [QA evidence](evidence/reviewer-workbench-2026-10-16.json) records those checks. Original Park Fire measurements and PNGs were reused without new Earth Engine requests. Reviewer observations do not alter frozen labels, classify the Park Fire discrepancy or establish construction/vehicle accuracy. A small civilian construction/control pilot is the next science check.
