# Regular optical review pilot

Prepared 18 October 2026. The first routine pilot uses small land-side container-yard
areas in Rotterdam, Valencia and Genoa. It supports a person comparing satellite
images. Detector flags provide screening; formal accuracy calibration is not a
prerequisite for this bounded pilot. Thresholds, cloud/land masks and patch math are
unchanged.

## Run the regular workflow

After code review and specific approval of a new live batch, use **Actions → Sentinel
monitor → Run workflow** on the reviewed merged main commit:

| Input | Pilot value |
| --- | --- |
| `sites_profile` | `european-ports` |
| `sensors` | `optical` |
| `review_previews` | `true` |
| `optical_review_stretch` | `true` |
| `demo` | `false` |
| `end_date` | `2026-10-18` for the prepared first batch |
| `site_id` | Blank for all three; one profile site ID for a smaller run |
| `refresh` | `false` |
| `radar_diagnostics` | `false` |
| `publish` | `false` |

The prepared UTC target is `[2026-10-11,2026-10-18)` and its rolling baseline is
`[2026-09-13,2026-10-11)`. These dates describe completed UTC days and were chosen
before any new port imagery or detector output. Actual source availability, common
valid coverage and preview usefulness remain unknown until a live run.

The fixed profile reads [sites.yaml](../pilots/european-ports/sites.yaml) and
[settings.yaml](../pilots/european-ports/settings.yaml). The pilot's three-site guard
is separate from the active `max_sites: 1` configuration. The workflow accepts only
`configured` or `european-ports`; it offers no arbitrary configuration path input.
Default and scheduled calls retain the configured locations, both sensors and no
additional review previews. `MONITOR_ENABLED` remains unchanged.

A local equivalent, using existing authorized Earth Engine credentials, is:

```console
sentinel-monitor run --sites pilots/european-ports/sites.yaml --settings pilots/european-ports/settings.yaml --sensors optical --review-previews --optical-review-stretch --end-date 2026-10-18 --results results-european-ports --output site-european-ports
```

Review flags require live mode. A shared optical display requires review previews
and an optical-capable sensor scope. Radar diagnostics require radar. Invalid
combinations reach the CLI's existing validation rather than being silently dropped.

## Pilot location scope

| Port area | Centre latitude, longitude | Square width |
| --- | --- | ---: |
| Rotterdam ECT Delta yard | 51.95730000, 4.06650000 | 400 m |
| Valencia MSC yard | 39.44008787, -0.32136927 | 300 m |
| Genoa PSA SECH yard | 44.40508294, 8.91058266 | 300 m |

Rotterdam and Valencia squares lie inside the retained mapped terminal polygons.
The Genoa square has 87.606% mapped terminal overlap; its 12.394% remainder can
include access, quay edges or water. These are map-area fractions, not image coverage.
The total planned area is 340,000 m² (3,400 analysis cells).

The exact analyst-selected centres, sizes, snapped grids, source references and
selection limits are retained in [the selection receipt](evidence/european-port-pilot-selection-2026-10-18.json).
The current SCL mask retains classes 4 and 5, so these areas focus on container yards
and adjacent port land. This is not a harbour-water or ship-detection pilot. Mapping
an area inside a terminal does not prove per-pixel optical validity or establish
change/quiet reference truth. Image resolution does not establish individual vehicle
identities or counts.

## Review behavior and private observations

Every usable comparison stays in the feed, including automated negatives. Ordinary
records show routine monitoring context without a fabricated validation label.
Frozen cases retain their original labels, independent references and case IDs.
Missing previews remain awaiting; insufficient comparisons and errors remain visible
in history and are never converted into negatives.

Fixed and shared before/after/overlay displays apply to the same comparison identity.
Ordinary records use the existing schema-1 eight-field key with an empty `case_id`;
frozen records keep their case ID. Science JSON and source PNG bytes are not rewritten
by report building. Export/restore and the private assessment accept ordinary reviews
without inventing reference truth. Actual choices, notes, timestamps, matching
receipts and derived assessments stay local and out of commits, uploads and public
evidence. Browser controls make no network writes.

An opt-in rerun reuses a record only if the fixed source PNG triples of all usable
comparisons are intact. Missing, corrupt or escaping source paths cause recomputation
with a fresh record-generation timestamp. Shared previews also retain their existing
integrity checks. Older observations cannot transfer to that fresh identity. A valid
insufficient-data record does not require fabricated preview files.

## Persistence and execution boundary

The regular workflow retains its existing behavior: a live run saves analysis JSON
and PNGs to the `results` branch even when `publish=false`, and uploads a report
artifact. `publish=false` prevents a Pages deployment; it does not disable analysis
history persistence. Reviewer exports are never pipeline inputs or artifact contents.
The new profile does not turn on the weekly schedule or add ports to the active site
file. No new live batch, results write, deployment or schedule expansion is performed
by this code change. A proposed first batch must name its reviewed commit, profile,
dates and options, including this persistence behavior.

Synthetic verification covers actual workflow argument forwarding, profile mapping,
flag rejection, ordinary empty-case review identities, private assessment matching,
negative/missing/insufficient/error handling, cache repair, and fixed/shared display
switching. Desktop, mobile and JavaScript-disabled browser checks use disposable
fixtures and fresh contexts. These checks establish software behavior, not detection
accuracy or live port coverage.

Verification: 380 offline tests and nine subtests passed; Ruff lint/format and the
synthetic browser checks passed. [Software QA receipt](evidence/regular-optical-review-qa-2026-10-18.json).
