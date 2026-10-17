# Validation status

Updated 17 October 2026 (Europe/Helsinki).

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

## Review queue workflow

Isolated imagery reports now show a queue of all usable review observations, browser-local progress, a pending-only queue filter and **Next unreviewed** navigation. Missing preview paths remain incomplete; insufficient comparisons stay in history rather than being counted as negatives or reviews. Notes alone do not complete a review. Existing export and case/refresh isolation remain intact. All 61 offline tests, browser navigation/persistence/export checks and the existing workbench browser checks passed; desktop/mobile screenshots were visually inspected. [QA evidence](evidence/review-queue-2026-10-16.json) records these results.

The three already completed construction reports were rebuilt as one local review bundle with unchanged source records and nine original PNGs: three usable radar observations and nine insufficient optical comparisons. Science evidence is tracked separately in [PR #10](https://github.com/Savvyboi/baseviewer/pull/10). No live run, public deployment, scheduling change or detector adjustment was needed for this workflow improvement. QA observations are not independent human adjudication; the verified quiet-civilian-example and accuracy gates remain open.

## Frozen rapid-construction pilot

Three 500 m cases at the historical Huoshenshan emergency public-health hospital are frozen before detector output: construction week ending February 3, 2020; pre-construction week ending January 20; and a nearby square shifted 0.01 degrees longitude east using the construction week's dates. [Selection provenance](evidence/huoshenshan-selection-2026-10-16.json) records the mapped footprint version/bounds, manifest hash, primary event/contractor references and exact cases. The first two use the midpoint of OSM way 766315840 version 9 bounds. The nearby square is a geometric comparison candidate, not established quiet ground truth.

The [National Health Commission report](https://en.nhc.gov.cn/2020-02/03/c_76130.htm) documents January 23 groundbreaking and February 2 delivery; the [contractor's January 28 report](https://english.cscec.com/CompanyNews/CorporateNews/202002/3018196.html) documents construction underway on January 27. The event target is [2020-01-27, 2020-02-03), with the unchanged rolling baseline [2019-12-30, 2020-01-27). That baseline includes four days after groundbreaking and can dilute the comparison. The pre-event target [2020-01-13, 2020-01-20) ends before documented work. All cases retain unreviewed labels and production settings. No threshold, AOI or window will be adjusted to fit outputs. All three explicitly approved runs have now passed on main, with imagery review recorded below. Active sites, scheduling and publication are unchanged.

## Rapid-construction pilot results

The [construction run](https://github.com/Savvyboi/baseviewer/actions/runs/38904946895), [pre-construction run](https://github.com/Savvyboi/baseviewer/actions/runs/38905067211) and [nearby comparison run](https://github.com/Savvyboi/baseviewer/actions/runs/38905236404) all passed serially at merged PR #9 commit `b84eca845595f4c0e3a0a76595a71173e2601a1e`. Each has no service or preview errors, exactly one usable radar comparison, three insufficient optical comparisons, and an artifact containing the new review controls. No deployment or results-branch write ran. [Complete live evidence](evidence/huoshenshan-imagery-2026-10-16.json) retains all source acquisitions, settings, UTC invocation bounds, signed diagnostics, archive/file hashes and review observations. Nine original PNGs are retained unchanged.

| Case | Radar target | Common valid coverage | Changed cells / valid cells | Flagged area | Valid cells flagged |
| --- | --- | --- | --- | --- | --- |
| Construction | January 27, 2020 | 99.20% | 904 / 2,480 | 90,298 m² | 36.45% |
| Pre-construction | January 15, 2020 | 98.84% | 260 / 2,471 | 25,971 m² | 10.52% |
| Nearby comparison | January 27, 2020 | 99.24% | 238 / 2,481 | 23,773 m² | 9.59% |

All radar sources are Sentinel-1A, relative orbit 113 ascending. Construction and nearby comparisons share the same January 3 / January 15 baseline dates and January 27 target acquisition. The pre-construction comparison uses December 22 / January 3 baselines and January 15 as target. Although the nominal event baseline window extends past groundbreaking, its actual radar baseline acquisitions both predate the documented work. The optical baseline source list includes January 23 and January 25. Distinct acquisition days, rather than overlapping optical tiles, are counted as observations.

| Case | Median VV / VH signed delta | Raw either-band / both-band support | Baseline range >3 dB, VV / VH |
| --- | --- | --- | --- |
| Construction | +0.57 / +0.32 dB | 39.03% / 11.53% | 7.98% / 12.90% |
| Pre-construction | +0.32 / -0.09 dB | 14.12% / 0.61% | 7.41% / 10.48% |
| Nearby comparison | -0.09 / -0.60 dB | 15.64% / 1.05% | 9.39% / 12.82% |

Diagnostics use common valid cells before connected-patch filtering, and their counts match the valid-cell totals above. Construction-case VV and VH mean deltas are +0.97 and +0.74 dB. VV/VH positive threshold support is 21.41% / 18.47%, compared with 3.20% / 2.63% pre-construction and 4.11% / 0.85% nearby. These are signal distributions, not confidence or classification scores.

Codex inspected all nine original before/after/overlay PNGs. The construction target shows expanded bright VV returns in the upper-left/central-left and larger connected overlay regions in the northwest, centre and southwest. The other two VV comparisons retain broadly similar gross patterns with smaller, separated overlay patches. The [labelled comparison sheet](evidence/huoshenshan-2026-10-16/review-sheet.png) places the three cases side by side; it is a presentation of the original imagery, not a new analysis. Radar previews show VV only, while either VV or VH can trigger the mask. These 500 m previews cannot resolve or identify construction equipment, vehicles or individual building details. Independent human adjudication remains pending; no frozen label was promoted to ground truth.

All nine optical comparisons remain **insufficient data**. Construction common valid coverage is 3.36% on January 30, 0% on February 2 and 0.32% on January 28; pre-construction is 1.60% on January 13, 0% on January 15 and 0.32% on January 18; nearby is 17.88%, 0% and 11.24% on the corresponding event dates. Every optical comparison has 11 metadata baseline days, which does not guarantee two valid daily observations per cell. Combined SCL/Cloud Score+ masks and per-pixel baseline validity leave too few common cells; the saved artifacts do not separate those mask causes. There is no Cloud Score+ fallback reported. Optical changed area is null in all three aggregates, and no insufficient comparison was scored as a negative or given a preview.

**Practical finding:** the unchanged detector surfaces a candidate during independently documented rapid construction, with more connected radar support than the two comparison candidates. It also flags both comparison candidates. That supports the review-first pilot but does not establish a false-positive rate, quiet controls, accurate construction boundaries or vehicle detection. The nearby area's land-cover comparability is unverified. No new threshold, model, AOI adjustment, mask relaxation or extra live run was introduced to improve these results. A verified quiet civilian example remains the most useful next check; representative EECU usage and the real failed-analysis deployment path are still pending.

**Provenance correction:** selection evidence originally recorded SHA-256 `a176ee2474c7c747e2da1598b509733eff2dc15311d7be5d77a5ee6e8ce4bb8d` from the Windows CRLF working file before Git normalized it. The immutable committed LF manifest and all three live artifacts have SHA-256 `de4dbc5b5b58f2ba73670111c371b7b7489a7838cd3aba5bf644ffbbcc92bfcd`. Replacing only LF with CRLF reproduces the original hash, and all frozen case values match the committed source. [Selection evidence](evidence/huoshenshan-selection-2026-10-16.json) now preserves both hashes, the source commit and Git blob. This corrects provenance bytes; no case input changed.

Before/after snapshots of the public HTML, latest/history JSON and three PNGs matched across the entire approved run sequence (six files). The results ref remains `8714435fea8b875f960d396f0b43d79f7545e22c`, the public analysis key remains `0d938c6c2828198c1593`, `MONITOR_ENABLED` remains unset, and only Engels is active. All 61 offline tests and both pre-merge PR #9 CI workflows passed; the live workflow results above establish execution of the committed pilot. Runtime remains wall time, not EECU consumption.

## Frozen civilian stable-surface reference

One further artifact-only case is prepared: **gobabeb-quiet-reference**, a 200 m square at the civilian Gobabeb HYPERNETS (GHNA) station, -23.60153°, 15.12589°. Target: July 11–18, 2022; rolling baseline: June 13–July 11 (all ends exclusive, UTC). The width follows the satellite cutout method in [De Vis et al. (2024)](https://www.frontiersin.org/journals/remote-sensing/articles/10.3389/frsen.2024.1323998/full). The date is the first accepted Sentinel-2 matchup in the paper whose full rolling baseline begins after its first listed accepted matchup, June 8. This freezes selection independently of this detector's output. GHNA is distinct from the nearby GONA RadCalNet station.

The study documents a stable gravel-plain surface and supplies dated, independent ground measurements. Five small source files from [Zenodo version 1.0.0](https://doi.org/10.5281/zenodo.8039303) were checksum-verified: June 22/28/30 and July 10/13. The initial Figure 2 viewing direction (5° zenith, 98° azimuth) has nonzero quality flags on June 22 and July 13, so it cannot supply the intended comparison. All six common five-degree azimuths were then inventoried; every direction passing the fixed zero-flag/valid-scan/finite-value rule across all five files was reported, without selecting by reflectance values. Only 83° and 113° passed. Their nearest-channel target-minus-four-sample-median differences range from -0.00379 to -0.01309 at nominal 490/560/665/842/900 nm. These small pointed-footprint differences support the reference selection; they are not band-integrated satellite measurements, the satellite baseline, or a detector acceptance test. [Selection and measurement evidence](evidence/gobabeb-selection-2026-10-16.json) retains exact source hashes, channel values, geometry selection and all exclusions.

The whole 200 m square remains unreviewed. Point optical stability does not certify every cell or radar stability, and a desert reference does not establish an urban construction/transport false-positive rate. The smaller square also differs from the 500 m construction cases; flagged fractions must retain that context. The original NetCDF files remain local because their embedded licence differs from the Zenodo record; they were not republished.

All 62 offline tests, lint/format checks and frozen-case/workflow checks passed. Previous cases, production settings, active sites and scheduling are unchanged. The only workflow change is one manual case choice. The single approved Validation acceptance run has now completed on main with `check=imagery`, `case_id=gobabeb-quiet-reference`; its results and limitations are recorded below. It retained the usable previews without deployment or a results-branch write. The frozen selection evidence remains a record of preparation before detector output.

## Gobabeb live reference result

The [single approved run](https://github.com/Savvyboi/baseviewer/actions/runs/38940083654) passed at PR #12 merge commit `3008c9b82b15020ee5eabd9dcb7b0333f52e4231`, with no service or preview errors. [Complete evidence](evidence/gobabeb-imagery-2026-10-16.json) retains the exact frozen input hash, run/artifact IDs, source record, archive/file hashes and all three original PNGs.

| Target acquisition | Sensor | Baseline days | Common valid coverage | Qualifying cells | Result |
| --- | --- | --- | --- | --- | --- |
| July 13, 2022 | Optical | 6 | 100% (400/400 cells) | 0 | No change detected |

The baseline acquisition dates are June 13/18/23/28 and July 3/8, all in tile T33KWP. SCL and Cloud Score+ screening is reported without fallback. The 200 m square uses the fixed 10 m grid; 400 x 400 display pixels do not add analysis detail. No radar comparison or diagnostic was returned, and radar/overlap area remain null. The artifact does not save a raw radar source inventory explaining availability. This is missing radar evidence, not a radar negative.

Codex inspected the [original baseline](evidence/gobabeb-2026-10-16/cff90cd3d81e21a51d738061/before.png), [target](evidence/gobabeb-2026-10-16/cff90cd3d81e21a51d738061/after.png) and [overlay](evidence/gobabeb-2026-10-16/cff90cd3d81e21a51d738061/overlay.png). Both dates look broadly uniform pale tan/orange with faint local tonal variation and no resolved broad transition. The target and overlay are byte-identical, consistent with zero qualifying cells. All pixels are opaque, but the red display channel is at 255 everywhere; green/blue ranges are narrow (baseline 199–211 / 148–158, target 197–209 / 142–157). The fixed 0–0.3 RGB stretch and gamma 1.2 therefore limit fine texture/contrast review. These previews and the small ground-instrument footprints do not establish a whole-AOI quiet label. Independent human adjudication remains pending.

**Finding:** the independently selected stable-surface reference adds one usable optical detector-negative observation to the civilian pilot. It supplies no radar control and does not establish a representative false-positive rate, construction/transport accuracy or boundaries. The clipped optical display also exposes a practical limit for human review of bright surfaces. No threshold, mask, date, AOI or frozen label was adjusted to fit this output, and no extra run was dispatched.

The local pilot queue now combines the three construction radar comparisons and this optical comparison: four usable review entries, twelve original PNGs and nine insufficient optical comparisons retained in history. Records and PNGs are unchanged; Chrome checks confirmed all image hashes and export identities, with no prefilled reviews. Public HTML, latest/history JSON and three PNG hashes matched before/after the approved run. The results ref remains `8714435fea8b875f960d396f0b43d79f7545e22c`; monitoring remains disabled. The 6.327 s analysis duration is wall time, not EECU consumption. Full-AOI human review, radar quiet/change discrimination, representative compute and failed-publication acceptance remain open.

## Review image information

Isolated review reports now show sensor/polarization or RGB, tile/grid/PNG dimensions and the distinction between grid spacing and source resolution. Original PNG links and a measured display-endpoint notice make the bright Gobabeb limitation explicit. At least 95% of opaque PNG pixels at a channel endpoint triggers this display-only notice; it does not affect detection or reviewer decisions. The queue shows unclear observations separately within reviewed totals. Reference label status is named separately from browser-local reviewer observations.

All 63 offline tests and the viewer/workbench browser checks passed, using synthetic QA observations in temporary browser contexts. Original source-history and all twelve PNG hashes are unchanged; desktop/mobile layouts were visually inspected and no-JavaScript access remains available. [QA evidence](evidence/review-image-context-2026-10-17.json) records the results. No additional Earth Engine request, live run, publication or scheduling change was introduced. This UI change does not calibrate construction/transport detection or establish ground truth.
