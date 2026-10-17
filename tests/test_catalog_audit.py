"""Public metadata replay checks use saved or synthetic metadata, never live services."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from sentinel_monitor.catalog_audit import audit
from sentinel_monitor.config import Settings, Site

ROOT = Path(__file__).resolve().parents[1]


def product(day, *, seconds=0, orbit=15, platform="A", mode="IW", polarizations=None, datatake=1):
    start = datetime.fromisoformat(day).replace(tzinfo=UTC) + timedelta(seconds=seconds)
    stop = start + timedelta(seconds=25)
    return {
        "product_id": (
            f"S1{platform}_{mode}_GRDH_1SDV_{start:%Y%m%dT%H%M%S}_"
            f"{stop:%Y%m%dT%H%M%S}_000001_{datatake:06X}_ABCD"
        ),
        "start_time": start.isoformat(),
        "stop_time": stop.isoformat(),
        "relative_orbit": orbit,
        "pass": "ASCENDING",
        "platform": platform,
        "mode": mode,
        "polarizations": polarizations or ["VV", "VH"],
        "absolute_orbit": 1,
        "datatake": datatake,
    }


def inputs(items):
    site = {
        "id": "synthetic",
        "name": "Synthetic QA only",
        "latitude": 50,
        "longitude": 8,
        "size_m": 500,
    }
    manifest = {
        "cases": {
            "synthetic": {
                "site": site,
                "end_date": "2021-11-13",
                "event_time_utc": "2021-11-06T11:00:00Z",
            }
        }
    }
    catalog = {
        "schema_version": 1,
        "case_ids": ["synthetic"],
        "query": {
            "start": "2021-10-01",
            "end": "2021-11-14",
            "grid": Site(**site).grid(),
            "url": "https://example.invalid/synthetic-qa",
            "truncated": False,
        },
        "items": items,
    }
    return manifest, catalog


def test_saved_two_catalog_inventory_replays_frozen_cases_without_live_services():
    manifest = json.loads((ROOT / "validation/cases.json").read_text(encoding="utf-8"))
    catalog = json.loads(
        (ROOT / "validation/salzbachtal-s1-catalog.json").read_text(encoding="utf-8")
    )
    with patch("ee.Initialize", side_effect=AssertionError("No EE initialization")):
        result = audit(manifest, catalog, Settings())
    assert len(catalog["items"]) == 24
    for provider in catalog["providers"]:
        assert provider["returned_count"] == 24
        assert not provider["limit_reached"] and not provider["next_link_present"]
    for item in catalog["items"]:
        assert item["grid_corners_inside_asf_footprint"]
        assert item["cdse_matching_metadata"] and len(item["cdse_counterparts"]) == 1
        counterpart = item["cdse_counterparts"][0]
        assert counterpart["grid_corners_inside_footprint"]
        assert item["product_id"].split("_")[:8] == counterpart["product_id"].split("_")[:8]
    for cid, baseline_counts, targets in [
        ("salzbachtal-demolition", {15: 5, 66: 5, 139: 4}, 3),
        ("salzbachtal-pre-demolition", {15: 4, 66: 5, 139: 5}, 4),
    ]:
        case = result["cases"][cid]
        assert not case["quiet_ground_truth_established"]
        assert sum(g["target_acquisitions"] for g in case["groups"]) == targets
        for group in case["groups"]:
            assert group["eligibility"] == "metadata_eligible"
            assert (
                len(group["baseline_acquisition_dates"])
                == baseline_counts[group["radar_group"]["relative_orbit"]]
            )
            assert group["baseline_platforms_mixed"]
        assert all(
            t["relative_to_approximate_event"]
            == ("at_or_after" if cid == "salzbachtal-demolition" else "before")
            for t in case["target_timing_only"]
        )
    choices = yaml.load(
        (ROOT / ".github/workflows/validation.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )["on"]["workflow_dispatch"]["inputs"]["case_id"]["options"]
    assert set(catalog["case_ids"]) <= set(choices)


def test_utc_boundaries_and_event_day_morning_are_not_silently_filtered():
    items = [
        product(d) for d in ["2021-10-08", "2021-10-09", "2021-10-20", "2021-11-06", "2021-11-13"]
    ]
    manifest, catalog = inputs(items)
    case = audit(manifest, catalog, Settings())["cases"]["synthetic"]
    assert case["eligible_source_count"] == 3
    group = case["groups"][0]
    assert group["baseline_acquisition_dates"] == ["2021-10-09", "2021-10-20"]
    assert group["target_source_ids"] == [items[3]["product_id"]]
    assert case["target_timing_only"][0]["relative_to_approximate_event"] == "before"
    utc_offset = copy.deepcopy(catalog)
    utc_offset["items"][1]["start_time"] = "2021-10-09T02:00:00+02:00"
    assert audit(manifest, utc_offset, Settings()) == audit(manifest, catalog, Settings())


def test_days_not_slices_or_platforms_and_unmatched_groups_remain_explicit():
    items = [
        product("2021-10-09"),
        product("2021-10-09", seconds=1, platform="B"),
        product("2021-11-07", datatake=2),
        product("2021-11-07", seconds=1, datatake=2),
        product("2021-10-10", orbit=66),
        product("2021-11-08", orbit=139),
        product("2021-11-09", mode="SM"),
        product("2021-11-10", polarizations=["HH", "HV"]),
    ]
    manifest, catalog = inputs(items)
    case = audit(manifest, catalog, Settings())["cases"]["synthetic"]
    groups = {g["radar_group"]["relative_orbit"]: g for g in case["groups"]}
    assert groups[15]["eligibility"] == "insufficient_baseline_days"
    assert groups[15]["baseline_platforms_mixed"]
    assert groups[15]["target_acquisitions"] == 1
    assert groups[66]["eligibility"] == "no_target_acquisitions"
    assert groups[139]["eligibility"] == "insufficient_baseline_days"
    assert len(case["excluded_source_ids"]) == 2


def test_empty_inventory_is_not_a_radar_negative_or_quiet_label():
    manifest, catalog = inputs([])
    case = audit(manifest, catalog, Settings())["cases"]["synthetic"]
    assert case["groups"] == [] and not case["quiet_ground_truth_established"]
    assert "status" not in case


@pytest.mark.parametrize(
    "invalid",
    [
        "duplicate",
        "missing_orbit",
        "naive_time",
        "truncated",
        "short_query",
        "wrong_grid",
        "filename_mismatch",
    ],
)
def test_incomplete_or_inconsistent_evidence_rejects_instead_of_inventing_eligibility(invalid):
    manifest, catalog = inputs([product("2021-10-09")])
    if invalid == "duplicate":
        catalog["items"] *= 2
    elif invalid == "missing_orbit":
        del catalog["items"][0]["relative_orbit"]
    elif invalid == "naive_time":
        catalog["items"][0]["start_time"] = "2021-10-09T00:00:00"
    elif invalid == "truncated":
        del catalog["query"]["truncated"]
    elif invalid == "short_query":
        catalog["query"]["start"] = "2021-10-10"
    elif invalid == "wrong_grid":
        catalog["query"]["grid"]["bounds"][0] += 10
    else:
        catalog["items"][0]["platform"] = "B"
    with pytest.raises(ValueError):
        audit(manifest, catalog, Settings())
