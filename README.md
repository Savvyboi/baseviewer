# Baseviewer

Weekly **possible ground-change** monitoring with Google Earth Engine, Sentinel-1 radar, Sentinel-2 optical imagery, Python, GitHub Actions and GitHub Pages.

The first location is **Engels air base**, with a 2 km square around the [public aerodrome reference coordinate](https://ourairports.com/airports/RU-8602/). This initial tile covers only part of the airfield. The configured Earth Engine project is `baseviewer-511722`. Coordinates and project IDs are not credentials.

The one-location live workflow has passed, including Google federation authentication, both sensors, persistent history, and PNG previews. The [published report](https://savvyboi.github.io/baseviewer/) is a prototype: quiet/known-change validation, threshold calibration, and the 20-location EECU benchmark are still pending. See [validation status](docs/validation.md). Scheduled analysis is gated by `MONITOR_ENABLED=true`.

## Run locally

Python 3.11 or newer is required; development and CI use Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\sentinel-monitor.exe validate
.\.venv\Scripts\sentinel-monitor.exe run --demo --end-date 2026-10-12
.\.venv\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8765`. Demo reports carry a prominent **SYNTHETIC DATA** label and use illustrations, not satellite imagery. `--demo-scenario quiet` and `--demo-scenario cloudy` exercise other statuses. The demo checks report plumbing and status decisions; it does not validate Earth Engine's scientific outputs.

On Linux/macOS use `.venv/bin/python` and `.venv/bin/sentinel-monitor`, or activate the virtual environment and use `python` / `sentinel-monitor` directly.

For a real run, configure [Google access](docs/google-cloud.md), then:

```powershell
.\.venv\Scripts\sentinel-monitor.exe run --output site-live --end-date 2026-10-12
```

`--project PROJECT_ID` or `EE_PROJECT_ID` overrides `earth_engine_project` in `settings.yaml`. The client always initializes with an explicit project. Live mode uses Application Default Credentials; no private keys are stored in the repository.

## Regular Sentinel-2 review

Ordinary monitoring reports support the same local review controls as frozen validation
cases when `--review-previews` is requested. Use `--sensors optical` for Sentinel-2-only
analysis and `--optical-review-stretch` for an additional paired display range. Review
all usable observations, including those without an automated flag; notes stay in the
browser and can be exported/restored locally.

The manual **Sentinel monitor** workflow exposes these controls and a fixed
`european-ports` profile for three small container-yard areas. Its default remains the
configured site, both sensors, and review previews disabled. The port profile does not
change the active site file or enable scheduling. See [the regular optical review
pilot](docs/regular-optical-review.md) for the exact inputs, locations and persistence.

## Configure locations and rules

Add entries to `sites.yaml` with a unique lowercase slug, name, latitude, longitude and `size_m` (default 2000). Widths must be multiples of 10 m, between 30 m and 20 km. The analysis constructs a metric square in local UTM or polar UPS and stores its fixed CRS and grid transform. A 2 km square has 40,000 cells at 10 m. The grid centre can shift by up to 5 m in each axis to keep cell edges aligned.

Select one location using `--site-id engels-air-base`; repeat the option for several locations. The initial `max_sites: 1` guard must be raised deliberately before larger runs. Planned area is the sum of individual squared widths.

`settings.yaml` contains prototype thresholds:

| Check | Starting value |
| --- | --- |
| Optical mean absolute reflectance difference over B2/B3/B4/B8 | > 0.10 |
| Absolute radar VV **or** VH difference | > 3 dB |
| Minimum connected patch, 8-neighbour connectivity | 9 cells (~900 m²) |
| Common valid AOI coverage per comparison | ≥ 70% |
| Independent baseline acquisition days per evaluated pixel | ≥ 2 |
| Cloud Score+ `cs_cdf` | ≥ 0.6 |
| Conservative radar terrain slope exclusion | > 15° |

These values need calibration against quiet and known-change examples. A flag means **possible ground change**. Weather, moisture, vegetation and remaining sensor artefacts can also change the signal. Reports do not infer causes or assign confidence percentages.

## Dates and processing

All windows are UTC and end-exclusive. With `--end-date 2026-10-12`, the target window is `[2026-10-05, 2026-10-12)` and the baseline is `[2026-09-07, 2026-10-05)`. Without the option, the end is the start of the current UTC day, so only complete days are included.

Optical processing uses `COPERNICUS/S2_SR_HARMONIZED`, scales reflectance by 0.0001, keeps SCL classes 4 and 5, and links Cloud Score+ by `system:index`. Missing Cloud Score+ pixels fall back to SCL; the affected comparison records reduced screening quality. Categorical masks use nearest-neighbour sampling. See the [Sentinel-2 catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED) and [Cloud Score+ catalog](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED).

Radar processing uses IW acquisitions with VV and VH and compares only matching relative orbit/pass groups. It respects native validity, excludes low-backscatter/noisy edges and incidence-angle extremes, and screens steep terrain with [Copernicus DEM 2024_1](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30_2024_1). The slope mask is a conservative screen, not a complete layover/shadow model. Speckle averaging and baseline medians operate on linear power; comparison then uses dB. Earth Engine's [Sentinel-1 preprocessing](https://developers.google.com/earth-engine/guides/sentinel1) applies geometric terrain correction, without radiometric terrain flattening.

Overlapping tiles or radar slices from the same UTC acquisition day are mosaicked before baseline counting, so they cannot masquerade as independent observations. Target granules/slices sharing a datatake are mosaicked, and each distinct target acquisition is compared with its sensor/group baseline, including multiple acquisitions on one day. Common validity, patch operations, area reductions and preview reprojections use the location's fixed grid.

Reported areas are the spatial union of qualifying comparisons per sensor, avoiding double counting across acquisitions. Overlap is spatial support from both sensors during the week; it does not assert simultaneous observations. Each candidate includes actual acquisition times, baseline acquisition days, source IDs, thresholds, coverage and analysis version. Baseline previews are explicitly labeled composites and use the same stretch as their target previews.

## Validation diagnostics

Three additional historical weeks at Engels have passed with publishing disabled. Radar
candidates recur across all four reviewed weeks, covering about 20–84% of common valid
cells per acquisition. These results do not establish quiet controls or detection accuracy.
See [the evidence and remaining acceptance gates](docs/validation.md).

For an investigation run, add `--radar-diagnostics` (or enable the corresponding manual
workflow input). This optional extra reduction saves signed VV/VH distributions, baseline
variability and polarization-specific threshold fractions on common valid cells. It does
not change detection rules and is off by default. Requesting it recomputes older cached
records without diagnostics. The diagnostics passed live execution on all four reviewed weeks; the signed results and
baseline variability are recorded in the validation notes.

`--imagery-diagnostics` optionally retains pre-filter source counts/exclusions,
orbit/baseline eligibility, comparison validity and pre-patch counts, plus optical
reflectance/difference distributions and fixed-stretch endpoint support. It is also
available on `review-case` and the isolated validation workflow, off by default.
It adds computation and upgrades cached records without changing science keys or
original previews. [Diagnostic scope and measured Gobabeb findings](docs/imagery-diagnostics.md)
are documented. The first approved Gobabeb diagnostic run passed; it confirms a radar
catalog gap and optical display clipping, without establishing a radar quiet control.

For controlled failures, `--demo-scenario sensor-error` and
`--demo-scenario preview-error` create labelled synthetic reports and return exit code 2.
The **Validation acceptance** workflow packages these reports as ordinary and Pages
artifacts on PRs, with no deployment job. A manual `failure-artifacts` run deliberately
ends failed after saving its evidence.

`sentinel-monitor validate-live --project PROJECT_ID` runs 12 small constant-raster
checks through the production comparison method on Earth Engine, writes expected/observed
JSON under `results-validation/`, and returns nonzero if a check fails. The workflow's
manual `numeric` option can run it on main with the existing federation. All 12 numeric
checks passed on Earth Engine; they do not establish real-imagery accuracy.

Frozen imagery cases are separate from active monitoring. Use
`sentinel-monitor review-case --case park-fire-event` or
`--case park-fire-pre-event`, or select `imagery` in the manual validation workflow.
The one-case run uses production settings, saves an isolated report artifact and records
its [independent source context](validation/cases.json). Both cases have passed live execution and their original PNGs have been reviewed;
the findings do not establish accuracy or an independent quiet control. See
[validation status](docs/validation.md).

`--review-previews` saves imagery for all usable comparisons, including detector-negative
observations, and includes those observations in the review report. It is off by default,
adds preview requests and upgrades older cached records when requested. It does not change
detection rules; insufficient data remains insufficient data.

## Human review

Isolated validation reports include aligned baseline/target/overlay controls and
browser-local reviewer observations with JSON export. Every usable acquisition can
be reviewed, including zero-flag results. Refreshed records get separate reviews;
notes do not change detector outputs. Export a copy to keep or share the review.
See [the review workflow, existing implementations and imagery limits](docs/human-review.md).
Use `sentinel-monitor assess-reviews` to assess a saved export against the original
history entirely offline. Actual observations, derived summaries and provenance
receipts stay in an ignored private directory; see the
[private assessment methodology and evaluation gates](docs/private-review-assessment.md).

## History and errors

Live and synthetic data are separated under `results/live` and `results/demo`. Each site/window/science configuration has a deterministic record key. Detection IDs also include sensor and source acquisitions. Repeating a completed run reuses the saved record. Changing scientific settings changes the key; changing concurrency or preview settings does not.

Use `--refresh` for late-ingested imagery, threshold validation, or replacing an earlier result for the same window. This updates that window's record and preserves earlier weeks. Errors and failed previews are retried on subsequent runs without needing `--refresh`. A completed `insufficient_data` result is cached; use `--refresh` to check for new arrivals.

Homepage statuses are `possible_change`, `no_change_detected`, `insufficient_data`, or `error`. A usable sensor can flag a candidate even if the other fails. A partial analysis error is shown explicitly and cannot silently become an all-clear. CLI exit code 2 means useful reports were built with partial errors; exit code 1 means the command could not complete. Other locations and sensors continue after individual request failures. Transient requests have bounded retries; site processing is sequential initially.

Generate a complete website from persistent history without accessing Earth Engine:

```text
sentinel-monitor build --results results --output site-live
```

Choose separate output directories for live and demo builds. Public exports include HTML, JSON and actual PNG files, not expiring thumbnail links. All configured coordinates and report data are public when deployed to Pages.

## GitHub Actions and Pages

[The single workflow](.github/workflows/monitor.yml) runs lint, regression checks and a synthetic report on pull requests and main-branch pushes. Weekly monitoring is scheduled for Monday at 06:30 UTC, but its job remains gated until `MONITOR_ENABLED` is `true`.

Configure these repository **Actions variables** after following [the Google setup guide](docs/google-cloud.md):

| Variable | Value |
| --- | --- |
| `EE_PROJECT_ID` | `baseviewer-511722` |
| `WIF_PROVIDER` | Full Workload Identity provider resource name |
| `EE_SERVICE_ACCOUNT` | Monitoring service-account email |
| `MONITOR_ENABLED` | Leave unset until live validation and publication pass; then `true` |

In Settings → Pages, select **GitHub Actions** as the source. See GitHub's [Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

First use **Actions → Sentinel monitor → Run workflow** on `main`, with demo enabled and publish disabled. The generated site is downloadable as an artifact. For the first live trial, disable demo and keep publish disabled. Review acquisition dates, coverage, sources and previews, then run manually with publish enabled. Publishing a demo is possible only when explicitly requested by the manual input and will replace the public homepage with a labeled demo.

The workflow fetches history from the `results` branch (creating it if necessary), saves live JSON/PNGs there, rebuilds the complete static site, then deploys a Pages artifact. A concurrency lock serializes publishers, so runs cannot overwrite each other's history. Useful partial results can still be saved/deployed while the workflow is marked failed. OIDC permissions are limited to the monitoring/deployment jobs; checks receive read access. Third-party actions are pinned to verified commit SHAs.

## Benchmark before scaling

Use 20 representative locations across several historical weeks, including varied sizes, cloud conditions and candidate densities. Raise `max_sites` to 20 only for that stage. Include both sensors, all baseline work, summaries, previews and retries in measurement. Workload tags are saved in each record and `results/run-summary.json`; filter these in [Cloud Monitoring](https://developers.google.com/earth-engine/guides/monitoring_usage). Elapsed seconds in the report are diagnostic wall time, **not EECU usage**.

Record measured EECU-hours and extrapolate explicitly:

```text
sentinel-monitor benchmark --measured-sites 20 --measured-eecu-hours 1 --target-sites 200 --monthly-runs 5
```

That example estimates 50 EECU-hours/month, without claiming that the real workload costs one hour. Use a 100 EECU-hour monthly planning budget and verify the project's [current tier and allowance](https://developers.google.com/earth-engine/guides/noncommercial_tiers). No benchmark has yet been measured. Scale to 200 only after compute measurement, quiet/known-change visual inspection and a manual publication pass.

## Development

```text
ruff check .
ruff format --check src tests
pytest -q
```

The checks exercise configuration, UTC windows, grid construction, coverage/status handling, orbit isolation, tile deduplication, history, mode separation, escaping and Earth Engine expression serialization using the client library's offline API fixture. Reducer outputs in those graph tests are mocked. They establish client-side construction and handling, not real imagery accuracy; the live one-site run verifies server execution and saved previews, while scientific accuracy remains an acceptance step.

Object recognition, people/vehicle counting, a database and coordinate-entry forms are outside this initial milestone.
