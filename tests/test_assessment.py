"""Private evaluator verification uses synthetic data and disposable repositories only."""

import copy
import hashlib
import json
import socket
import subprocess
from dataclasses import asdict
from unittest.mock import patch

import pytest
from PIL import Image

from sentinel_monitor.assessment import (
    IDENTITY_FIELDS,
    MAX_REVIEW_BYTES,
    PRIVATE_DIRECTORY,
    AssessmentError,
    assess,
    identity,
    validate_reviews,
    write_assessment,
)
from sentinel_monitor.cli import main
from sentinel_monitor.config import Settings, Site, windows
from sentinel_monitor.decisions import location_status


def comparison(name="example", status="possible_change", sensor="optical"):
    usable = status in {"possible_change", "no_change_detected"}
    result = {
        "id": name,
        "sensor": sensor,
        "acquisition_date": "2020-01-29",
        "status": status,
        "valid_coverage": 1 if usable else 0,
        "changed_area_m2": 900 if status == "possible_change" else 0,
        "source_ids": ["synthetic:target"],
        "baseline_source_ids": ["synthetic:baseline-1", "synthetic:baseline-2"],
        "baseline_acquisition_dates": ["2020-01-03", "2020-01-15"],
        "baseline_observations": 2,
    }
    if usable:
        result["changed_cells"] = 9 if status == "possible_change" else 0
        result["previews"] = {view: f"assets/{view}.png" for view in ("before", "after", "overlay")}
    return result


def record(*comparisons):
    site = Site("civilian-fixture", "Synthetic civilian site", 0, 3, 100)
    return {
        "schema_version": 1,
        "analysis_version": "0.1.0",
        "analysis_key": "synthetic-key",
        "mode": "live",
        "generated_at": "2020-02-04T12:00:00+00:00",
        "site": asdict(site),
        "settings": asdict(Settings()),
        "grid": site.grid(),
        "windows": windows("2020-02-03"),
        "status": location_status(list(comparisons), []),
        "errors": [],
        "validation_case": {"id": "civilian-fixture", "review_status": "unreviewed"},
        "review_previews_requested": True,
        "comparisons": list(comparisons),
        "source_diagnostics": {"synthetic_only": True},
    }


def observation(source, index=0, decision="likely_visible_change", note="SYNTHETIC QA ONLY"):
    item = source["comparisons"][index]
    return {
        "mode": source["mode"],
        "case_id": source["validation_case"]["id"],
        "site_id": source["site"]["id"],
        "analysis_key": source["analysis_key"],
        "comparison_id": item["id"],
        "record_generated_at": source["generated_at"],
        "acquisition_date": item["acquisition_date"],
        "sensor": item["sensor"],
        "decision": decision,
        "note": note,
        "reviewed_at": "2020-02-05T12:00:00Z",
    }


def export(*entries):
    return {
        "schema_version": 1,
        "kind": "human imagery review observations",
        "exported_at": "2020-02-05T12:00:00Z",
        "reviews": list(entries),
    }


