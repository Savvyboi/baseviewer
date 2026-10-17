# Human imagery review

Updated 17 October 2026 (Europe/Helsinki).

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

## Image information in the viewer

Isolated review observations now identify **Sentinel-1 radar / VV** or **Sentinel-2 optical / RGB**, tile width, 10 m analysis-grid spacing, analysis-cell dimensions and the actual PNG dimensions. The three construction squares have 50 × 50 grid cells; Gobabeb has 20 × 20. Both are enlarged to 400 × 400 previews. The current radar source IDs are high-resolution IW GRD products: nominal source resolution is approximately 20 × 22 m at 10 m pixel spacing, before the additional production smoothing. [Copernicus product specifications](https://sentiwiki.copernicus.eu/web/s1-products) distinguish spacing from resolution. Each displayed image also has an **Open original PNG** link; increasing the display size adds no ground detail.

Baseline/target previews are checked locally for display endpoints. A notice appears when at least 95% of opaque display pixels in a channel are at 0 or 255. It describes the PNG, not an analysis threshold or certainty about surface change. Gobabeb's red channel is at the maximum throughout both views; the orange overlay is excluded from this measurement. Transparent pixels do not contribute, and missing preview files do not block retained results. The notice advises Unclear when the display cannot support a decision; it does not change an existing reviewer choice.

All 63 offline tests and the viewer/workbench browser checks passed. Temporary browser tests restored and re-exported synthetic QA observations, including notes and timestamps; the user's browser storage was not accessed. Unclear observations are counted explicitly within reviewed totals. Reference labels are named separately from browser-local reviewer observations. Original source-history and twelve PNG hashes matched. Metadata, display notices and PNG links work without JavaScript. Desktop/mobile screenshots were visually inspected. [QA evidence](evidence/review-image-context-2026-10-17.json) records the checks. No new live execution was needed.

## Implemented first pass

Frozen validation reports now include a collapsible comparison viewer for each usable acquisition with previews, including observations with zero detector flags. Baseline, target and overlay use the same display area and existing fixed stretch. Transparent preview pixels show a checkerboard. The original side-by-side previews remain available without JavaScript.

The reviewer can choose **Likely visible change**, **No obvious visible change**, **Unclear**, or leave an observation **Unreviewed**, with a short note. These are reviewer observations, not verified labels or detector overrides. Notes stay in browser-local storage when available. JSON export includes every eligible comparison in the open report, its case, source-record timestamp, science key and comparison ID. It includes unreviewed records so missing reviews remain apparent. Storage failures are shown and the current notes can still be exported.

Reviews are isolated by mode, case, site, science key, comparison ID and record-generation timestamp. A refreshed analysis starts a new review even if the science key and source acquisition are unchanged. The workbench appears only in isolated validation reports requesting review previews; routine monitoring reports retain their current behavior. There is no shared review service, automatic ground-truth promotion, import/merge flow or network write.

No additional imagery was requested for this UI change. The downloaded Park Fire records and PNGs were rebuilt locally; their measurements, source IDs and source preview files were preserved. This verifies the review workflow, not construction or vehicle-detection accuracy. Existing public publication and disabled scheduling remain unchanged.

## Review queue

Isolated review reports now list every usable acquisition in a queue, show how many have a reviewer observation, and offer **Next unreviewed** with keyboard focus on the next reviewer choice. **Only unreviewed in queue** hides completed queue rows while leaving the active image and note controls available. A note alone does not complete a review; choosing Unclear records that the acquisition was reviewed with uncertainty. Resetting the choice to Unreviewed returns it to the queue.

Usable comparisons with missing preview paths remain **Awaiting previews** and incomplete. Insufficient-data comparisons stay in check history and are excluded from review totals. The queue includes usable detector-negative observations. Counts restore from the existing browser-local notes; they do not change detector statuses, frozen case labels or ground truth. Export retains its existing scope: complete-preview comparisons in the open report, including unreviewed entries.

The three completed Huoshenshan artifact reports were combined locally using their unchanged records and nine original PNGs. The single report has three usable radar reviews and nine insufficient optical comparisons. Its frozen-reference JSON contains the original provenance for each case. [Pilot evidence PR #10](https://github.com/Savvyboi/baseviewer/pull/10) records the science findings separately. No additional imagery request was needed to make the saved pilot reviewable.

All 61 offline tests and browser queue/workbench checks passed. Desktop and mobile queue screenshots were visually inspected. [Queue QA evidence](evidence/review-queue-2026-10-16.json) records the checks and source hashes; QA notes were confined to temporary browser contexts. Independent human adjudication and a verified quiet civilian example remain outstanding.

## Verified

All 58 existing offline tests pass. Headless Chrome checks exercised keyboard/image switching, save/reload, export contents, cross-case and refreshed-record isolation, blocked-storage recovery and JavaScript-disabled previews. The 1280 px desktop and 390 px mobile layouts fit without horizontal overflow and their screenshots were visually inspected. An isolated wheel build contains the JavaScript asset. [QA evidence](evidence/reviewer-workbench-2026-10-16.json) records checks and source/screenshot hashes. QA notes are explicitly marked as test data and were not added to analysis records or used as labels.

The rapid-construction pilot has now executed: its radar comparison flags 36.45% of valid cells versus 10.52% in the pre-construction comparison and 9.59% nearby. All three trigger, and optical data are insufficient throughout. See [the live review and limitations](validation.md#rapid-construction-pilot-results). This supplies a documented construction candidate for the review workflow, while a verified quiet civilian example remains the next science check. The Park Fire optical discrepancy, broad Engels radar responses and EECU/publication gates remain unresolved.

The single approved [Gobabeb stable-surface reference run](validation.md#gobabeb-live-reference-result) passed, adding one usable optical observation with full common coverage and zero qualifying cells. Its location/dates were selected from published stability and independent ground measurements before detector output. No radar comparison was returned. The original RGB views are broadly similar but have a saturated red display channel, limiting fine visual review; full-AOI human adjudication remains pending. The local civilian pilot queue now has four review entries and twelve original PNGs across construction/comparison/reference cases. No frozen label was promoted or extra run requested.
