"""Synthetic Sentinel-2 human triage reports; no imagery requests or private inputs."""

import copy
import json
from pathlib import Path

import pytest
from PIL import Image
from test_assessment import comparison, export, observation, record

from sentinel_monitor.assessment import AssessmentError, assess
from sentinel_monitor.reports import build_site, save_json, sensor_scope


def review_record(scope=("optical",)):
    source = record(
        comparison("flag"),
        comparison("negative", "no_change_detected"),
        comparison("awaiting", "no_change_detected"),
        comparison("insufficient", "insufficient_data"),
    )
    source.update(
        requested_sensors=list(scope),
        usable_sensors=["optical"],
        newest_observation="2020-01-29",
        changed_area={"optical_m2": 900, "radar_m2": None, "overlap_m2": None},
        has_errors=False,
    )
    source["validation_case"]["label"] = "SYNTHETIC QA ONLY"
    source["comparisons"][2]["previews"] = {"before": "assets/before.png"}
    source["comparisons"][3]["reason"] = "Synthetic cloud/mask coverage gap"
    for item in source["comparisons"]:
        item["cloud_screening"] = "SYNTHETIC SCL and Cloud Score+ masking"
    return source


def render_fixture(root, source=None):
    source = review_record() if source is None else source
    results, output = root / "results", root / "report"
    assets = results / "live/assets"
    assets.mkdir(parents=True, exist_ok=True)
    for view, colour in (
        ("before", (90, 110, 130)),
        ("after", (100, 120, 140)),
        ("overlay", (170, 120, 90)),
    ):
        Image.new("RGB", (10, 10), colour).save(assets / f"{view}.png")
    save_json(results / "live/records/synthetic.json", source)
    build_site(results, output, "live")
    return results, output


