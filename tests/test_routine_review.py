"""Routine review tests use disposable synthetic records and local generated PNGs only."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from test_assessment import comparison, export, observation
from test_sentinel2_review import render_fixture, review_record

from sentinel_monitor.assessment import IDENTITY_FIELDS, AssessmentError, assess, identity
from sentinel_monitor.reports import (
    build_site,
    preview_available,
    preview_display_info,
    save_json,
)


def routine_record():
    source = review_record()
    source.pop("validation_case")
    return source


def routine_observation(source, **kwargs):
    # Reuse the schema-1 synthetic helper without adding a case to the actual record.
    return observation({**source, "validation_case": {"id": ""}}, **kwargs)


def shared_fixture(root, state="complete"):
    source = routine_record()
    alternate = {
        "status": state,
        "common_valid_cells": 100,
        "previews": {view: f"assets/shared-{view}.png" for view in ("before", "after", "overlay")},
    }
    if state == "error":
        alternate["error"] = {"message": "Synthetic shared preview failure"}
        alternate.pop("previews")
    source["comparisons"][0]["optical_review"] = alternate
    results, output = render_fixture(root, source)
    for relative in alternate.get("previews", {}).values():
        Image.new("RGB", (10, 10), (80, 100, 120)).save(results / "live" / relative)
    build_site(results, output, "live")
    return source, results, output


def test_routine_review_includes_flags_negatives_and_unavailable_rows(tmp_path):
    source = routine_record()
    original = copy.deepcopy(source)
    results, output = render_fixture(tmp_path, source)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert html.count('class="review-tools"') == 2
    assert html.count('data-case-id=""') == 2
    assert html.count("data-review-target=") == 3
    assert "Screening: no_change_detected" in html
    assert "Routine monitoring" in html
    assert "no independent reference label is attached" in html
    assert "validation-case.json" not in html
    assert "Validation case:" not in html
    assert "Awaiting previews" in html
    assert "Synthetic cloud/mask coverage gap" in html
    assert "insufficient data" in html
    assert (output / "review.js").is_file()
    assert json.loads((output / "history.json").read_text(encoding="utf-8")) == [original]
    assert json.loads((results / "live/records/synthetic.json").read_text("utf-8")) == original
    for retained in (results / "live/assets").glob("*.png"):
        assert retained.read_bytes() == (output / "assets" / retained.name).read_bytes()
    assert source == original


def test_routine_analysis_errors_stay_visible_and_never_gain_controls(tmp_path):
    source = routine_record()
    failed = comparison("failed", "error")
    failed["reason"] = "Synthetic comparison processing failed"
    source["comparisons"].append(failed)
    source.update(
        has_errors=True,
        errors=[{"sensor": "optical", "message": "Synthetic acquisition failure"}],
    )
    _, output = render_fixture(tmp_path, source)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert html.count('class="review-tools"') == 2
    assert html.count("data-review-target=") == 3
    assert "Synthetic comparison processing failed" in html
    assert "Synthetic acquisition failure" in html
    result = assess([source], export(), output / "assets")
    assert result["denominators"]["all_science_comparisons"] == 5
    assert result["denominators"]["error"] == 1
    assert result["comparisons"][-1]["review_eligible"] is False


def test_empty_case_review_matches_exact_identity_and_stale_reviews_stay_excluded(tmp_path):
    source = routine_record()
    _, output = render_fixture(tmp_path, source)
    entry = routine_observation(source, decision="unclear")
    result = assess([source], export(entry), output / "assets")
    row = result["comparisons"][0]
    assert tuple(row["identity"]) == (
        "mode",
        "case_id",
        "site_id",
        "analysis_key",
        "record_generated_at",
        "comparison_id",
        "acquisition_date",
        "sensor",
    )
    assert identity(row["identity"]) == tuple(entry[field] for field in IDENTITY_FIELDS)
    assert row["identity"]["case_id"] == ""
    assert row["observation"] == entry
    assert row["reference_context"] == {}
    assert row["reference_truth"] == "not_established"
    assert result["denominators"]["review_eligible"] == 2
    assert result["denominators"]["not_review_eligible"] == 2
    assert result["denominators"]["awaiting_previews"] == 1
    assert result["source_records"][0]["original_source_record"] == source
    refreshed = copy.deepcopy(source)
    refreshed["generated_at"] = "2020-02-06T12:00:00Z"
    stale = assess([refreshed], export(entry), output / "assets")
    assert stale["excluded_review_counts"] == {"stale_record": 1}
    assert stale["comparisons"][0]["observation"] is None
    mismatch = dict(entry, case_id="fabricated-case")
    assert assess([source], export(mismatch), output / "assets")["excluded_review_counts"] == {
        "out_of_report": 1
    }


def test_frozen_case_identity_and_reference_link_remain_unchanged(tmp_path):
    source = review_record()
    source["validation_case"].update(review_status="frozen independent reference")
    expected = observation(source)
    _, output = render_fixture(tmp_path, source)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert 'data-case-id="civilian-fixture"' in html
    assert "SYNTHETIC QA ONLY" in html
    assert "frozen independent reference" in html
    assert 'href="validation-case.json"' in html
    result = assess([source], export(expected), output / "assets")
    assert identity(result["comparisons"][0]["identity"]) == identity(expected)
    assert result["comparisons"][0]["observation"] == expected
    assert result["comparisons"][0]["reference_context"] == source["validation_case"]


@pytest.mark.parametrize("state", ["missing", "unreadable", "missing_path"])
def test_routine_missing_source_preview_stays_visible_without_controls(tmp_path, state):
    source = routine_record()
    results, output = render_fixture(tmp_path, source)
    retained = results / "live/assets/after.png"
    if state == "missing":
        retained.unlink()
    elif state == "unreadable":
        retained.write_bytes(b"SYNTHETIC invalid PNG")
    else:
        source["comparisons"][0]["previews"].pop("after")
        save_json(results / "live/records/synthetic.json", source)
    build_site(results, output, "live")
    html = (output / "index.html").read_text(encoding="utf-8")
    assert html.count("data-review-target=") == 3
    assert html.count('class="review-tools"') == (1 if state == "missing_path" else 0)
    assert "Awaiting previews:" in html
    assert "Screening: possible_change" in html
    if state != "missing_path":
        assert 'src="assets/after.png"' not in html
        assert 'href="assets/after.png"' not in html
    result = assess([source], export(), results / "live/assets")
    assert result["denominators"]["all_science_comparisons"] == 4
    if state == "missing_path":
        assert result["comparisons"][0]["review_eligible"] is False
    else:
        assert result["comparisons"][0]["preview_state"] == "missing_or_unreadable_files"


@pytest.mark.parametrize("state", ["complete", "error", "missing"])
def test_routine_shared_displays_are_honest_and_fixed_pngs_unchanged(tmp_path, state):
    source, results, output = shared_fixture(tmp_path, "complete" if state == "missing" else state)
    record_bytes = (results / "live/records/synthetic.json").read_bytes()
    fixed_bytes = {p.name: p.read_bytes() for p in (results / "live/assets").glob("*.png")}
    if state == "missing":
        (results / "live/assets/shared-after.png").unlink()
        build_site(results, output, "live")
    html = (output / "index.html").read_text(encoding="utf-8")
    assert ('data-rendering="Shared optical range"' in html) == (state == "complete")
    assert html.count('class="review-tools"') == 2
    assert html.count("Open original PNG") == 7
    assert 'data-case-id=""' in html
    if state == "error":
        assert "Synthetic shared preview failure" in html
        assert "Alternate failed" in html
    elif state == "missing":
        assert "Shared-range PNG endpoint check is incomplete" in html
        assert 'src="assets/shared-' not in html
        assert 'href="assets/shared-' not in html
    else:
        assert "Open optional shared-range PNGs" in html
    assert (results / "live/records/synthetic.json").read_bytes() == record_bytes
    for name in ("before.png", "after.png", "overlay.png"):
        assert (results / "live/assets" / name).read_bytes() == fixed_bytes[name]
    assert json.loads((output / "history.json").read_text(encoding="utf-8")) == [source]


@pytest.mark.parametrize("requested", [None, False])
def test_routine_review_opt_in_is_required(tmp_path, requested):
    source = routine_record()
    if requested is None:
        source.pop("review_previews_requested")
    else:
        source["review_previews_requested"] = requested
    _, output = render_fixture(tmp_path, source)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert 'class="review-tools"' not in html
    assert 'id="review-queue"' not in html
    assert 'src="review.js"' not in html
    assert "Screening: no_change_detected" not in html
    assert "Candidate observations" in html
    result = assess([source], export(routine_observation(source)), output / "assets")
    assert result["denominators"]["review_eligible"] == 0
    assert result["excluded_review_counts"] == {"source_not_review_eligible": 1}


def test_routine_invalid_scope_rejects_before_any_output_write(tmp_path):
    source = routine_record()
    results, output = render_fixture(tmp_path, source)
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    source["requested_sensors"] = ["radar"]
    save_json(results / "live/records/synthetic.json", source)
    Image.new("RGB", (10, 10), (20, 30, 40)).save(results / "live/assets/after.png")
    with pytest.raises(ValueError, match="outside requested scope"):
        build_site(results, output, "live")
    after = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    assert after == before


@pytest.mark.parametrize(
    "relative",
    [
        "assets/%2e%2e/outside.png",
        "assets/percent%25.png",
        "assets/before.png?variant=other",
        "assets/before.png#different-view",
    ],
)
def test_url_ambiguous_preview_paths_reject_before_image_or_file_reads(tmp_path, relative):
    source = routine_record()
    item = source["comparisons"][0]
    item["previews"] = {view: relative for view in ("before", "after", "overlay")}
    with (
        patch("PIL.Image.open", side_effect=AssertionError("Ambiguous image must not be read")),
        patch.object(Path, "read_bytes", side_effect=AssertionError("No asset read permitted")),
    ):
        assert preview_available(tmp_path, relative) is False
        assert preview_display_info(tmp_path, item) == {
            "dimensions": {},
            "limits": [],
            "opaque_pixels": {},
        }
        with pytest.raises(AssessmentError):
            assess([source], export(), tmp_path / "assets")


@pytest.mark.parametrize("relative", ["assets/%2e%2e/outside.png", "assets/hash#file.png"])
@pytest.mark.parametrize("rendering", ["fixed", "shared"])
def test_existing_url_ambiguous_literal_png_never_becomes_a_browser_link(
    tmp_path, relative, rendering
):
    source, results, output = shared_fixture(tmp_path)
    literal = results / "live" / relative
    literal.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (10, 10), (60, 90, 120)).save(literal)
    # A real contained filesystem PNG is still unsafe when its browser URL has another meaning.
    assert literal.is_file()
    item = source["comparisons"][0]
    paths = item["previews"] if rendering == "fixed" else item["optical_review"]["previews"]
    paths["before"] = relative
    save_json(results / "live/records/synthetic.json", source)
    build_site(results, output, "live")
    html = (output / "index.html").read_text(encoding="utf-8")
    assert f'src="{relative}"' not in html
    assert f'href="{relative}"' not in html
    assert f'data-src="{relative}"' not in html
    assert html.count('class="review-tools"') == (1 if rendering == "fixed" else 2)
    if rendering == "fixed":
        assert "Awaiting previews:" in html
        with pytest.raises(AssessmentError):
            assess([source], export(), results / "live/assets")
    else:
        assert 'data-rendering="Shared optical range"' not in html
        assert "Shared-range PNG endpoint check is incomplete" in html
    assert preview_available(results / "live", relative) is False
    info = preview_display_info(results / "live", item, paths)
    assert "before" not in info["dimensions"]
    assert literal.is_file()


if __name__ == "__main__":
    import sys

    fixture_root = Path(sys.argv[1])
    shared_fixture(fixture_root / "routine")
    refreshed_source = routine_record()
    refreshed_source["generated_at"] = "2020-02-06T12:00:00Z"
    render_fixture(fixture_root / "refreshed", refreshed_source)
    default_source = dict(routine_record(), review_previews_requested=False)
    render_fixture(fixture_root / "default", default_source)
    shared_fixture(fixture_root / "failed", "error")
    print("Synthetic routine browser fixtures prepared locally.")