@pytest.fixture
def synthetic(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    (tmp_path / ".gitignore").write_text(".preview-*/\n", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    for view in ("before", "after", "overlay"):
        Image.new("RGB", (10, 10), (100, 120, 130)).save(assets / f"{view}.png")
    source = record(comparison())
    history_path, reviews_path = tmp_path / "history.json", tmp_path / "reviews.json"
    history_path.write_text(json.dumps([source]), encoding="utf-8")
    reviews_path.write_text(json.dumps(export(observation(source))), encoding="utf-8")
    return tmp_path, assets, source, history_path, reviews_path


def test_complete_denominator_partial_export_and_no_reference_promotion(synthetic):
    _, assets, _, _, _ = synthetic
    source = record(
        comparison(),
        comparison("negative", "no_change_detected"),
        comparison("pending"),
        comparison("insufficient", "insufficient_data"),
        comparison("error", "error"),
    )
    source["comparisons"][2].pop("previews")
    source["errors"] = [{"sensor": "radar", "error": "SyntheticError"}]
    result = assess([source], export(observation(source, decision="unclear")), assets)
    d = result["denominators"]
    assert d["all_science_comparisons"] == 5
    assert (d["usable"], d["insufficient_data"], d["error"]) == (3, 1, 1)
    assert d["review_eligible"] == 2 and d["not_review_eligible"] == 3
    assert d["eligible_unreviewed"] == 1 and d["awaiting_previews"] == 1
    assert d["unclear"] == d["reviewed_including_unclear"] == 1
    assert d["reviewed"] == 0 and d["unreviewed"] == 4
    assert result["comparisons"][1]["observation"] is None
    assert result["source_records"][0]["absent_sensors"] == ["radar"]
    assert result["source_records"][0]["original_source_record"] == source
    assert all(row["reference_truth"] == "not_established" for row in result["comparisons"])
    assert result["accuracy"]["available"] is False
    assert result["detector_by_appearance_counts"]["insufficient_data"]["unreviewed"] == 1


def test_notes_and_reset_timestamps_do_not_complete_review(synthetic):
    _, assets, source, _, _ = synthetic
    entry = observation(source, decision="unreviewed", note="Synthetic draft")
    result = assess([source], export(entry), assets)
    assert result["denominators"]["eligible_unreviewed"] == 1
    assert result["denominators"]["reviewed_including_unclear"] == 0
    assert result["comparisons"][0]["observation"] == entry


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", "demo"),
        ("case_id", "other-case"),
        ("site_id", "other-site"),
        ("analysis_key", "other-key"),
        ("comparison_id", "other-comparison"),
        ("record_generated_at", "2020-02-06T12:00:00Z"),
        ("acquisition_date", "2020-01-30"),
        ("sensor", "radar"),
    ],
)
def test_each_identity_field_is_exact_and_never_transfers(synthetic, field, value):
    _, assets, source, _, _ = synthetic
    entry = observation(source)
    entry[field] = value
    result = assess([source], export(entry), assets)
    assert result["comparisons"][0]["observation"] is None
    assert result["denominators"]["eligible_unreviewed"] == 1
    reason = "stale_record" if field == "record_generated_at" else "out_of_report"
    assert result["excluded_review_counts"] == {reason: 1}


def test_key_order_invariance_but_equivalent_timestamp_spelling_is_stale(synthetic):
    _, assets, source, _, _ = synthetic
    entry = observation(source)
    assert identity(entry) == identity(dict(reversed(list(entry.items()))))
    entry["record_generated_at"] = "2020-02-04T12:00:00Z"
    result = assess([source], export(entry), assets)
    assert result["excluded_review_counts"] == {"stale_record": 1}


def test_refreshed_history_retains_distinct_rows_without_pooling(synthetic):
    _, assets, source, _, _ = synthetic
    refreshed = copy.deepcopy(source)
    refreshed["generated_at"] = "2020-02-06T12:00:00+00:00"
    result = assess([source, refreshed], export(observation(source)), assets)
    assert result["denominators"]["all_science_comparisons"] == 2
    assert result["comparisons"][0]["observation"] is not None
    assert result["comparisons"][1]["observation"] is None


@pytest.mark.parametrize("duplicate", ["review", "record", "comparison"])
def test_duplicate_identities_reject_atomically(synthetic, duplicate):
    workspace, assets, source, history_path, reviews_path = synthetic
    history, payload = [source], export(observation(source))
    if duplicate == "review":
        payload["reviews"] *= 2
    elif duplicate == "record":
        history *= 2
    else:
        source["comparisons"] *= 2
    history_path.write_text(json.dumps(history), encoding="utf-8")
    reviews_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AssessmentError):
        write_assessment(history_path, reviews_path, workspace, assets)
    assert not (workspace / PRIVATE_DIRECTORY).exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", ""),
        ("site_id", " "),
        ("case_id", None),
        ("sensor", []),
        ("comparison_id", 1),
        ("analysis_key", "bad\nidentity"),
        ("acquisition_date", "2020-02-30"),
        ("record_generated_at", "2020-02-04"),
        ("decision", []),
        ("decision", "truth"),
        ("note", 42),
        ("reviewed_at", "bad-timestamp"),
    ],
)
def test_malformed_review_entries_reject(synthetic, field, value):
    _, _, source, _, _ = synthetic
    entry = observation(source)
    entry[field] = value
    with pytest.raises(AssessmentError):
        validate_reviews(export(entry))


