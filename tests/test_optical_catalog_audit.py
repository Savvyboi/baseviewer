"""Offline optical metadata checks; synthetic edge cases never call a service."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sentinel_monitor.config import Settings, Site
from sentinel_monitor.optical_catalog_audit import audit

ROOT = Path(__file__).resolve().parents[1]


def product(day, tile="32TMQ", cloud=0):
    stamp = day.replace("-", "") + "T100000"
    return {
        "product_id": f"S2A_MSIL2A_{stamp}_N0500_R001_T{tile}_{stamp}.SAFE",
        "start_time": day + "T10:00:00Z",
        "provider_id": "synthetic-" + stamp + tile,
        "cloud_cover_percent": cloud,
        "footprint": {"type": "Polygon", "coordinates": [[[8, 44], [9, 44], [9, 45], [8, 44]]]},
    }


def inputs(items):
    site = {
        "id": "synthetic",
        "name": "Synthetic QA",
        "latitude": 44,
        "longitude": 8,
        "size_m": 500,
    }
    manifest = {"cases": {"synthetic": {"site": site, "end_date": "2019-07-05"}}}
    catalog = {
        "schema_version": 1,
        "case_id": "synthetic",
        "query": {
            "url": "https://example.invalid/synthetic",
            "start": "2019-05-30",
            "end": "2019-07-06",
            "grid": Site(**site).grid(),
            "truncated": False,
        },
        "items": items,
    }
    return manifest, catalog


def test_boundaries_daily_mosaics_and_scene_cloud_are_not_pixel_eligibility():
    items = [
        product(d) for d in ["2019-05-30", "2019-05-31", "2019-06-01", "2019-06-28", "2019-07-05"]
    ]
    items += [product("2019-06-01", tile="32TMR", cloud=100)]
    manifest, catalog = inputs(items)
    result = audit(manifest, catalog, Settings())
    assert result["baseline_product_count"] == 3
    assert result["baseline_distinct_days"] == 2
    assert result["target_product_count"] == result["target_distinct_days"] == 1
    assert result["metadata_baseline_sufficient"]
    assert result["aoi_valid_coverage"] is None
    assert not result["ee_ingestion_verified"]
    assert 100 in result["baseline"][1]["scene_cloud_percent_by_product"].values()
    changed = copy.deepcopy(catalog)
    changed["items"][1]["start_time"] = "2019-05-31T12:00:00+02:00"
    assert audit(manifest, changed, Settings()) == result


def test_many_same_day_tiles_cannot_supply_two_baseline_days():
    manifest, catalog = inputs([product("2019-06-01"), product("2019-06-01", tile="32TMR")])
    result = audit(manifest, catalog, Settings())
    assert not result["metadata_baseline_sufficient"]
    assert result["target_distinct_days"] == 0


@pytest.mark.parametrize("change", ["duplicate", "time", "cloud", "missing", "footprint"])
def test_invalid_source_provenance_is_rejected(change):
    manifest, catalog = inputs([product("2019-06-01")])
    if change == "duplicate":
        catalog["items"] *= 2
    elif change == "time":
        catalog["items"][0]["start_time"] = "2019-06-01T10:00:00"
    elif change == "cloud":
        catalog["items"][0]["cloud_cover_percent"] = float("nan")
    elif change == "missing":
        del catalog["items"][0]["provider_id"]
    else:
        catalog["items"][0]["footprint"] = None
    with pytest.raises(ValueError):
        audit(manifest, catalog, Settings())


@pytest.mark.parametrize("change", ["truncated", "grid", "start", "end", "limit"])
def test_query_must_cover_the_frozen_case_and_respect_source_bound(change):
    manifest, catalog = inputs([product("2019-06-01"), product("2019-06-02")])
    settings = Settings()
    if change == "truncated":
        catalog["query"]["truncated"] = True
    elif change == "grid":
        catalog["query"]["grid"]["bounds"][0] += 10
    elif change == "start":
        catalog["query"]["start"] = "2019-06-01"
    elif change == "end":
        catalog["query"]["end"] = "2019-07-04"
    else:
        settings = Settings(max_images_per_sensor=1)
    with pytest.raises(ValueError):
        audit(manifest, catalog, settings)


def test_saved_catalog_replays_without_network_or_ee():
    manifest = json.loads((ROOT / "validation/sentinel2-cases.json").read_text(encoding="utf-8"))
    catalog = json.loads(
        (ROOT / "validation/sentinel2-optical-catalog.json").read_text(encoding="utf-8")
    )
    expected = json.loads(
        (ROOT / "docs/evidence/sentinel2-eligibility-2026-10-18.json").read_text(encoding="utf-8")
    )
    with (
        patch("ee.Initialize", side_effect=AssertionError("No EE")),
        patch("socket.socket", side_effect=AssertionError("No network")),
    ):
        result = audit(manifest, catalog, Settings())
    assert result == expected
    assert result["baseline_distinct_days"] == 6
    assert result["target_distinct_days"] == 1
    assert result["target"][0]["day"] == "2019-07-01"
    assert manifest["cases"][catalog["case_id"]]["review_status"] == "unreviewed"


def test_saved_normalization_matches_complete_primary_response_and_hashes():
    import hashlib

    catalog = json.loads(
        (ROOT / "validation/sentinel2-optical-catalog.json").read_text(encoding="utf-8")
    )
    raw = (ROOT / catalog["source_response"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == catalog["source_response_sha256"]
    response = json.loads(raw)
    assert response["@odata.count"] == len(response["value"]) == 7
    assert "@odata.nextLink" not in response
    originals = {item["Id"]: item for item in response["value"]}
    for item in catalog["items"]:
        original = originals[item["provider_id"]]
        attrs = {entry["Name"]: entry["Value"] for entry in original["Attributes"]}
        assert item["product_id"] == original["Name"]
        assert item["start_time"] == original["ContentDate"]["Start"]
        assert item["stop_time"] == original["ContentDate"]["End"]
        assert item["footprint"] == original["GeoFootprint"]
        assert item["cloud_cover_percent"] == attrs["cloudCover"]
        assert item["attributes"] == attrs
    selection = json.loads(
        (ROOT / "docs/evidence/sentinel2-selection-2026-10-18.json").read_text(encoding="utf-8")
    )
    for name, expected in selection["exact_lf_sha256"].items():
        data = (ROOT / name).read_bytes()
        assert b"\r" not in data
        assert hashlib.sha256(data).hexdigest() == expected


def test_manual_workflow_maps_only_the_known_case_to_separate_manifest():
    import yaml

    workflow = yaml.load(
        (ROOT / ".github/workflows/validation.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    cid = "genoa-morandi-east-demolition"
    choices = workflow["on"]["workflow_dispatch"]["inputs"]["case_id"]["options"]
    assert choices.count(cid) == 1
    script = next(
        step["run"]
        for step in workflow["jobs"]["imagery"]["steps"]
        if "sentinel-monitor review-case" in step.get("run", "")
    )
    assert f'if [[ "$CASE_ID" == {cid} ]]; then' in script
    assert "args+=(--case-file validation/sentinel2-cases.json)" in script
    assert "--case-file $" not in script
