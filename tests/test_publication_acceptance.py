"""Controlled publication bundles: mocked service outcomes, real HTML/JSON/PNG over HTTP."""

import copy
import json
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

import pytest
from PIL import Image

from sentinel_monitor.cli import main
from sentinel_monitor.earth import EarthEngineAnalyzer
from sentinel_monitor.reports import read_records

ROOT = Path(__file__).resolve().parents[1]


def outcome(status="no_change_detected", *, sensor_error=False, preview_error=False):
    comparison = {
        "id": "controlled-fixture",
        "sensor": "optical",
        "acquisition_date": "2026-10-10",
        "acquisition_times": ["2026-10-10T00:00:00+00:00"],
        "baseline_acquisition_dates": ["2026-09-09", "2026-09-23"],
        "baseline_observations": 2,
        "source_ids": ["synthetic:target"],
        "baseline_source_ids": ["synthetic:before"],
        "status": status,
        "valid_coverage": 1,
        "changed_cells": 9 if status == "possible_change" else 0,
        "changed_area_m2": 900 if status == "possible_change" else 0,
    }
    if status == "possible_change":
        if preview_error:
            comparison.update(
                preview_error="HTTPError", preview_error_message="Fixture preview failed"
            )
        else:
            comparison["previews"] = {
                name: f"assets/controlled-fixture/{name}.png"
                for name in ["before", "after", "overlay"]
            }
    return {
        "comparisons": [comparison],
        "errors": (
            [{"sensor": "radar", "error": "EEException", "message": "Fixture radar failed"}]
            if sensor_error
            else []
        ),
        "changed_area": {
            "optical_m2": comparison["changed_area_m2"],
            "radar_m2": None,
            "overlap_m2": None,
        },
        "newest_observation": "2026-10-10T00:00:00+00:00",
        "workload_tag": "controlled-fixture",
    }


def invoke(tmp_path, result, *, end="2026-10-12", extra=()):
    with (
        patch("sentinel_monitor.earth.initialize"),
        patch.object(EarthEngineAnalyzer, "__init__", return_value=None),
        patch.object(EarthEngineAnalyzer, "analyze", return_value=copy.deepcopy(result)) as analyze,
    ):
        code = main(
            [
                "run",
                "--sites",
                str(ROOT / "sites.yaml"),
                "--settings",
                str(ROOT / "settings.yaml"),
                "--results",
                str(tmp_path / "results"),
                "--output",
                str(tmp_path / "site"),
                "--end-date",
                end,
                *extra,
            ]
        )
    return code, analyze.call_count


@contextmanager
def served(directory):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(directory)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


@pytest.mark.parametrize(
    "comparison_status,sensor_error,preview_error,expected",
    [
        ("no_change_detected", True, False, "error"),
        ("possible_change", True, False, "possible_change"),
        ("possible_change", False, True, "possible_change"),
    ],
)
def test_failure_bundle_survives_http_publication_and_recovers(
    tmp_path,
    comparison_status,
    sensor_error,
    preview_error,
    expected,
):
    # These are test illustrations, never actual satellite observations.
    folder = tmp_path / "results/live/assets/controlled-fixture"
    folder.mkdir(parents=True)
    for name in ["before", "after", "overlay"]:
        Image.new("RGB", (20, 20), (80, 100, 120)).save(folder / f"{name}.png")

    assert invoke(tmp_path, outcome(), end="2026-10-05") == (0, 1)
    result = outcome(comparison_status, sensor_error=sensor_error, preview_error=preview_error)
    assert invoke(tmp_path, result) == (2, 1)
    # A failure must retry without --refresh, rather than reusing a failed record.
    assert invoke(tmp_path, result) == (2, 1)
    records = read_records(tmp_path / "results", "live")
    assert len(records) == 2
    assert records[0]["status"] == expected
    assert records[0]["has_errors"] is True

    with served(tmp_path / "site") as base:
        with urlopen(base + "/index.html") as response:
            assert response.status == 200
            html = response.read().decode()
        assert "Some analysis or previews failed" in html
        expected_message = "Fixture radar failed" if sensor_error else "Fixture preview failed"
        assert expected_message in html
        for name in ["latest", "history"]:
            with urlopen(f"{base}/{name}.json") as response:
                exported = json.load(response)
            assert exported[0]["status"] == expected
            assert exported[0]["has_errors"] is True
        for path in records[0]["comparisons"][0].get("previews", {}).values():
            assert f'src="{path}"' in html
            with urlopen(base + "/" + path) as response:
                with Image.open(BytesIO(response.read())) as image:
                    assert image.format == "PNG"
                    image.verify()

    assert invoke(tmp_path, outcome()) == (0, 1)
    recovered = read_records(tmp_path / "results", "live")
    assert len(recovered) == 2
    assert recovered[0]["has_errors"] is False
    assert recovered[0]["status"] == "no_change_detected"
    assert recovered[1]["windows"]["target_end"] == "2026-10-05"
    summary = json.loads((tmp_path / "results/run-summary.json").read_text())
    assert summary["has_errors"] is False
    assert invoke(tmp_path, outcome()) == (0, 0)


def test_diagnostic_request_upgrades_cache_without_changing_science_key(tmp_path):
    assert invoke(tmp_path, outcome()) == (0, 1)
    first = read_records(tmp_path / "results", "live")[0]
    assert invoke(tmp_path, outcome(), extra=["--radar-diagnostics"]) == (0, 1)
    upgraded = read_records(tmp_path / "results", "live")[0]
    assert upgraded["analysis_key"] == first["analysis_key"]
    assert upgraded["radar_diagnostics_requested"] is True
    assert len(read_records(tmp_path / "results", "live")) == 1
    assert invoke(tmp_path, outcome(), extra=["--radar-diagnostics"]) == (0, 0)


