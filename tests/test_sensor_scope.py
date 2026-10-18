"""Offline contracts for requested sensor scope, cache identity and source isolation."""

import json
from pathlib import Path
from unittest.mock import patch

import ee
import pytest
from ee.apitestcase import ApiTestCase

from sentinel_monitor.cli import main, parser
from sentinel_monitor.config import (
    Settings,
    Site,
    record_requested_sensors,
    requested_sensors,
    signature,
    windows,
)
from sentinel_monitor.demo import analyze_demo
from sentinel_monitor.earth import EarthEngineAnalyzer

ROOT = Path(__file__).resolve().parents[1]
SITE = Site("fields", "Fields", 48.1, 1.6)
PERIOD = windows("2026-10-12")


def test_default_science_signatures_remain_frozen_and_scopes_are_distinct():
    # Captured from main before the sensor option existed: old cache paths stay valid.
    assert signature(SITE, Settings(), PERIOD, "live") == "5e7257098d5c9f5eedb2"
    assert signature(SITE, Settings(), PERIOD, "demo:change") == "435de0a02fda4afcea3c"
    old = signature(SITE, Settings(), PERIOD, "live")
    for value in ("both", ["optical", "radar"], ["radar", "optical"]):
        assert signature(SITE, Settings(), PERIOD, "live", requested_sensors=value) == old
    keys = {
        signature(SITE, Settings(), PERIOD, "live", requested_sensors=value)
        for value in ("both", "optical", "radar")
    }
    assert len(keys) == 3


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ["optical", "radar"]),
        ("both", ["optical", "radar"]),
        ("optical", ["optical"]),
        ("radar", ["radar"]),
        (["radar", "optical"], ["optical", "radar"]),
        (("optical",), ["optical"]),
    ],
)
def test_sensor_scope_is_canonical(value, expected):
    assert requested_sensors(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "Optical", "thermal", [], ["optical", "optical"], ["thermal"], ["optical", "both"], 1],
)
def test_invalid_or_duplicate_scope_is_rejected(value):
    with pytest.raises(ValueError):
        requested_sensors(value)


@pytest.mark.parametrize(
    "scope,scenario,expected_status,error_sensor",
    [
        ("optical", "sensor-error", "possible_change", None),
        ("radar", "preview-error", "possible_change", None),
        ("radar", "sensor-error", "error", "radar"),
        ("optical", "preview-error", "possible_change", None),
        ("optical", "cloudy", "insufficient_data", None),
    ],
)
def test_demo_scope_does_not_invent_absent_sensor_results(
    tmp_path, scope, scenario, expected_status, error_sensor
):
    result = analyze_demo(
        SITE, Settings(), PERIOD, "synthetic-key", tmp_path, scenario, requested_sensors=scope
    )
    assert [c["sensor"] for c in result["comparisons"]] == [scope]
    entry = result["comparisons"][0]
    assert entry["status"] == expected_status
    absent = "radar" if scope == "optical" else "optical"
    assert result["changed_area"][f"{absent}_m2"] is None
    assert result["changed_area"]["overlap_m2"] is None
    assert [e["sensor"] for e in result["errors"]] == ([error_sensor] if error_sensor else [])
    if scenario == "preview-error" and scope == "optical":
        assert entry["preview_error"] == "SyntheticError"
    else:
        assert "preview_error" not in entry
    assert all(s.startswith("synthetic:") for s in entry["source_ids"])


