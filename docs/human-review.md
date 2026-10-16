# Human imagery review

Recorded 16 October 2026 (Europe/Helsinki).

The requested direction is construction and visible concentrations of larger vehicles, with every usable acquisition going through human review. The first useful product behavior is a small review queue with clear before/after imagery and a way to keep the reviewer's observations. Automated object identification and counts are not established capabilities. New validation work uses civilian construction and transport examples.

## What already exists

| Primary source | What it demonstrates | Decision for this prototype |
| --- | --- | --- |
| [Canty's Earth Engine iMAD tutorial and source](https://developers.google.com/earth-engine/tutorials/community/imad-tutorial-pt1) | Multiband statistical change maps and relative radiometric normalization, with executable Earth Engine examples. This is a community-contributed tutorial hosted by Google. | A useful later option if simple differences keep producing unstable candidates. Introducing an iterative statistical method now would add complexity before representative review labels exist. |
| [Tang et al., broad-area construction screening](https://www.sciencedirect.com/science/article/pii/S2666017224000221) | Time-series construction screening using spectral mixture analysis, CCDC and rule-based filters. The paper treats outputs as candidate sites for subsequent analysis. | Supports construction screening followed by human review. Adopting its multiyear model is a larger change than this weekly prototype needs now. |
| [ONS Data Science Campus truck prototype](https://github.com/datasciencecampus/detecting-trucks), [Fisser et al. source](https://github.com/hfisser/S2TD) | Specialized detection of moving trucks on roads in Sentinel-2 imagery. ONS reports that its experimental system did not meet the desired near-real-time robustness and did not enter production; its repository is archived. | A research reference, not a ready production dependency or evidence for parked-vehicle detection. No code or models were imported. |
| [Global Fishing Watch Sentinel-1 vessel dataset](https://globalfishingwatch.org/platform-update/2024-may-data-download-portal-new-dataset-released-featuring-vessel-detections-from-sentinel-1-sar/) | A dedicated vessel-detection product with scene footprints and AIS matching context. | Shows that ships have an established specialized pipeline. Keep that separate from the current land-change detector; no account, integration or external data download was added. |

The inference from these sources is that a general change-review tool is the simplest first step, while construction time series, ships and moving road vehicles need different detection methods. None of the sources validates this repository's thresholds, aircraft detection or vehicle counts.

## Practical limits of the current feed

The [Sentinel-2 catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED) documents 10 m pixels for the B2/B3/B4/B8 bands used here. The detector also requires at least nine connected cells, approximately 900 m². Resizing the preview does not add ground detail. Large surface alterations can be review candidates; detecting individual cars or identifying aircraft from this pipeline is not a supported claim. Whether a concentration of vehicles creates a usable signal needs civilian examples and human labels.

The current optical mask retains SCL classes 4 and 5, so it excludes water and cannot be presented as a general ship detector. The 28-day rolling baseline can also absorb gradual construction. Neither the water mask nor the thresholds were changed to fit a desired result. These are product limitations to address with a small representative civilian pilot rather than a new training pipeline now.

## Implemented first pass

Frozen validation reports now include a collapsible comparison viewer for each usable acquisition with previews, including observations with zero detector flags. Baseline, target and overlay use the same display area and existing fixed stretch. Transparent preview pixels show a checkerboard. The original side-by-side previews remain available without JavaScript.

The reviewer can choose **Likely visible change**, **No obvious visible change**, **Unclear**, or leave an observation **Unreviewed**, with a short note. These are reviewer observations, not verified labels or detector overrides. Notes stay in browser-local storage when available. JSON export includes every eligible comparison in the open report, its case, source-record timestamp, science key and comparison ID. It includes unreviewed records so missing reviews remain apparent. Storage failures are shown and the current notes can still be exported.

Reviews are isolated by mode, case, site, science key, comparison ID and record-generation timestamp. A refreshed analysis starts a new review even if the science key and source acquisition are unchanged. The workbench appears only in isolated validation reports requesting review previews; routine monitoring reports retain their current behavior. There is no shared review service, automatic ground-truth promotion, import/merge flow or network write.

No additional imagery was requested for this UI change. The downloaded Park Fire records and PNGs were rebuilt locally; their measurements, source IDs and source preview files were preserved. This verifies the review workflow, not construction or vehicle-detection accuracy. Existing public publication and disabled scheduling remain unchanged.

## Verified

All 58 existing offline tests pass. Headless Chrome checks exercised keyboard/image switching, save/reload, export contents, cross-case and refreshed-record isolation, blocked-storage recovery and JavaScript-disabled previews. The 1280 px desktop and 390 px mobile layouts fit without horizontal overflow and their screenshots were visually inspected. An isolated wheel build contains the JavaScript asset. [QA evidence](evidence/reviewer-workbench-2026-10-16.json) records checks and source/screenshot hashes. QA notes are explicitly marked as test data and were not added to analysis records or used as labels.

The next small science-validation step is a documented civilian construction example with a nearby visually similar comparison area. Review every usable date and record uncertain/insufficient cases. The Park Fire optical discrepancy and broad Engels radar responses remain unresolved; this UI change does not calibrate them or complete the EECU/publication gates.
