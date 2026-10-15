# Validation status

Recorded 16 October 2026 (Europe/Helsinki).

## Verified

- 37 offline regression checks pass, including UTC windows, metric grids, sensor/orbit isolation, coverage rules, saved history, error diagnostics, and reduction limits.
- The [one-site live run](https://github.com/Savvyboi/baseviewer/actions/runs/38824576055) passed for Engels air base, with exclusive end date `2026-10-12` and publishing disabled.
- Workload Identity Federation and the monitoring service account performed server-side comparisons and created PNG previews after the thumbnail-creation permission was granted.
- The results branch contains a complete JSON record and valid 400 x 400 before, after, and overlay PNGs.
- The [first Pages deployment](https://github.com/Savvyboi/baseviewer/actions/runs/38825866484) passed. The [public prototype](https://savvyboi.github.io/baseviewer/) and all three PNG previews plus both JSON links returned HTTP 200. Publication reused the completed live record without requesting an analysis refresh.
- Repeated refreshes replaced the same site/window record; no duplicate record was created for these reruns.

## Current example

The 2 km tile uses `EPSG:32638` and a fixed 10 m grid. Target dates are `[2026-10-05, 2026-10-12)`; baseline dates are `[2026-09-07, 2026-10-05)`.

One optical acquisition passed the coverage rule and reported no threshold crossing; three optical comparisons returned insufficient data. A radar acquisition on `2026-10-08`, matched to descending relative orbit 152, flagged approximately 2.97 km² with 88.5% common valid coverage. This is a widespread radar signal difference, not established ground truth or an inferred cause. The initial 3 dB threshold still requires calibration.

## Required before scaling

1. Compare several historical weeks at the first location and inspect source imagery for quiet and candidate cases. Do not label a period quiet solely because the detector returned no flag.
2. Select representative public validation locations with independent dated evidence of change and quiet controls. Include varied AOI sizes, cloud conditions and terrain.
3. Measure 20 locations across several weeks, including both sensors, all baseline work, summaries and previews. Use tagged Cloud Monitoring EECU data; elapsed runtime is not compute consumption.
4. Record the measured EECU-hours, source weeks and site mix. Extrapolate to five monthly runs only after this representative measurement.
5. Complete the imagery validation and compute review before enabling scheduled publication. The first manual Pages deployment and its saved asset/JSON links have been verified; failure-state publication still needs a controlled acceptance check.

## Publication scope

The first publication contains only the reviewed Engels example and its explicit prototype/calibration notice. `max_sites: 1` remains in place, and `MONITOR_ENABLED` is unset, so scheduled monitoring stays disabled during validation. Pages publication does not establish detection accuracy or completion of the compute benchmark.
