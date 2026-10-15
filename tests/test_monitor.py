import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import ee
import pytest
from ee.apitestcase import ApiTestCase

from sentinel_monitor.cli import main
from sentinel_monitor.config import Settings, Site, signature, windows
from sentinel_monitor.decisions import comparison_status, detection_id, location_status
from sentinel_monitor.demo import patch_cells
from sentinel_monitor.earth import EarthEngineAnalyzer, error_details, retry
from sentinel_monitor.reports import build_site, read_records

ROOT = Path(__file__).resolve().parents[1]
SITE = Site("fields", "Fields", 48.1, 1.6)
PERIOD = windows("2026-10-12")


@pytest.mark.parametrize(
    "latitude,longitude,size",
    [
        (91, 1, 2000),
        (0, 181, 2000),
        (float("nan"), 0, 2000),
        (0, 0, 2001),
        (True, 0, 2000),
        (0, 0, 20),
    ],
)
def test_invalid_site(latitude, longitude, size):
    with pytest.raises(ValueError):
        Site("bad", "Bad", latitude, longitude, size)


@pytest.mark.parametrize(
    "latitude,longitude,crs",
    [
        (48.1, 1.6, "EPSG:32631"),
        (-33, 151, "EPSG:32756"),
        (85, 15, "EPSG:32661"),
        (-85, 15, "EPSG:32761"),
        (0, 180, "EPSG:32660"),
    ],
)
def test_metric_square_and_grid(latitude, longitude, crs):
    site = Site("grid", "Grid", latitude, longitude, 2000)
    grid = site.grid()
    left, bottom, right, top = grid["bounds"]
    assert grid["crs"] == crs
    assert right - left == top - bottom == 2000
    assert grid["cells"] == 40000
    assert grid["transform"] == [10, 0, left, 0, -10, top]
    assert site.grid() == grid