def test_optical_triage_includes_negatives_and_separates_unavailable_data(tmp_path):
    source = review_record()
    original = copy.deepcopy(source)
    results, output = render_fixture(tmp_path, source)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Human imagery review feed" in html
    assert "Radar not requested for this analysis" in html
    assert "not requested (requires both sensors)" in html
    assert "Requested sensor without returned comparisons" not in html
    assert html.count("data-review-target=") == 3
    assert html.count('class="review-tools"') == 2
    assert "Screening: no_change_detected" in html
    assert 'data-preview-ready="false"' in html
    assert "Awaiting previews" in html
    assert "Synthetic cloud/mask coverage gap" in html
    assert "Cloud / mask context: SYNTHETIC SCL" in html
    assert "10 m resolution" in html
    assert "Automated screening:" in html
    for path in (results / "live/records/synthetic.json", output / "history.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert (value[0] if isinstance(value, list) else value) == original
    assert source == original


@pytest.mark.parametrize("scope", [None, ["optical", "radar"]])
def test_legacy_and_explicit_both_keep_genuine_radar_gap(tmp_path, scope):
    source = review_record()
    if scope is None:
        source.pop("requested_sensors")
    else:
        source["requested_sensors"] = scope
    _, output = render_fixture(tmp_path, source)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Requested sensors: optical, radar" in html
    assert "Requested sensor without returned comparisons: radar" in html
    assert "Radar not requested" not in html
    assert ("legacy record: both" in html) == (scope is None)


@pytest.mark.parametrize("state", ["missing", "unreadable", "missing_path"])
def test_unavailable_previews_never_gain_review_controls(tmp_path, state):
    source = review_record()
    if state == "missing_path":
        source["comparisons"][0]["previews"].pop("after")
    else:
        source["comparisons"][0]["previews"]["after"] = "assets/unavailable.png"
    results, output = render_fixture(tmp_path, source)
    if state == "unreadable":
        (results / "live/assets/unavailable.png").write_bytes(b"synthetic invalid PNG")
        build_site(results, output, "live")
    html = (output / "index.html").read_text(encoding="utf-8")
    assert html.count("data-review-target=") == 3
    assert html.count('class="review-tools"') == 1
    assert html.count('data-preview-ready="false"') == 2
    assert "Awaiting previews:" in html
    assert 'src=""' not in html


@pytest.mark.parametrize("scope", [[], ["optical", "optical"], ["other"], "optical", None])
def test_invalid_declared_scope_is_rejected(tmp_path, scope):
    source = review_record()
    source["requested_sensors"] = scope
    with pytest.raises(ValueError):
        sensor_scope(source)
    with pytest.raises(AssessmentError):
        assess([source], export(), tmp_path)


def test_comparison_outside_requested_scope_is_rejected(tmp_path):
    source = review_record(("radar",))
    with pytest.raises(ValueError):
        sensor_scope(source)
    with pytest.raises(AssessmentError):
        assess([source], export(), tmp_path)


def test_assessment_separates_unrequested_from_absent_and_retains_exact_identity(tmp_path):
    source = review_record()
    _, output = render_fixture(tmp_path, source)
    entry = observation(source, decision="unclear")
    result = assess([source], export(entry), output / "assets")
    summary = result["source_records"][0]
    assert summary["requested_sensors"] == ["optical"]
    assert summary["not_requested_sensors"] == ["radar"]
    assert summary["absent_sensors"] == []
    assert result["denominators"]["all_science_comparisons"] == 4
    assert result["denominators"]["awaiting_previews"] == 1
    assert result["comparisons"][0]["observation"] == entry
    refreshed = copy.deepcopy(source)
    refreshed["generated_at"] = "2020-02-06T12:00:00Z"
    result = assess([refreshed], export(entry), output / "assets")
    assert result["excluded_review_counts"] == {"stale_record": 1}
    assert result["denominators"]["reviewed_including_unclear"] == 0
    source.pop("requested_sensors")
    result = assess([source], export(), output / "assets")
    assert result["source_records"][0]["absent_sensors"] == ["radar"]
    assert result["source_records"][0]["not_requested_sensors"] == []


def test_requested_sensor_failure_stays_visible(tmp_path):
    source = review_record()
    source.update(
        errors=[{"sensor": "optical", "message": "Synthetic acquisition failure"}], has_errors=True
    )
    _, output = render_fixture(tmp_path, source)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Synthetic acquisition failure" in html
    assert "Some analysis or previews failed" in html
    assert "Radar not requested" in html


@pytest.mark.parametrize("requested", [["optical"], ["radar"], ["optical", "radar"]])
def test_requested_acquisition_failure_without_comparisons_is_not_a_negative(tmp_path, requested):
    source = review_record(requested)
    source.update(
        comparisons=[],
        usable_sensors=[],
        newest_observation=None,
        status="error",
        changed_area={"optical_m2": None, "radar_m2": None, "overlap_m2": None},
        errors=[{"sensor": requested[0], "message": "Synthetic source acquisition failed"}],
        has_errors=True,
    )
    _, output = render_fixture(tmp_path, source)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Requested sensor without returned comparisons: " + ", ".join(requested) in html
    assert "Synthetic source acquisition failed" in html
    assert "this is not a negative screening result" in html
    assert 'class="review-tools"' not in html
    result = assess([source], export(), output / "assets")
    assert result["source_records"][0]["absent_sensors"] == requested
    assert result["source_records"][0]["not_requested_sensors"] == sorted(
        {"optical", "radar"} - set(requested)
    )
    assert result["denominators"]["all_science_comparisons"] == 0
    assert result["source_records"][0]["detector_status"] == "error"


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1])
    render_fixture(root / "optical")
    refreshed = review_record()
    refreshed["generated_at"] = "2020-02-06T12:00:00Z"
    render_fixture(root / "refreshed", refreshed)
    legacy = review_record()
    legacy.pop("requested_sensors")
    render_fixture(root / "legacy", legacy)
    print("Synthetic browser fixtures prepared.")