def demo_arguments(tmp_path, scope="both"):
    return [
        "run",
        "--demo",
        "--sensors",
        scope,
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


def records(tmp_path):
    return list((tmp_path / "results/demo/records").glob("*.json"))


def test_cli_scopes_have_separate_cache_paths_and_record_provenance(tmp_path):
    for scope in ("both", "optical", "radar"):
        assert main(demo_arguments(tmp_path, scope)) == 0
    paths = records(tmp_path)
    assert len(paths) == 3
    values = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    assert len({value["analysis_key"] for value in values}) == 3
    assert {tuple(value["requested_sensors"]) for value in values} == {
        ("optical", "radar"),
        ("optical",),
        ("radar",),
    }
    for value in values:
        assert {c["sensor"] for c in value["comparisons"]} == set(value["requested_sensors"])
    summary = json.loads((tmp_path / "results/run-summary.json").read_text(encoding="utf-8"))
    assert summary["requested_sensors"] == ["radar"]


def test_legacy_record_is_both_and_remains_immutable_on_cache_hit(tmp_path):
    assert main(demo_arguments(tmp_path)) == 0
    path = records(tmp_path)[0]
    value = json.loads(path.read_text(encoding="utf-8"))
    value.pop("requested_sensors")
    path.write_text(json.dumps(value), encoding="utf-8")
    old_bytes = path.read_bytes()
    with patch("sentinel_monitor.demo.analyze_demo", side_effect=AssertionError("cache miss")):
        assert main(demo_arguments(tmp_path)) == 0
    assert path.read_bytes() == old_bytes
    assert main(demo_arguments(tmp_path, "optical")) == 0
    assert path.read_bytes() == old_bytes
    assert len(records(tmp_path)) == 2


def test_cached_scope_metadata_mismatch_is_never_reused(tmp_path):
    assert main(demo_arguments(tmp_path, "optical")) == 0
    path = records(tmp_path)[0]
    value = json.loads(path.read_text(encoding="utf-8"))
    value["requested_sensors"] = ["optical", "radar"]
    value["generated_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert main(demo_arguments(tmp_path, "optical")) == 0
    refreshed = json.loads(path.read_text(encoding="utf-8"))
    assert refreshed["requested_sensors"] == ["optical"]
    assert refreshed["generated_at"] != value["generated_at"]


@pytest.mark.parametrize(
    "command,scope,option",
    [
        ("run", "optical", "--radar-diagnostics"),
        ("run", "radar", "--optical-review-stretch"),
        ("review-case", "optical", "--radar-diagnostics"),
        ("review-case", "radar", "--optical-review-stretch"),
    ],
)
def test_explicit_incompatible_sensor_options_fail_before_service_access(
    tmp_path, command, scope, option
):
    arguments = [
        command,
        "--sensors",
        scope,
        option,
        "--results",
        str(tmp_path / "results"),
        "--output",
        str(tmp_path / "site"),
    ]
    if command == "review-case":
        arguments += ["--case", "gobabeb-quiet-reference"]
    if command == "run" and option == "--optical-review-stretch":
        arguments += ["--review-previews"]
    with patch("sentinel_monitor.earth.initialize") as initialize:
        assert main(arguments) == 1
    initialize.assert_not_called()
    assert not (tmp_path / "results").exists()
    assert not (tmp_path / "site").exists()


@pytest.mark.parametrize("scope,has_radar", [("optical", False), ("both", True), ("radar", True)])
def test_review_case_diagnostics_match_requested_scope(tmp_path, scope, has_radar):
    from sentinel_monitor.validation import review_case

    args = parser().parse_args(
        [
            "review-case",
            "--case",
            "gobabeb-quiet-reference",
            "--sensors",
            scope,
            "--case-file",
            str(ROOT / "validation/cases.json"),
            "--settings",
            str(ROOT / "settings.yaml"),
            "--results",
            str(tmp_path / "results"),
            "--output",
            str(tmp_path / "site"),
        ]
    )
    with patch("sentinel_monitor.cli.main", return_value=0) as invoke:
        assert review_case(args) == 0
    arguments = invoke.call_args.args[0]
    assert arguments[arguments.index("--sensors") + 1] == scope
    assert ("--radar-diagnostics" in arguments) is has_radar
    assert "--review-previews" in arguments


class TestSensorScopedEarthEngineGraphs(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.graphs = []

        def compute(obj):
            self.graphs.append(obj.serialize())
            return {
                "valid_cells": 40000,
                "changed_cells": 9,
                "area": 900,
                "fallback_cells": 0,
                "optical_m2": 900,
                "radar_m2": 900,
                "overlap_m2": 900,
            }

        ee.data.computeValue = compute

    @staticmethod
    def sources():
        from datetime import UTC, datetime

        return [
            {
                "id": f"synthetic:{day}",
                "index": day,
                "day": day,
                "time": int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000),
                "relativeOrbitNumber_start": 1,
                "orbitProperties_pass": "ASCENDING",
            }
            for day in ("2026-09-09", "2026-09-23", "2026-10-10")
        ]

    def analyzer(self, scope, **options):
        analyzer = EarthEngineAnalyzer(
            SITE,
            Settings(),
            PERIOD,
            "scoped-key",
            Path("unused"),
            requested_sensors=scope,
            **options,
        )
        analyzer.metadata = lambda collection: self.sources()
        analyzer.previews = lambda *args: {}
        return analyzer

    def test_optical_only_never_constructs_radar_inventory_terrain_or_prepared_graph(self):
        analyzer = self.analyzer("optical", imagery_diagnostics=True)
        inventory_calls, prepared_graphs = [], []

        def inventory(raw, sensor, period):
            inventory_calls.append((sensor, raw.serialize()))
            return ee.Dictionary({})

        def compare(sensor, prepared, *args):
            prepared_graphs.append((sensor, prepared.serialize()))

        analyzer.compare = compare
        with (
            patch("sentinel_monitor.earth.source_inventory", side_effect=inventory),
            patch.object(analyzer, "terrain", side_effect=AssertionError("radar terrain used")),
            patch.object(
                analyzer, "radar", side_effect=AssertionError("radar prepared graph used")
            ),
        ):
            result = analyzer.analyze()
        assert result["errors"] == []
        assert [sensor for sensor, _ in inventory_calls] == ["optical"]
        assert [sensor for sensor, _ in prepared_graphs] == ["optical"]
        graph = " ".join(graph for _, graph in inventory_calls + prepared_graphs)
        assert "COPERNICUS/S2_SR_HARMONIZED" in graph
        assert "Image.linkCollection" in graph
        assert "COPERNICUS/S1_GRD" not in graph
        assert "Terrain.slope" not in graph
        assert set(result["source_diagnostics"]) == {"optical"}

    def test_optical_only_keeps_existing_detector_math_and_unavailable_aggregates(self):
        scoped = self.analyzer("optical").analyze()
        scoped_graphs = " ".join(self.graphs)
        self.graphs.clear()
        both = self.analyzer("both").analyze()
        assert scoped["errors"] == both["errors"] == []
        optical = next(c for c in both["comparisons"] if c["sensor"] == "optical")
        assert scoped["comparisons"] == [optical]
        assert scoped["changed_area"] == {"optical_m2": 900, "radar_m2": None, "overlap_m2": None}
        for algorithm in (
            "Image.connectedPixelCount",
            "Image.linkCollection",
            "Image.reproject",
            "Image.reduceRegion",
        ):
            assert algorithm in scoped_graphs
        for radar_algorithm in ("Terrain.slope", "Image.exp", "Image.log10", "COPERNICUS/S1_GRD"):
            assert radar_algorithm not in scoped_graphs

    def test_radar_only_does_not_construct_optical_cloud_graph(self):
        analyzer = self.analyzer("radar")
        result = analyzer.analyze()
        assert result["errors"] == []
        assert [c["sensor"] for c in result["comparisons"]] == ["radar"]
        assert result["changed_area"] == {"optical_m2": None, "radar_m2": 900, "overlap_m2": None}
        graph = " ".join(self.graphs)
        assert "Terrain.slope" in graph
        assert "GOOGLE/CLOUD_SCORE_PLUS" not in graph
        assert "COPERNICUS/S2_SR_HARMONIZED" not in graph


def test_review_case_annotation_preserves_retained_other_scope_and_science_records(tmp_path):
    from dataclasses import asdict, replace

    from sentinel_monitor.config import load_config
    from sentinel_monitor.validation import review_case

    case_id = "gobabeb-quiet-reference"
    case = json.loads((ROOT / "validation/cases.json").read_text(encoding="utf-8"))["cases"][
        case_id
    ]
    site, period = Site(**case["site"]), windows(case["end_date"])
    _, settings = load_config(ROOT / "sites.yaml", ROOT / "settings.yaml")
    directory = tmp_path / "results" / case_id / "live" / "records"
    directory.mkdir(parents=True)
    retained = {}
    current = None
    for scope, science in [
        ("both", settings),
        ("optical", replace(settings, optical_threshold=0.2)),
        ("optical", settings),
    ]:
        key = signature(site, science, period, "live", scope)
        path = directory / f"{site.id}-{period['target_end']}-{key}.json"
        record = {
            "mode": "live",
            "site": asdict(site),
            "windows": period,
            "analysis_key": key,
            "requested_sensors": requested_sensors(scope),
            "generated_at": "2026-10-18T00:00:00+00:00",
            "comparisons": [],
        }
        if scope == "both":
            record.pop("requested_sensors")  # Historical BOTH provenance.
        path.write_text(json.dumps(record), encoding="utf-8")
        if scope == "optical" and science == settings:
            current = path
        else:
            retained[path] = path.read_bytes()
    args = parser().parse_args(
        [
            "review-case",
            "--case",
            case_id,
            "--sensors",
            "optical",
            "--case-file",
            str(ROOT / "validation/cases.json"),
            "--settings",
            str(ROOT / "settings.yaml"),
            "--results",
            str(tmp_path / "results"),
            "--output",
            str(tmp_path / "site"),
        ]
    )
    with (
        patch("sentinel_monitor.cli.main", return_value=0),
        patch("sentinel_monitor.reports.build_site"),
    ):
        assert review_case(args) == 0
    for path, original in retained.items():
        assert path.read_bytes() == original
    assert json.loads(current.read_text(encoding="utf-8"))["validation_case"]["id"] == case_id


def test_record_scope_distinguishes_absent_legacy_field_from_api_none_default():
    assert requested_sensors() == requested_sensors(None) == ["optical", "radar"]
    assert record_requested_sensors({}) == ["optical", "radar"]
    for scope in (["optical"], ["radar"], ["optical", "radar"]):
        assert record_requested_sensors({"requested_sensors": scope}) == scope


@pytest.mark.parametrize(
    "value",
    [
        None,
        "both",
        "optical",
        [],
        ["optical", "optical"],
        {},
        ["radar", "optical"],
        ["optical", "thermal"],
    ],
)
def test_explicit_malformed_record_scope_is_invalid(value):
    with pytest.raises(ValueError):
        record_requested_sensors({"requested_sensors": value})


@pytest.mark.parametrize("scope", ["both", "optical", "radar"])
@pytest.mark.parametrize(
    "value",
    [None, "both", [], ["optical", "optical"], {}, ["radar", "optical"], ["optical", "thermal"]],
)
def test_explicit_malformed_cache_scope_recomputes_instead_of_becoming_legacy(
    tmp_path, scope, value
):
    assert main(demo_arguments(tmp_path, scope)) == 0
    path = records(tmp_path)[0]
    cached = json.loads(path.read_text(encoding="utf-8"))
    cached["requested_sensors"] = value
    cached["generated_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(json.dumps(cached), encoding="utf-8")
    with patch("sentinel_monitor.demo.analyze_demo", wraps=analyze_demo) as analyze:
        assert main(demo_arguments(tmp_path, scope)) == 0
    analyze.assert_called_once()
    refreshed = json.loads(path.read_text(encoding="utf-8"))
    assert refreshed["requested_sensors"] == requested_sensors(scope)
    assert refreshed["generated_at"] != cached["generated_at"]
