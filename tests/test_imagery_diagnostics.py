"""Offline diagnostics tests: real EE graphs, synthetic response data, no live requests."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import ee
import pytest
from ee.apitestcase import ApiTestCase

from sentinel_monitor.cli import main, parser
from sentinel_monitor.config import Settings, Site, windows
from sentinel_monitor.diagnostics import group_eligibility, optical_summary, source_inventory
from sentinel_monitor.earth import EarthEngineAnalyzer
from sentinel_monitor.reports import read_records
from sentinel_monitor.validation import review_case

ROOT = Path(__file__).resolve().parents[1]
PERIOD = windows("2022-07-18")
SITE = Site("fixture", "Synthetic fixture", 0, 3, 100)


def sources():
    return [
        {
            "id": f"synthetic:{day}",
            "index": day,
            "day": day,
            "time": index + 1,
            "relativeOrbitNumber_start": 1,
            "orbitProperties_pass": "ASCENDING",
        }
        for index, day in enumerate(("2022-06-13", "2022-06-18", "2022-07-13"))
    ]


def test_group_eligibility_keeps_days_datatakes_and_unmatched_orbits_separate():
    items = sources()
    target = dict(items[-1], id="synthetic:slice", radar_datatake=7, platform="A")
    items[-1].update(radar_datatake=7, platform="A")
    other = dict(target, id="synthetic:second", radar_datatake=8)
    groups = {
        (1, "ASCENDING"): items + [target, other],
        (2, "DESCENDING"): items[:2],
        (3, "ASCENDING"): [target],
        (4, "ASCENDING"): [items[0], dict(items[0], id="synthetic:overlap"), target],
    }
    result = group_eligibility(groups, PERIOD["target_start"], 2)
    assert [r["eligibility"] for r in result] == [
        "metadata_eligible",
        "no_target_acquisitions",
        "insufficient_baseline_days",
        "insufficient_baseline_days",
    ]
    assert result[0]["target_acquisitions"] == 2
    assert len(result[0]["target_source_ids"]) == 3
    assert result[0]["baseline_acquisition_dates"] == ["2022-06-13", "2022-06-18"]
    assert group_eligibility({}, PERIOD["target_start"], 2) == []


def test_optical_output_keeps_units_band_identity_and_missing_statistics():
    result = optical_summary(
        {
            "before_B4_mean": 0.4,
            "after_B4_count": 100,
            "after_B4_max": 0.5,
            "mean_abs_difference_p95": 0.08,
            "after_high_B4_mean": 1.0,
            "before_low_B2_mean": 0.2,
        },
        ["B2", "B3", "B4", "B8"],
    )
    assert result["baseline"]["B4"]["mean"] == 0.4
    assert result["target"]["B4"]["count"] == 100
    assert result["target"]["B4"]["max"] == 0.5
    assert result["target"]["B2"]["mean"] is None
    assert result["mean_absolute_difference"]["p95"] == 0.08
    assert result["display_endpoint_fractions"]["after"]["B4"]["at_or_above_max"] == 1
    assert result["display_endpoint_fractions"]["before"]["B2"]["at_or_below_min"] == 0.2
    assert result["display_stretch"] == {
        "bands": ["B4", "B3", "B2"],
        "min": 0,
        "max": 0.3,
        "gamma": 1.2,
    }


class TestImageryDiagnosticGraphs(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.graphs = []
        self.stats = {"valid_cells": 100, "changed_cells": 9, "area": 900}
        self.diagnostics = {
            "masks": {
                "target_valid_cells": 100,
                "baseline_eligible_cells": 100,
                "threshold_cells": 12,
            },
            "optical": {"before_B4_mean": 0.4, "after_high_B4_mean": 1.0},
        }
        self.inventory = {
            window: {
                "stage_counts": {"intersecting": 0, "IW": 0, "VV": 0, "VH": 0},
                "exclusions": {},
            }
            for window in ("baseline", "target")
        }
        self.fail_diagnostic = False
        self.fail_inventory = False

        def compute(obj):
            graph = obj.serialize()
            self.graphs.append(graph)
            if '"stage_counts"' in graph:
                if self.fail_inventory:
                    raise ee.EEException(
                        "Inventory error access_token=secret https://test.invalid/x"
                    )
                return self.inventory
            if '"masks"' in graph:
                if self.fail_diagnostic:
                    raise ee.EEException("Optical diagnostic request failed")
                return self.diagnostics
            return self.stats

        ee.data.computeValue = compute

    def analyzer(self, enabled=True, items=None):
        analyzer = EarthEngineAnalyzer(
            SITE, Settings(), PERIOD, "synthetic-key", Path("unused"), imagery_diagnostics=enabled
        )
        analyzer.metadata = lambda collection: sources() if items is None else items
        analyzer.previews = lambda *args: {"before": "synthetic.png"}
        return analyzer

    def test_inventory_is_one_bounded_request_before_pixel_preprocessing(self):
        value = source_inventory(ee.ImageCollection("COPERNICUS/S1_GRD"), "radar", PERIOD)
        graph = value.serialize()
        for key in (
            "instrumentMode",
            "transmitterReceiverPolarisation",
            "relative_orbit",
            "examples_truncated",
            "baseline",
            "target",
            "IW",
            "VV",
            "VH",
        ):
            assert key in graph
        assert '"count": {"constantValue": 10}' in graph
        assert "Filter.not" in graph
        assert "Image.select" not in graph and "Image.reduceRegion" not in graph
        assert "2022-06-13" in graph and "2022-07-11" in graph and "2022-07-18" in graph
        assert (
            "Image.linkCollection"
            not in source_inventory(
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED"), "optical", PERIOD
            ).serialize()
        )

    def test_enabled_graphs_keep_science_and_original_previews_unchanged(self):
        ordinary = self.analyzer(enabled=False)
        ordinary.sensor("optical")
        original = copy.deepcopy(ordinary.comparisons[0])
        original_summary_graph = self.graphs[-1]
        self.graphs.clear()
        diagnostic = self.analyzer()
        diagnostic.sensor("optical")
        entry = copy.deepcopy(diagnostic.comparisons[0])
        values = entry.pop("imagery_diagnostics")
        assert entry == original
        assert self.graphs[1] == original_summary_graph
        assert values["common_valid_cells"] == 100 and values["patch_cells"] == 9
        assert values["threshold_cells"] == 12
        assert values["target_valid_cells"] == 100 and values["baseline_eligible_cells"] == 100
        assert values["optical"]["baseline"]["B4"]["mean"] == 0.4
        assert (
            values["optical"]["display_endpoint_fractions"]["after"]["B4"]["at_or_above_max"] == 1
        )
        graph = self.graphs[2]
        for operation in (
            "Image.abs",
            "Image.subtract",
            "Image.updateMask",
            "Reducer.count",
            "Reducer.minMax",
            "Reducer.percentile",
            "Image.gte",
            "Image.lte",
        ):
            assert operation in graph
        assert '"maxPixels": {"constantValue": 4200}' in graph  # 21 bands, no coarsening.
        assert '"maxPixels": {"constantValue": 600}' in graph  # Three mask bands.
        assert "bestEffort" not in graph and "crsTransform" in graph
        assert diagnostic.errors == []

    def test_enabled_radar_keeps_the_same_science_graph_and_uses_only_mask_diagnostics(self):
        ordinary = self.analyzer(enabled=False)
        ordinary.sensor("radar")
        original = copy.deepcopy(ordinary.comparisons[0])
        original_graph = self.graphs[-1]
        self.graphs.clear()
        self.diagnostics.pop("optical")
        diagnostic = self.analyzer()
        diagnostic.sensor("radar")
        entry = copy.deepcopy(diagnostic.comparisons[0])
        values = entry.pop("imagery_diagnostics")
        assert entry == original and self.graphs[1] == original_graph
        assert values["threshold_units"] == "dB" and values["threshold"] == 3
        assert values["threshold_cells"] == 12 and "optical" not in values
        assert "Reducer.percentile" not in self.graphs[-1]
        assert (
            diagnostic.source_diagnostics["radar"]["groups"][0]["eligibility"]
            == "metadata_eligible"
        )

    def test_empty_radar_has_source_evidence_and_no_negative_comparison(self):
        analyzer = self.analyzer(items=[])
        analyzer.sensor("radar")
        assert analyzer.comparisons == [] and analyzer.masks == {}
        diagnostic = analyzer.source_diagnostics["radar"]
        assert diagnostic["windows"] == self.inventory
        assert diagnostic["eligible_metadata_complete"] is True
        assert diagnostic["eligible_source_count"] == 0 and diagnostic["groups"] == []
        assert len(self.graphs) == 1

    def test_orbit_mismatch_records_metadata_gap_without_pixel_reduction(self):
        items = sources()
        items[-1]["relativeOrbitNumber_start"] = 2
        analyzer = self.analyzer(items=items)
        analyzer.sensor("radar")
        assert analyzer.comparisons[0]["status"] == "insufficient_data"
        assert "not_evaluated_reason" in analyzer.comparisons[0]["imagery_diagnostics"]
        assert len(self.graphs) == 1
        assert [g["eligibility"] for g in analyzer.source_diagnostics["radar"]["groups"]] == [
            "no_target_acquisitions",
            "insufficient_baseline_days",
        ]

    def test_low_coverage_keeps_subset_counts_without_accepted_change(self):
        self.stats["valid_cells"] = 60
        analyzer = self.analyzer()
        analyzer.previews = lambda *args: pytest.fail("No imagery for insufficient coverage")
        analyzer.sensor("optical")
        entry = analyzer.comparisons[0]
        assert entry["status"] == "insufficient_data" and "changed_cells" not in entry
        assert entry["imagery_diagnostics"]["patch_cells"] == 9
        assert entry["imagery_diagnostics"]["common_valid_cells"] == 60
        assert analyzer.masks == {}

    def test_empty_common_mask_reports_validity_without_optical_distributions(self):
        self.stats.update(valid_cells=0, changed_cells=0)
        self.diagnostics.pop("optical")
        analyzer = self.analyzer()
        analyzer.sensor("optical")
        entry = analyzer.comparisons[0]
        assert entry["status"] == "insufficient_data"
        assert entry["imagery_diagnostics"]["optical_unavailable_reason"] == "No common valid cells"
        assert "Reducer.percentile" not in self.graphs[-1]
        assert entry["imagery_diagnostics"]["common_valid_cells"] == 0

    def test_request_failures_preserve_measurements_previews_and_sanitized_evidence(self):
        self.fail_inventory = self.fail_diagnostic = True
        analyzer = self.analyzer()
        analyzer.sensor("optical")
        entry = analyzer.comparisons[0]
        assert entry["status"] == "possible_change" and entry["changed_cells"] == 9
        assert entry["previews"]["before"] == "synthetic.png" and "optical" in analyzer.masks
        assert len(analyzer.errors) == 2
        assert analyzer.source_diagnostics["optical"]["eligible_metadata_complete"] is True
        assert "secret" not in json.dumps(analyzer.errors) and "test.invalid" not in json.dumps(
            analyzer.errors
        )
        assert (
            entry["imagery_diagnostics"]["error"]["message"] == "Optical diagnostic request failed"
        )


def test_imagery_diagnostics_upgrade_cache_retry_failure_and_export(tmp_path):
    result = {
        "comparisons": [],
        "errors": [],
        "changed_area": {"optical_m2": None, "radar_m2": None, "overlap_m2": None},
        "newest_observation": None,
        "workload_tag": "synthetic-test",
    }
    args = [
        "run",
        "--sites",
        str(ROOT / "tests" / "fixtures" / "sites.yaml"),
        "--settings",
        str(ROOT / "settings.yaml"),
        "--end-date",
        "2022-07-18",
        "--results",
        str(tmp_path / "results"),
        "--output",
        str(tmp_path / "site"),
    ]
    with (
        patch("sentinel_monitor.earth.initialize"),
        patch.object(EarthEngineAnalyzer, "__init__", return_value=None) as initialize,
        patch.object(EarthEngineAnalyzer, "analyze", return_value=result) as analyze,
    ):
        assert main(args) == 0
        first = read_records(tmp_path / "results", "live")[0]
        failed = copy.deepcopy(result)
        failed["errors"] = [
            {
                "sensor": "radar",
                "stage": "imagery source diagnostics",
                "error": "EEException",
                "message": "synthetic failure",
            }
        ]
        analyze.return_value = failed
        assert main([*args, "--imagery-diagnostics"]) == 2
        assert initialize.call_args.kwargs["imagery_diagnostics"] is True
        complete = copy.deepcopy(result)
        complete["source_diagnostics"] = {"radar": {"synthetic": True}}
        analyze.return_value = complete
        assert main([*args, "--imagery-diagnostics"]) == 0  # Retry partial failure.
        assert main([*args, "--imagery-diagnostics"]) == 0  # Cache complete evidence.
        assert analyze.call_count == 3
    record = read_records(tmp_path / "results", "live")[0]
    assert record["analysis_key"] == first["analysis_key"]
    assert record["imagery_diagnostics_requested"] is True
    assert json.loads((tmp_path / "site/history.json").read_text())[0]["source_diagnostics"] == {
        "radar": {"synthetic": True}
    }
    assert len(list((tmp_path / "results/live/records").glob("*.json"))) == 1


def test_review_case_forwards_explicit_flag_only_and_demo_rejects_it(tmp_path):
    base = [
        "review-case",
        "--case",
        "gobabeb-quiet-reference",
        "--case-file",
        str(ROOT / "validation/cases.json"),
        "--settings",
        str(ROOT / "settings.yaml"),
        "--results",
        str(tmp_path / "results"),
        "--output",
        str(tmp_path / "site"),
    ]
    for flags in ([], ["--imagery-diagnostics"]):
        args = parser().parse_args([*base, *flags])
        with patch("sentinel_monitor.cli.main", return_value=2) as invoke:
            assert review_case(args) == 2
        assert ("--imagery-diagnostics" in invoke.call_args.args[0]) == bool(flags)
        manifest = json.loads(
            (tmp_path / "site/gobabeb-quiet-reference/validation-case.json").read_text()
        )
        assert manifest["imagery_diagnostics_requested"] == bool(flags)
    assert main(["run", "--demo", "--imagery-diagnostics"]) == 1