def test_complete_nonoverlapping_utc_windows():
    assert PERIOD == {
        "baseline_start": "2026-09-07",
        "baseline_end": "2026-10-05",
        "target_start": "2026-10-05",
        "target_end": "2026-10-12",
    }
    with pytest.raises(ValueError):
        windows("2099-01-01")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_valid_coverage": 1.1},
        {"optical_threshold": float("nan")},
        {"min_baseline_observations": 1},
        {"max_sites": 201},
        {"min_patch_pixels": True},
        {"radar_min_angle": 70},
    ],
)
def test_settings_reject_invalid_thresholds(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_detection_ids_stable_but_science_changes_invalidate_cache():
    key = signature(SITE, Settings(), PERIOD, "live")
    assert detection_id("fields", "optical", ["b", "a"], key) == detection_id(
        "fields", "optical", ["a", "b"], key
    )
    assert key != signature(SITE, replace(Settings(), optical_threshold=0.2), PERIOD, "live")
    assert key != signature(SITE, Settings(), PERIOD, "demo")
    assert key == signature(SITE, replace(Settings(), max_sites=20), PERIOD, "live")


def test_coverage_decisions_and_partial_failure():
    assert comparison_status(40000, 40000, 0, 0.7)[0] == "no_change_detected"
    assert comparison_status(28000, 40000, 9, 0.7)[0] == "possible_change"
    assert comparison_status(27999, 40000, 9, 0.7)[0] == "insufficient_data"
    assert comparison_status(0, 40000, 0, 0.7)[0] == "insufficient_data"
    assert location_status([], []) == "insufficient_data"
    assert location_status([{"status": "no_change_detected"}], [{"sensor": "radar"}]) == "error"
    assert (
        location_status([{"status": "possible_change"}], [{"sensor": "radar"}]) == "possible_change"
    )


def test_synthetic_patch_fixture_uses_eight_connected_cells():
    nine = {(x, y) for x in range(3) for y in range(3)}
    assert patch_cells(nine | {(9, 9)}, 9) == nine
    assert patch_cells(nine - {(0, 0)}, 9) == set()
    assert len(patch_cells({(x, x) for x in range(9)}, 9)) == 9


def demo_run(results, output, *extra):
    return main(
        [
            "run",
            "--sites",
            str(ROOT / "sites.yaml"),
            "--settings",
            str(ROOT / "settings.yaml"),
            "--results",
            str(results),
            "--output",
            str(output),
            "--demo",
            "--end-date",
            "2026-10-12",
            *extra,
        ]
    )


def test_demo_roundtrip_preserves_history_and_deduplicates(tmp_path):
    results, output = tmp_path / "results", tmp_path / "site"
    assert demo_run(results, output) == 0
    records = read_records(results, "demo")
    assert records[0]["status"] == "possible_change"
    assert records[0]["changed_area"]["overlap_m2"] == 900
    assert len(list(output.rglob("*.png"))) == 6
    assert "DEMO — SYNTHETIC DATA" in (output / "index.html").read_text(encoding="utf-8")
    assert demo_run(results, output) == 0
    assert len(read_records(results, "demo")) == 1
    assert demo_run(results, output, "--end-date", "2026-10-05", "--demo-scenario", "quiet") == 0
    records = read_records(results, "demo")
    assert len(records) == 2
    latest = json.loads((output / "latest.json").read_text(encoding="utf-8"))
    assert latest[0]["windows"]["target_end"] == "2026-10-12"
    assert records[1]["status"] == "no_change_detected"


def test_missing_data_demo_and_mode_isolation(tmp_path):
    results, output = tmp_path / "results", tmp_path / "site"
    assert demo_run(results, output, "--demo-scenario", "cloudy") == 0
    record = read_records(results, "demo")[0]
    assert record["status"] == "insufficient_data"
    assert record["usable_sensors"] == []
    assert not list(output.rglob("*.png"))
    assert read_records(results, "live") == []
    with pytest.raises(ValueError, match="mode"):
        build_site(results, output, "live")


def test_report_escapes_location_names(tmp_path):
    results, output = tmp_path / "results", tmp_path / "site"
    assert demo_run(results, output) == 0
    record_path = next((results / "demo" / "records").glob("*.json"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["site"]["name"] = '<script>alert("unsafe")</script>'
    record_path.write_text(json.dumps(record), encoding="utf-8")
    build_site(results, output, "demo")
    html = (output / "index.html").read_text(encoding="utf-8")
    assert '<script>alert("unsafe")</script>' not in html
    assert "&lt;script&gt;" in html


def test_retry_only_retries_transient_failures():
    attempts = []

    def operation():
        attempts.append(1)
        if len(attempts) < 3:
            raise TimeoutError()
        return "done"

    with patch("sentinel_monitor.earth.time.sleep"):
        assert retry(operation, 3) == "done"
    assert len(attempts) == 3
    with pytest.raises(ValueError):
        retry(lambda: (_ for _ in ()).throw(ValueError("invalid configuration")), 3)


class TestEarthEngineGraphs(ApiTestCase):
    """Build real EE expression graphs offline; server reductions are fixture results."""

    def setUp(self):
        super().setUp()
        self.graphs = []
        self.statistics = {
            "valid_cells": 40000,
            "changed_cells": 9,
            "area": 900,
            "fallback_cells": 0,
            "optical_m2": 900,
            "radar_m2": 900,
            "overlap_m2": 900,
        }

        def compute(obj):
            self.graphs.append(obj.serialize())
            return self.statistics

        ee.data.computeValue = compute

    def analyzer(self, tmp_path):
        analyzer = EarthEngineAnalyzer(SITE, Settings(), PERIOD, "test-key", tmp_path)
        analyzer.previews = lambda *args: {}
        return analyzer

    def sources(self, sensor, mismatch=False):
        sources = []
        for day in ["2026-09-09", "2026-09-23", "2026-10-10"]:
            sources.append(
                {
                    "id": f"synthetic:{sensor}:{day}",
                    "index": day,
                    "day": day,
                    "time": int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000),
                    "relativeOrbitNumber_start": 2 if mismatch and day == "2026-10-10" else 1,
                    "orbitProperties_pass": "ASCENDING",
                }
            )
        return sources

    def test_full_graphs_have_grid_masks_cloud_join_power_and_patch_operations(self):
        analyzer = self.analyzer(Path("unused"))
        analyzer.metadata = lambda collection: self.sources("both")
        result = analyzer.analyze()
        assert result["errors"] == [], result["errors"]
        assert len(result["comparisons"]) == 2
        assert all(c["status"] == "possible_change" for c in result["comparisons"])
        graph = " ".join(self.graphs)
        for algorithm in [
            "Image.connectedPixelCount",
            "Image.exp",
            "Image.log10",
            "Terrain.slope",
            "Image.reproject",
            "Image.reduceRegion",
            "Image.linkCollection",
        ]:
            assert algorithm in graph
        assert "EPSG:32631" in graph
        assert "crsTransform" in graph
        assert result["changed_area"]["overlap_m2"] == 900

    def test_orbit_mismatch_has_no_computation_or_negative_detection(self):
        analyzer = self.analyzer(Path("unused"))
        analyzer.metadata = lambda collection: self.sources("radar", mismatch=True)
        analyzer.sensor("radar")
        assert len(analyzer.comparisons) == 1
        assert analyzer.comparisons[0]["status"] == "insufficient_data"
        assert analyzer.comparisons[0]["baseline_observations"] == 0
        assert self.graphs == []

    def test_low_coverage_rejects_candidate_and_does_not_make_previews(self):
        analyzer = self.analyzer(Path("unused"))
        analyzer.metadata = lambda collection: self.sources("optical")
        self.statistics["valid_cells"] = 5000
        analyzer.previews = lambda *args: pytest.fail("No previews for insufficient data")
        analyzer.sensor("optical")
        assert analyzer.comparisons[0]["status"] == "insufficient_data"
        assert analyzer.masks == {}

    def test_quiet_reduction_is_not_a_candidate(self):
        analyzer = self.analyzer(Path("unused"))
        analyzer.metadata = lambda collection: self.sources("optical")
        self.statistics["changed_cells"] = 0
        self.statistics["area"] = 0
        analyzer.previews = lambda *args: pytest.fail("No previews for quiet observations")
        analyzer.sensor("optical")
        assert analyzer.comparisons[0]["status"] == "no_change_detected"

    def test_overlapping_granules_are_one_baseline_observation(self):
        analyzer = self.analyzer(Path("unused"))
        sources = self.sources("optical")
        sources[1]["day"] = sources[0]["day"]
        analyzer.metadata = lambda collection: sources
        analyzer.sensor("optical")
        assert analyzer.comparisons[0]["baseline_observations"] == 1
        assert analyzer.comparisons[0]["status"] == "insufficient_data"
        assert self.graphs == []

    def test_sensor_error_preserves_other_sensor_detection(self):
        analyzer = self.analyzer(Path("unused"))
        original = analyzer.sensor
        analyzer.metadata = lambda collection: self.sources("optical")

        def sensor(name):
            if name == "radar":
                raise TimeoutError()
            return original(name)

        analyzer.sensor = sensor
        result = analyzer.analyze()
        assert result["errors"] == [
            {"sensor": "radar", "error": "TimeoutError", "message": "TimeoutError"}
        ]
        assert location_status(result["comparisons"], result["errors"]) == "possible_change"

    def test_distinct_same_day_acquisitions_are_each_evaluated(self):
        analyzer = self.analyzer(Path("unused"))
        sources = self.sources("optical")
        additional = dict(sources[-1])
        additional.update(id="synthetic:second", index="second", time=additional["time"] + 3600000)
        sources.append(additional)
        analyzer.metadata = lambda collection: sources
        analyzer.sensor("optical")
        assert len(analyzer.comparisons) == 2
        assert len({c["id"] for c in analyzer.comparisons}) == 2

    def test_slices_of_same_datatake_are_one_target_comparison(self):
        analyzer = self.analyzer(Path("unused"))
        sources = self.sources("radar")
        sources[-1].update(radar_datatake=77, platform="A")
        additional = dict(sources[-1])
        additional.update(id="synthetic:slice", index="slice", time=additional["time"] + 10000)
        sources.append(additional)
        analyzer.metadata = lambda collection: sources
        analyzer.sensor("radar")
        assert len(analyzer.comparisons) == 1
        assert len(analyzer.comparisons[0]["source_ids"]) == 2

    def test_service_error_message_is_preserved_and_comparison_continues(self):
        analyzer = self.analyzer(Path("unused"))
        sources = self.sources("optical")
        additional = dict(sources[-1])
        additional.update(id="second", index="second", time=additional["time"] + 3600000)
        analyzer.metadata = lambda collection: sources + [additional]
        message = "Image.reduceRegion: server rejected the comparison"

        def compute(obj):
            raise ee.EEException(message)

        ee.data.computeValue = compute
        analyzer.sensor("optical")
        assert len(analyzer.comparisons) == 2
        assert all(c["status"] == "error" for c in analyzer.comparisons)
        assert all(message in c["reason"] for c in analyzer.comparisons)
        assert all(
            e["message"] == message and e["stage"] == "reduce comparison" for e in analyzer.errors
        )
        assert analyzer.masks == {}


def test_service_diagnostics_redact_credentials_and_signed_urls():
    message = error_details(
        ee.EEException(
            'API error access_token="secret123" refresh_token=secret456 '
            "Authorization: Bearer abc.def.ghi https://example.test/preview?token=secret789"
        )
    )["message"]
    assert "API error" in message
    for secret in ["secret123", "secret456", "abc.def.ghi", "secret789", "secret-key-data"]:
        assert secret not in message


def test_live_failure_exports_diagnostic_summary_and_returns_nonzero(tmp_path):
    diagnostic = {"sensor": "radar", "error": "EEException", "message": "Image error detail"}
    result = {
        "comparisons": [],
        "errors": [diagnostic],
        "changed_area": {"optical_m2": None, "radar_m2": None, "overlap_m2": None},
        "newest_observation": None,
        "workload_tag": "test",
    }
    with (
        patch("sentinel_monitor.earth.initialize"),
        patch.object(EarthEngineAnalyzer, "__init__", return_value=None),
        patch.object(EarthEngineAnalyzer, "analyze", return_value=result),
    ):
        status = main(
            [
                "run",
                "--sites",
                str(ROOT / "sites.yaml"),
                "--settings",
                str(ROOT / "settings.yaml"),
                "--end-date",
                "2026-10-12",
                "--results",
                str(tmp_path / "results"),
                "--output",
                str(tmp_path / "site"),
            ]
        )
    assert status == 2
    summary = json.loads((tmp_path / "results/run-summary.json").read_text(encoding="utf-8"))
    assert summary["sites"][0]["errors"] == [diagnostic]
    assert "Image error detail" in (tmp_path / "site/index.html").read_text(encoding="utf-8")


class TestReductionPixelBudget(ApiTestCase):
    def test_four_band_live_summary_fits_without_coarsening_the_grid(self):
        analyzer = EarthEngineAnalyzer(
            Site("engels", "Engels", 51.480499, 46.215, 2000),
            Settings(),
            PERIOD,
            "budget-test",
            Path("unused"),
        )
        image = ee.Image.constant([1, 0, 0, 0]).rename(
            ["valid_cells", "changed_cells", "area", "fallback_cells"]
        )
        with patch.object(ee.Image, "reduceRegion", return_value=ee.Dictionary({})) as reduce:
            analyzer.reduce(image)
        options = reduce.call_args.kwargs
        # The live server rejected 160,000 band-pixels against the old 40,100 cap.
        assert options["maxPixels"] >= 160000
        assert options["maxPixels"] < 200000
        assert options["crs"] == "EPSG:32638"
        assert options["crsTransform"] == [10, 0, 583370, 0, -10, 5704960]
        assert "bestEffort" not in options
        assert "scale" not in options
