# Validation status

Recorded 16 October 2026 (Europe/Helsinki).

## Verified

- 46 offline checks pass, including UTC windows, metric grids, sensor/orbit isolation, coverage rules, saved history, error diagnostics, reduction limits, optional radar diagnostics and controlled HTTP publication bundles.
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

**Unresolved:** saved radar previews display VV only, although either VV or VH can trigger a candidate. They cannot establish the sign, magnitude or contributing polarization of the broad response. They also cannot distinguish environmental variation, baseline instability and processing artefacts. The baseline has only two daily observations, so baseline variability needs explicit inspection before considering thresholds. Earth Engine documents its [Sentinel-1 preprocessing and heterogeneous collection](https://developers.google.com/earth-engine/guides/sentinel1); matching orbit/pass alone does not establish scientific accuracy.

## Optional radar diagnostics

`sentinel-monitor run --radar-diagnostics --end-date 2026-10-12 --results results-validation --output site-validation` requests an additional bounded Earth Engine reduction for each radar comparison with common valid cells.

The diagnostic JSON records VV and VH separately: baseline and target backscatter distributions, signed target-minus-baseline differences, daily baseline range, fractions above +3 dB and below −3 dB, baseline-range exceedance, and fractions crossing the threshold in either/both polarizations. All use common valid cells before connected-patch filtering. Mean and percentile summaries describe the signal; they are not confidence estimates. Percentiles use Earth Engine reducer defaults.

The flag is off by default, is available as a manual workflow input and adds compute when selected. It does not change thresholds, masks, statuses or science keys. Requesting diagnostics upgrades an older completed record instead of silently reusing one without diagnostics. Diagnostic request failures retain usable detections, surface a partial error and are retried by a later run. Synthetic mode rejects this flag.

**Live execution pending:** the new diagnostic expressions have offline graph coverage, with mocked reducer values. Local Google ADC is unavailable, and GitHub federation is restricted to main. Run the diagnostic code after its PR is merged, initially with publishing disabled. These historical runs executed the existing main implementation; none contains the new diagnostic measurements. Do not infer numerical diagnostic results from the PNGs.

## Controlled failure acceptance

`tests/test_publication_acceptance.py` drives the real CLI, persistence and report builder with controlled service outcomes, then serves the generated bundle over local HTTP:

- A usable negative optical result plus a radar error yields location `error`, not an all-clear.
- A candidate plus a radar error preserves the candidate and displays the partial failure.
- A failed preview preserves the candidate measurements and displays an unavailable-preview message.
- HTML, latest/history JSON and every referenced PNG remain accessible and consistent with those outcomes.
- Failed records retry without `--refresh`; successful recovery replaces the matching record, preserves the earlier week and is subsequently cached.

These checks use mocked Earth Engine responses and synthetic test PNGs. They verify local publication bundles and exit code 2 for partial failures. The optional diagnostic table and failure messages were also visually checked in Chrome at 1280 px and 390 px widths; neither layout overflowed the page. A controlled failed analysis through GitHub's Pages artifact/deploy jobs remains pending; no synthetic failure was published over the live report.

## Independent examples and quiet controls

Two public event cases have dated primary evidence and are shortlisted for later validation, without changing the active site list:

| Case | Proposed target / baseline (UTC, end-exclusive) | Independent evidence | Remaining acceptance work |
| --- | --- | --- | --- |
| Valencia flooding, Spain | Target [2024-10-28, 2024-11-04); baseline [2024-09-30, 2024-10-28) | [NASA Landsat observation on October 30](https://science.nasa.gov/earth/earth-observatory/valencia-floods-153533/) and [ESA/LIST October 31 inundation map with October 19 reference](https://www.esa.int/ESA_Multimedia/Images/2024/11/Sentinel-1_derived_map_of_flood_affected_urban_area_-_Valencia_Spain) | Choose a small AOI intersecting a mapped flood polygon and a nearby dry control; check actual Sentinel source coverage and radar orbit matches. The optical land-only mask may exclude inundated pixels, so insufficient coverage must not be scored as a negative detection. |
| Park Fire, California | Target [2024-07-22, 2024-07-29); baseline [2024-06-24, 2024-07-22) | [NASA's dated July 27 Landsat images](https://science.nasa.gov/earth/earth-observatory/after-the-park-fires-rapid-growth-153122/) | Select a burn-interior AOI and an unburned control from an independent perimeter; inspect smoke, clouds, slope screening and actual source dates. |

These are candidate validation designs, not completed accuracy checks. Freeze AOIs and labels from independent evidence before examining detector outputs. Include a pre-event week at each AOI and nearby control areas, visually review both dates, and record review provenance and exclusions. Absence of a reported event alone does not establish a quiet control. No event attribution is assigned to Engels candidates.

## Compute acceptance before scaling

A representative 20-location, multiweek benchmark remains unmeasured. The four weeks at one 2 km site are not representative of that workload. No EECU total or monthly cost estimate has been established.

For the eventual benchmark, record the site/size/terrain/cloud mix, exact weeks, implementation/settings, UTC request interval and workload tags. Run uncached or explicitly refreshed analyses, including both sensors, baseline work, summaries, previews and bounded retries. Retain Cloud Monitoring exports with metric names, units, interval, filters and raw data. Convert measured EECU-seconds to hours by dividing by 3,600.

Google's [usage-monitoring guide](https://developers.google.com/earth-engine/guides/monitoring_usage) distinguishes successful completed-request compute from in-progress compute, which includes failed requests. Review failure/retry consumption explicitly and avoid double counting those metrics. A deterministic tag can include earlier reruns, so filter by the actual benchmark interval. Diagnostic reductions must be included if they will be enabled in the measured workload. Elapsed runtime is not EECU usage.

Extrapolate to five monthly runs only after measuring the representative sample. Keep the 100 EECU-hour planning target provisional until actual project allowance and measured consumption have been reviewed.

## Publication scope and remaining gates

`sites.yaml` still contains only Engels, `max_sites: 1` is unchanged and `MONITOR_ENABLED` was verified unset. Scheduled monitoring and expansion remain disabled. Historical validation saved records to the results branch with publishing off; the reviewed October 12 prototype remains public.

Before any rollout: execute the new diagnostics on live imagery, resolve or characterize the broad response using independent quiet/change controls, complete the representative EECU review, and exercise the failed-analysis Pages deployment path. Do not tune to this single site or treat the reference agent plan as approval to enable scheduling or expand the site list.