def test_schema_note_size_and_entry_limits(synthetic):
    _, _, source, _, _ = synthetic
    entry = observation(source, note="😀" * 1000)
    assert validate_reviews(export(entry))
    entry["note"] += "x"
    with pytest.raises(AssessmentError):
        validate_reviews(export(entry))
    payload = export()
    payload["schema_version"] = True
    with pytest.raises(AssessmentError):
        validate_reviews(payload)
    payload = export(*([observation(source)] * 5001))
    with pytest.raises(AssessmentError):
        validate_reviews(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("valid_coverage", -0.1),
        ("valid_coverage", 1.1),
        ("valid_coverage", float("inf")),
        ("valid_coverage", True),
        ("changed_cells", -1),
        ("changed_cells", 101),
        ("changed_cells", 1.5),
        ("changed_area_m2", -1),
        ("changed_area_m2", float("nan")),
        ("changed_cells", 0),
        ("changed_area_m2", 0),
        ("source_ids", []),
        ("baseline_observations", 3),
        ("changed_cells", 1),
        ("changed_area_m2", 1e20),
        ("baseline_acquisition_dates", ["2020-01-28"]),
    ],
)
def test_malformed_scientific_comparisons_reject_atomically(synthetic, field, value):
    workspace, assets, source, history_path, reviews_path = synthetic
    source["comparisons"][0][field] = value
    history_path.write_text(json.dumps([source]), encoding="utf-8")
    with pytest.raises(AssessmentError):
        write_assessment(history_path, reviews_path, workspace, assets)
    assert not (workspace / PRIVATE_DIRECTORY).exists()


@pytest.mark.parametrize("field", ["settings", "grid", "windows", "analysis_version"])
def test_required_provenance_cannot_be_omitted(synthetic, field):
    _, assets, source, _, _ = synthetic
    source.pop(field)
    with pytest.raises(AssessmentError):
        assess([source], export(), assets)


@pytest.mark.parametrize(
    "field,value",
    [("cells", -1), ("cells", 99), ("cells", True), ("transform", [20, 0, 0, 0, -20, 0])],
)
def test_invalid_grid_rejects(synthetic, field, value):
    _, assets, source, _, _ = synthetic
    source["grid"][field] = value
    with pytest.raises(AssessmentError):
        assess([source], export(), assets)


@pytest.mark.parametrize(
    "bad",
    [
        '{"schema_version":1,"schema_version":1}',
        '{"x":NaN}',
        '{"x":1e400}',
        '{"x":"\\ud800"}',
        "not json",
    ],
)
def test_invalid_json_rejects_without_output(synthetic, bad):
    workspace, assets, _, history_path, reviews_path = synthetic
    reviews_path.write_text(bad, encoding="utf-8")
    with pytest.raises(AssessmentError):
        write_assessment(history_path, reviews_path, workspace, assets)
    assert not (workspace / PRIVATE_DIRECTORY).exists()


def test_oversized_export_rejects_before_reading(synthetic):
    workspace, assets, _, history_path, reviews_path = synthetic
    reviews_path.write_bytes(b" " * (MAX_REVIEW_BYTES + 1))
    with pytest.raises(AssessmentError):
        write_assessment(history_path, reviews_path, workspace, assets)
    assert not (workspace / PRIVATE_DIRECTORY).exists()


@pytest.mark.parametrize(
    "path",
    [
        ".",
        "./",
        "assets/../secret.png",
        "/absolute.png",
        "https://example.test/image.png",
        "assets\\before.png",
        "assets/image.png?token=synthetic",
        "C:/secret.png",
    ],
)
def test_preview_paths_are_local_and_confined(synthetic, path):
    _, assets, source, _, _ = synthetic
    source["comparisons"][0]["previews"]["before"] = path
    with pytest.raises(AssessmentError):
        assess([source], export(), assets)


def test_missing_unreadable_and_undeclared_previews_remain_science_rows(synthetic):
    _, assets, source, _, _ = synthetic
    (assets / "before.png").unlink()
    (assets / "after.png").write_text("synthetic invalid PNG", encoding="utf-8")
    result = assess([source], export(observation(source)), assets)
    row = result["comparisons"][0]
    assert row["retained_render"]["before"]["state"] == "missing_file"
    assert row["retained_render"]["after"]["state"] == "unreadable_file"
    assert row["preview_state"] == "missing_or_unreadable_files"
    assert result["denominators"]["awaiting_previews"] == 1
    assert (
        row["observation"] is not None
    )  # Original export was eligible; missing files are separate.
    source["comparisons"][0].pop("previews")
    result = assess([source], export(observation(source)), assets)
    assert result["excluded_review_counts"] == {"source_not_review_eligible": 1}
    assert result["denominators"]["all_science_comparisons"] == 1


