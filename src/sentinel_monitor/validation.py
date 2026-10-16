"""Small live numeric checks using the production comparison path, not real imagery."""

import math
import uuid
from datetime import UTC, datetime
from pathlib import Path

import ee

from .config import Settings, Site, windows
from .earth import OPTICAL, RADAR, EarthEngineAnalyzer

CASES = {
    "unchanged": ("no_change_detected", 1.0, 0),
    "nine_cell_patch": ("possible_change", 1.0, 9),
    "one_cell_patch": ("no_change_detected", 1.0, 0),
    "diagonal_patch": ("possible_change", 1.0, 9),
    "missing_target": ("insufficient_data", 0.0, 0),
    "one_valid_baseline": ("insufficient_data", 0.0, 0),
}


def sources():
    return [
        {
            "id": f"constant-fixture:{day}",
            "index": day,
            "day": day,
            "time": int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000),
        }
        for day in ["2024-01-08", "2024-01-20", "2024-02-03"]
    ]


def fixture(analyzer, sensor, case):
    """A 10 x 10 grid, with known reflectance or power values and mask holes."""
    coordinates = ee.Image.pixelCoordinates(analyzer.projection)
    x, y = coordinates.select("x"), coordinates.select("y")
    if case == "nine_cell_patch":
        patch = x.gte(3).And(x.lt(6)).And(y.gte(3)).And(y.lt(6))
    elif case == "one_cell_patch":
        patch = x.eq(3).And(y.eq(3))
    elif case == "diagonal_patch":
        patch = x.eq(y).And(x.gte(0)).And(x.lt(9))
    else:
        patch = ee.Image(0)
    if sensor == "optical":
        before = ee.Image.constant([0.1] * 4).rename(OPTICAL)
        after = before.add(patch.multiply(0.2))
        before = before.addBands(ee.Image(0).rename("cloud_fallback"))
        after = after.addBands(ee.Image(0).rename("cloud_fallback"))
    else:
        # Prepared radar imagery is linear power. VV increases by exactly 6 dB
        # in the patch, while VH remains unchanged.
        before = ee.Image.constant([0.1, 0.01]).rename(RADAR)
        after = before.multiply(
            patch.multiply(10**0.6 - 1).add(1).addBands(ee.Image(1)).rename(RADAR)
        )
    prepared = []
    items = sources()
    for index, item in enumerate(items):
        image = after if index == 2 else before
        if case == "missing_target" and index == 2:
            image = image.updateMask(ee.Image(0))
        if case == "one_valid_baseline" and index == 1:
            image = image.updateMask(ee.Image(0))
        prepared.append(
            analyzer.on_grid(image)
            .set("system:index", item["index"])
            .set("system:time_start", item["time"])
        )
    return ee.ImageCollection.fromImages(prepared), items


def diagnostic_matches(comparison, case):
    diagnostic = comparison.get("radar_diagnostics")
    if not diagnostic:
        return False
    count = 9 if case == "nine_cell_patch" else 0
    expected = {"VV": (-10.0, 6 * count / 100, count / 100), "VH": (-20.0, 0.0, 0.0)}
    for band, (baseline, mean_delta, fraction) in expected.items():
        values = diagnostic["polarizations"][band]
        for actual, desired in [
            (values["baseline_db"]["mean_db"], baseline),
            (values["signed_delta_db"]["mean_db"], mean_delta),
            (values["positive_fraction"], fraction),
            (values["negative_fraction"], 0),
            (values["baseline_range_db"]["mean_db"], 0),
        ]:
            if actual is None or not math.isclose(actual, desired, abs_tol=1e-6):
                return False
        if values["signed_delta_db"]["count"] != 100:
            return False
    return math.isclose(diagnostic["either_fraction"], count / 100, abs_tol=1e-6) and (
        diagnostic["both_fraction"] == 0
    )


def live_checks():
    """Evaluate on EE servers; a failed assertion remains in the saved evidence."""
    started = datetime.now(UTC)
    tag = f"sentinel-numeric-{uuid.uuid4().hex[:16]}"
    ee.data.setWorkloadTag(tag)
    settings = Settings()
    site = Site("numeric-fixture", "Synthetic numeric fixture", 0, 3, 100)
    period = windows("2024-02-05")
    checks = []
    for sensor in ["optical", "radar"]:
        for case, (status, coverage, changed) in CASES.items():
            include_diagnostics = sensor == "radar" and case in {"unchanged", "nine_cell_patch"}
            analyzer = EarthEngineAnalyzer(
                site,
                settings,
                period,
                f"numeric-{sensor}-{case}",
                Path("unused"),
                radar_diagnostics=include_diagnostics,
            )
            analyzer.previews = lambda *args: {}
            collection, items = fixture(analyzer, sensor, case)
            analyzer.compare(sensor, collection, items[:2], items[2:])
            comparison = analyzer.comparisons[0]
            passed = (
                not analyzer.errors
                and comparison["status"] == status
                and math.isclose(comparison["valid_coverage"], coverage, abs_tol=1e-9)
                and (comparison.get("changed_cells") or 0) == changed
            )
            if include_diagnostics:
                passed = passed and diagnostic_matches(comparison, case)
            checks.append(
                {
                    "sensor": sensor,
                    "case": case,
                    "passed": passed,
                    "expected": {
                        "status": status,
                        "valid_coverage": coverage,
                        "changed_cells": changed,
                    },
                    "observed": comparison,
                    "errors": analyzer.errors,
                }
            )
    return {
        "kind": "synthetic live Earth Engine numeric validation",
        "note": (
            "Constant rasters exercise production comparisons; not imagery accuracy or EECU usage."
        ),
        "workload_tag": tag,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "grid": site.grid(),
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }
