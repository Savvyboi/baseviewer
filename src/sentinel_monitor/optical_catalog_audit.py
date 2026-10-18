"""Replay frozen public Sentinel-2 L2A metadata offline; no imagery or EE calls."""

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import yaml

from .catalog_audit import utc_time
from .config import Settings, Site, windows

PRODUCT = re.compile(r"S2[A-D]_MSIL2A_(\d{8}T\d{6})_N\d{4}_R\d{3}_T[0-9A-Z]{5}_\d{8}T\d{6}\.SAFE")


def source(item):
    required = {"product_id", "start_time", "footprint", "cloud_cover_percent", "provider_id"}
    if not isinstance(item, dict) or required - item.keys():
        raise ValueError("Incomplete public optical product metadata")
    if not isinstance(item["product_id"], str) or not PRODUCT.fullmatch(item["product_id"]):
        raise ValueError("Expected original Sentinel-2 L2A SAFE product ID")
    instant = utc_time(item["start_time"])
    if instant.strftime("%Y%m%d") != item["product_id"].split("_")[2][:8]:
        raise ValueError("Product ID and UTC acquisition day disagree")
    cloud = item["cloud_cover_percent"]
    if cloud is not None and (
        type(cloud) not in (float, int) or not math.isfinite(cloud) or not 0 <= cloud <= 100
    ):
        raise ValueError("Invalid scene cloud percentage")
    footprint = item["footprint"]
    if (
        not isinstance(footprint, dict)
        or footprint.get("type") not in {"Polygon", "MultiPolygon"}
        or not footprint.get("coordinates")
        or not isinstance(item["provider_id"], str)
        or not item["provider_id"]
    ):
        raise ValueError("Missing footprint or provider identity")
    return instant


def audit(manifest, catalog, settings):
    """Trust the retained spatial query; count UTC days, without a cloud-percent filter."""
    if catalog.get("schema_version") != 1:
        raise ValueError("Unsupported optical catalog snapshot schema")
    cid = catalog["case_id"]
    case = manifest["cases"][cid]
    period = windows(case["end_date"])
    grid = Site(**case["site"]).grid()
    query = catalog["query"]
    low = utc_time(period["baseline_start"], date_allowed=True)
    split = utc_time(period["target_start"], date_allowed=True)
    high = utc_time(period["target_end"], date_allowed=True)
    if (
        query.get("truncated") is not False
        or not query.get("url", "").startswith("https://")
        or query.get("grid") != grid
        or utc_time(query["start"], date_allowed=True) > low
        or utc_time(query["end"], date_allowed=True) < high
    ):
        raise ValueError("Complete catalog query must cover frozen grid and windows")
    items = catalog["items"]
    if not isinstance(items, list):
        raise ValueError("Catalog items must be a list")
    timed = [(item, source(item)) for item in items]
    if len({item["product_id"] for item, _ in timed}) != len(timed):
        raise ValueError("Duplicate product IDs in catalog snapshot")
    selected = [(item, instant) for item, instant in timed if low <= instant < high]
    if len(selected) > settings.max_images_per_sensor:
        raise ValueError("Public inventory exceeds production source bound")
    baseline, target = defaultdict(list), defaultdict(list)
    for item, instant in selected:
        (baseline if instant < split else target)[instant.date().isoformat()].append(item)

    def days(group):
        return [
            {
                "day": day,
                "product_ids": sorted(item["product_id"] for item in entries),
                "scene_cloud_percent_by_product": {
                    item["product_id"]: item["cloud_cover_percent"]
                    for item in sorted(entries, key=lambda item: item["product_id"])
                },
            }
            for day, entries in sorted(group.items())
        ]

    return {
        "kind": "offline public Sentinel-2 L2A metadata eligibility replay",
        "schema_version": 1,
        "case_id": cid,
        "windows": period,
        "grid": grid,
        "intersecting_l2a_products": len(selected),
        "baseline_product_count": sum(map(len, baseline.values())),
        "target_product_count": sum(map(len, target.values())),
        "baseline_distinct_days": len(baseline),
        "target_distinct_days": len(target),
        "minimum_baseline_days": settings.min_baseline_observations,
        "metadata_baseline_sufficient": len(baseline) >= settings.min_baseline_observations,
        "baseline": days(baseline),
        "target": days(target),
        "aoi_valid_coverage": None,
        "ee_ingestion_verified": False,
        "limitations": [
            "Spatial filtering is trusted from the retained query; no catalog is contacted.",
            "Public L2A products do not prove EE harmonized collection ingestion or identity.",
            "Granules on one UTC day are one observation; platforms and tiles are not extra days.",
            "No scene cloud-percent filter: production applies SCL and Cloud Score+ per pixel.",
            "Metadata counts do not establish per-cell baseline sufficiency or common coverage.",
            "Automated flags are triage; appearance observations are not certified ground truth.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-file", type=Path, default=Path("validation/sentinel2-cases.json"))
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--settings", type=Path, default=Path("settings.yaml"))
    args = parser.parse_args()
    print(
        json.dumps(
            audit(
                json.loads(args.case_file.read_text(encoding="utf-8")),
                json.loads(args.catalog.read_text(encoding="utf-8")),
                Settings(**yaml.safe_load(args.settings.read_text(encoding="utf-8"))),
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