@pytest.mark.parametrize(
    "ignore",
    [
        "",
        ".preview-output/private-review-assessment/assessment-probe/\n",
        ".preview-output/private-review-assessment/assessment-*/\n",
    ],
)
def test_actual_final_and_staging_paths_must_be_ignored(synthetic, ignore):
    workspace, assets, _, history_path, reviews_path = synthetic
    (workspace / ".gitignore").write_text(ignore, encoding="utf-8")
    with pytest.raises(AssessmentError):
        write_assessment(history_path, reviews_path, workspace, assets)
    assert not (workspace / PRIVATE_DIRECTORY).exists()


def test_success_is_private_atomic_escaped_and_preserves_source_bytes(synthetic):
    workspace, assets, source, history_path, reviews_path = synthetic
    note = "SYNTHETIC <script>alert('qa')</script> & 😀"
    reviews_path.write_text(json.dumps(export(observation(source, note=note))), encoding="utf-8")
    inputs = [history_path, reviews_path, *assets.glob("*.png")]
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    path = write_assessment(history_path, reviews_path, workspace, assets)
    assert path.is_relative_to(workspace / PRIVATE_DIRECTORY)
    rendered = path.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in rendered and "<script>" not in rendered
    assert "default-src 'none'" in rendered and "localStorage" not in rendered
    result = json.loads(path.with_name("assessment.json").read_text(encoding="utf-8"))
    assert result["classification"] == "PRIVATE_LOCAL_REVIEW_ASSESSMENT_DO_NOT_PUBLISH"
    assert result["comparisons"][0]["observation"]["note"] == note
    assert (
        result["comparisons"][0]["retained_render"]["before"]["sha256"]
        == hashes[assets / "before.png"]
    )
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in hashes.items())
    assert not list((workspace / PRIVATE_DIRECTORY).glob(".assessment-*"))
    second = write_assessment(history_path, reviews_path, workspace, assets)
    assert second != path and path.exists()


def test_cli_prints_no_observations_and_never_initializes_live_analysis(synthetic, capsys, caplog):
    workspace, assets, source, history_path, reviews_path = synthetic
    note = "SYNTHETIC_PRIVATE_SENTINEL"
    reviews_path.write_text(json.dumps(export(observation(source, note=note))), encoding="utf-8")
    args = [
        "assess-reviews",
        "--history",
        str(history_path),
        "--reviews",
        str(reviews_path),
        "--private-workspace",
        str(workspace),
        "--asset-root",
        str(assets),
    ]
    with (
        patch("sentinel_monitor.earth.initialize", side_effect=AssertionError("No EE")),
        patch.object(socket, "create_connection", side_effect=AssertionError("No network")),
    ):
        assert main(args) == 0
    logs = capsys.readouterr()
    assert logs.out == "Private assessment saved under .preview-output/private-review-assessment.\n"
    reviews_path.write_text(
        json.dumps(export(observation(source), observation(source))), encoding="utf-8"
    )
    assert main(args) == 1
    assert note not in logs.out + logs.err + caplog.text
    assert source["analysis_key"] not in caplog.text
    assert "Private assessment failed" in caplog.text


def test_every_identity_field_missing_rejects(synthetic):
    _, _, source, _, _ = synthetic
    for field in IDENTITY_FIELDS:
        entry = observation(source)
        entry.pop(field)
        with pytest.raises(AssessmentError):
            validate_reviews(export(entry))


def test_usable_comparison_requires_sufficient_baseline_days(synthetic):
    _, assets, source, _, _ = synthetic
    source["comparisons"][0].update(
        baseline_observations=0, baseline_source_ids=[], baseline_acquisition_dates=[]
    )
    with pytest.raises(AssessmentError):
        assess([source], export(), assets)


def test_record_detector_status_must_match_comparisons_and_errors(synthetic):
    _, assets, source, _, _ = synthetic
    source["status"] = "no_change_detected"
    with pytest.raises(AssessmentError):
        assess([source], export(), assets)


def test_earth_engine_area_projection_variation_is_allowed(synthetic):
    _, assets, source, _, _ = synthetic
    source["comparisons"][0]["changed_area_m2"] = 898.7
    assert assess([source], export(), assets)["denominators"]["usable"] == 1


def test_legacy_insufficient_record_without_changed_cells_is_retained(synthetic):
    _, assets, _, _, _ = synthetic
    source = record(comparison("insufficient", "insufficient_data"))
    source["comparisons"][0].update(
        baseline_observations=0, baseline_source_ids=[], baseline_acquisition_dates=[]
    )
    result = assess([source], export(), assets)
    assert result["denominators"]["insufficient_data"] == 1
    assert result["source_records"][0]["absent_sensors"] == ["radar"]