def test_diagnostics_reject_synthetic_mode(tmp_path):
    assert invoke(tmp_path, outcome(), extra=["--demo", "--radar-diagnostics"]) == (1, 0)


def test_diagnostic_details_render_signed_values_and_missing_statistics(tmp_path):
    result = outcome("possible_change")
    result["comparisons"][0].update(
        sensor="radar",
        radar_diagnostics={
            "threshold_db": 3,
            "polarizations": {
                "VV": {
                    "signed_delta_db": {"median_db": -4, "p05_db": -6, "p95_db": -2},
                    "positive_fraction": 0.01,
                    "negative_fraction": 0.8,
                },
                "VH": {
                    "signed_delta_db": {"median_db": None, "p05_db": None, "p95_db": None},
                    "positive_fraction": None,
                    "negative_fraction": None,
                },
            },
        },
    )
    assert invoke(tmp_path, result, extra=["--radar-diagnostics"]) == (0, 1)
    html = (tmp_path / "site/index.html").read_text(encoding="utf-8")
    assert "Signed delta is target minus baseline" in html
    assert "-4.00 dB" in html
    assert "80.0%" in html
    assert "unavailable" in html
    assert "None dB" not in html


def test_review_previews_upgrade_cache_and_render_usable_negative_observations(tmp_path):
    assert invoke(tmp_path, outcome()) == (0, 1)
    assert "Imagery review observations" not in (tmp_path / "site/index.html").read_text(
        encoding="utf-8"
    )
    first = read_records(tmp_path / "results", "live")[0]
    assert invoke(tmp_path, outcome(), extra=["--review-previews"]) == (0, 1)
    upgraded = read_records(tmp_path / "results", "live")[0]
    assert upgraded["analysis_key"] == first["analysis_key"]
    assert upgraded["review_previews_requested"] is True
    html = (tmp_path / "site/index.html").read_text(encoding="utf-8")
    assert "Imagery review observations" in html
    assert "They do not establish a quiet control" in html
    assert "No change detected" in html
    assert invoke(tmp_path, outcome(), extra=["--review-previews"]) == (0, 0)


def test_case_runner_attaches_frozen_context_without_duplicate_records(tmp_path):
    result = outcome()
    result["comparisons"][0].update(
        acquisition_date="2024-07-20",
        acquisition_times=["2024-07-20T00:00:00+00:00"],
        baseline_acquisition_dates=["2024-06-20", "2024-07-02"],
    )
    result["newest_observation"] = "2024-07-20T00:00:00+00:00"
    with (
        patch("sentinel_monitor.earth.initialize"),
        patch.object(EarthEngineAnalyzer, "__init__", return_value=None),
        patch.object(EarthEngineAnalyzer, "analyze", return_value=result),
    ):
        code = main(
            [
                "review-case",
                "--case",
                "park-fire-pre-event",
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
    assert code == 0
    records = read_records(tmp_path / "results/park-fire-pre-event", "live")
    assert len(records) == 1
    record = records[0]
    assert record["site"]["id"] == "park-fire-reference"
    assert record["windows"]["target_end"] == "2024-07-22"
    assert record["validation_case"]["review_status"] == "unreviewed"
    assert record["review_previews_requested"] is True
    output = tmp_path / "site/park-fire-pre-event"
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "quiet conditions not established" in html
    assert 'href="validation-case.json"' in html
    assert "No change detected" in html
    assert (output / "validation-case.json").exists()


@pytest.mark.parametrize("sensor", ["optical", "radar"])
@pytest.mark.parametrize(
    "times,status,classification",
    [
        (["2021-11-06T09:00:00Z"], "possible_change", "before"),
        (["2021-11-07T05:42:45Z"], "no_change_detected", "after"),
        (["2021-11-06T10:00:00Z", "2021-11-06T12:00:00Z"], "possible_change", "straddling"),
        ([], "possible_change", "unknown"),
        ([], "insufficient_data", "unknown"),
    ],
)
def test_case_timing_context_survives_json_and_static_report_for_both_sensors(
    tmp_path, sensor, times, status, classification
):
    result = outcome(status)
    comparison = result["comparisons"][0]
    comparison.update(sensor=sensor, acquisition_date="2021-11-06", acquisition_times=times)
    original = copy.deepcopy(comparison)
    with (
        patch("sentinel_monitor.earth.initialize"),
        patch.object(EarthEngineAnalyzer, "__init__", return_value=None),
        patch.object(EarthEngineAnalyzer, "analyze", return_value=result),
    ):
        assert (
            main(
                [
                    "review-case",
                    "--case",
                    "salzbachtal-demolition",
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
            == 0
        )
    output = tmp_path / "site/salzbachtal-demolition"
    history = json.loads((output / "history.json").read_text(encoding="utf-8"))
    assert history[0]["validation_case"]["event_time_utc"] == "2021-11-06T11:00:00Z"
    assert history[0]["validation_case"]["quiet_ground_truth"] is False
    saved = history[0]["comparisons"][0]
    timing = saved.pop("event_timing")
    assert saved == original
    assert timing["classification"] == classification
    assert timing["source_acquisition_times"] == times
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Acquisition timing: " + timing["label"] in html
    assert "Approximate event reference: 2021-11-06T11:00:00Z" in html
    assert "exposure intervals unavailable" in html
    if classification != "after":
        assert "Do not interpret this acquisition as established post-event evidence" in html
    for value in times:
        assert value in html
