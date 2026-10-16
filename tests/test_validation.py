"""Validation harness tests are offline; server numeric outcomes remain an explicit gate."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from ee.apitestcase import ApiTestCase

from sentinel_monitor.cli import main
from sentinel_monitor.config import Settings, Site, windows
from sentinel_monitor.earth import EarthEngineAnalyzer
from sentinel_monitor.validation import diagnostic_matches, fixture

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("scenario", ["sensor-error", "preview-error"])
def test_synthetic_failure_is_labelled_separate_and_retried(tmp_path, scenario):
    arguments = [
        "run",
        "--demo",
        "--demo-scenario",
        scenario,
        "--end-date",
        "2026-10-12",
        "--sites",
        str(ROOT / "sites.yaml"),
        "--settings",
        str(ROOT / "settings.yaml"),
        "--results",
        str(tmp_path / "results"),
        "--output",
        str(tmp_path / "site"),
    ]
    for _ in range(2):
        assert main(arguments) == 2
    paths = list((tmp_path / "results/demo/records").glob("*.json"))
    assert len(paths) == 1
    assert not (tmp_path / "results/live").exists()
    record = json.loads(paths[0].read_text())
    assert record["has_errors"] is True and record["status"] == "possible_change"
    assert "DEMO — SYNTHETIC DATA" in (tmp_path / "site/index.html").read_text(encoding="utf-8")
    if scenario == "sensor-error":
        assert record["usable_sensors"] == ["optical"]
        assert record["changed_area"]["radar_m2"] is None
        assert record["changed_area"]["overlap_m2"] is None
    else:
        assert record["usable_sensors"] == ["optical", "radar"]
        assert "previews" not in record["comparisons"][0]
        assert record["comparisons"][0]["preview_error"] == "SyntheticError"


@pytest.mark.parametrize("passed,exit_code", [(True, 0), (False, 2)])
def test_live_numeric_cli_saves_success_or_failed_evidence(tmp_path, passed, exit_code):
    output = tmp_path / "numeric.json"
    evidence = {"passed": passed, "checks": [{"passed": passed}], "workload_tag": "test"}
    with (
        patch("sentinel_monitor.earth.initialize") as initialize,
        patch("sentinel_monitor.validation.live_checks", return_value=evidence),
    ):
        assert (
            main(["validate-live", "--project", "baseviewer-511722", "--output", str(output)])
            == exit_code
        )
    initialize.assert_called_once_with("baseviewer-511722")
    assert json.loads(output.read_text()) == evidence


def test_numeric_expectations_reject_swapped_polarizations_and_missing_data():
    values = {
        "radar_diagnostics": {
            "polarizations": {
                band: {
                    "baseline_db": {"mean_db": baseline},
                    "signed_delta_db": {"mean_db": 0, "count": 100},
                    "positive_fraction": 0,
                    "negative_fraction": 0,
                    "baseline_range_db": {"mean_db": 0},
                }
                for band, baseline in [("VV", -10), ("VH", -20)]
            },
            "either_fraction": 0,
            "both_fraction": 0,
        },
    }
    assert diagnostic_matches(values, "unchanged")
    swapped = copy.deepcopy(values)
    bands = swapped["radar_diagnostics"]["polarizations"]
    bands["VV"], bands["VH"] = bands["VH"], bands["VV"]
    assert not diagnostic_matches(swapped, "unchanged")
    values["radar_diagnostics"]["polarizations"]["VV"]["signed_delta_db"]["count"] = 99
    assert not diagnostic_matches(values, "unchanged")


class TestNumericFixtureGraphs(ApiTestCase):
    def test_fixture_graphs_use_a_hundred_cell_grid_and_required_masks(self):
        for sensor in ["optical", "radar"]:
            analyzer = EarthEngineAnalyzer(
                Site("fixture", "Fixture", 0, 3, 100),
                Settings(),
                windows("2024-02-05"),
                "fixture",
                Path("unused"),
            )
            for case in [
                "unchanged",
                "nine_cell_patch",
                "one_cell_patch",
                "diagonal_patch",
                "missing_target",
                "one_valid_baseline",
            ]:
                collection, items = fixture(analyzer, sensor, case)
                graph = collection.serialize()
                assert "Image.reproject" in graph
                if "patch" in case:
                    assert "Image.pixelCoordinates" in graph
                if case in {"missing_target", "one_valid_baseline"}:
                    assert "Image.updateMask" in graph
                assert len(items) == 3
                assert analyzer.grid["cells"] == 100
