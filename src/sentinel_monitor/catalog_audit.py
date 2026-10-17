"""Replay a saved public GRD inventory offline; never initialize Earth Engine."""

import argparse
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .config import Settings, Site, windows
from .decisions import radar_group
from .diagnostics import group_eligibility

PRODUCT = re.compile(
    r"S1([A-D])_([A-Z0-9]{2})_GRD[HMF]_1S[A-Z]{2}_"
    r"(\d{8}T\d{6})_(\d{8}T\d{6})_(\d{6})_([0-9A-F]{6})_[0-9A-F]{4}(?:\.SAFE)?"
)


def utc_time(value, *, date_allowed=False):
    if not isinstance(value, str):
        raise ValueError("Catalog timestamps must be strings")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        if date_allowed and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            parsed = parsed.replace(tzinfo=UTC)
        else:
            raise ValueError("Catalog timestamps require an explicit timezone")
    return parsed.astimezone(UTC)


def source(item):
    """Require complete metadata; a missing field must not create an empty group."""
    required = {
        "product_id",
        "start_time",
        "stop_time",
        "relative_orbit",
        "pass",
        "platform",
        "mode",
        "polarizations",
        "absolute_orbit",
        "datatake",
    }
    if not isinstance(item, dict) or required - item.keys():
        raise ValueError("Incomplete public product metadata")
    if not isinstance(item["product_id"], str) or not (
        match := PRODUCT.fullmatch(item["product_id"])
    ):
        raise ValueError("Expected an original Sentinel-1 GRD product ID")
    start, stop = utc_time(item["start_time"]), utc_time(item["stop_time"])
    filename_start = datetime.strptime(match[3], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    filename_stop = datetime.strptime(match[4], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    if (
        stop <= start
        or start.replace(microsecond=0) != filename_start
        or stop.replace(microsecond=0) != filename_stop
        or item["platform"] != match[1]
        or item["mode"] != match[2]
        or item["absolute_orbit"] != int(match[5])
        or item["datatake"] != int(match[6], 16)
    ):
        raise ValueError("Product ID and acquisition metadata disagree")
    if (
        type(item["relative_orbit"]) is not int
        or not 1 <= item["relative_orbit"] <= 175
        or item["pass"] not in {"ASCENDING", "DESCENDING"}
        or not isinstance(item["polarizations"], list)
        or any(p not in {"VV", "VH", "HH", "HV"} for p in item["polarizations"])
    ):
        raise ValueError("Invalid orbit, pass or polarization metadata")
    return {
        "id": item["product_id"],
        "day": start.date().isoformat(),
        "time": int(start.timestamp() * 1000),
        "relativeOrbitNumber_start": item["relative_orbit"],
        "orbitProperties_pass": item["pass"],
        "radar_datatake": item["datatake"],
        "platform": item["platform"],
    }


def audit(manifest, catalog, settings):
    """Trust the recorded catalog spatial query, then replay production date/group rules."""
    if catalog.get("schema_version") != 1:
        raise ValueError("Unsupported catalog snapshot schema")
    case_ids = catalog.get("case_ids")
    if (
        not isinstance(case_ids, list)
        or not case_ids
        or any(not isinstance(cid, str) for cid in case_ids)
        or len(set(case_ids)) != len(case_ids)
    ):
        raise ValueError("Catalog case_ids must be unique nonempty strings")
    query = catalog["query"]
    if query.get("truncated") is not False or not query.get("url", "").startswith("https://"):
        raise ValueError("An explicitly complete public catalog query is required")
    start, end = (utc_time(query[k], date_allowed=True) for k in ("start", "end"))
    if start >= end or not isinstance(catalog.get("items"), list):
        raise ValueError("Invalid query interval or item list")
    items = [(item, source(item)) for item in catalog["items"]]
    if len({s["id"] for _, s in items}) != len(items):
        raise ValueError("Duplicate product IDs in catalog snapshot")
    cases = {}
    for cid in case_ids:
        case = manifest["cases"][cid]
        period = windows(case["end_date"])
        grid = Site(**case["site"]).grid()
        low, high = (
            utc_time(period[k], date_allowed=True) for k in ("baseline_start", "target_end")
        )
        if grid != query["grid"] or start > low or end < high:
            raise ValueError("Catalog query does not cover the frozen grid and windows")
        selected = [(item, s) for item, s in items if low <= utc_time(item["start_time"]) < high]
        if len(selected) > settings.max_images_per_sensor:
            raise ValueError("Public inventory exceeds the production source bound")
        eligible, excluded = [], []
        for item, s in selected:
            if item["mode"] == "IW" and {"VV", "VH"} <= set(item["polarizations"]):
                eligible.append(s)
            else:
                excluded.append(s["id"])
        groups = defaultdict(list)
        for s in eligible:
            groups[radar_group(s)].append(s)
        summaries = group_eligibility(
            groups, period["target_start"], settings.min_baseline_observations
        )
        for summary in summaries:
            group = summary["radar_group"]
            members = groups[(group["relative_orbit"], group["pass"])]
            summary["baseline_platforms"] = sorted(
                {s["platform"] for s in members if s["day"] < period["target_start"]}
            )
            summary["target_platforms"] = sorted(
                {s["platform"] for s in members if s["day"] >= period["target_start"]}
            )
            summary["baseline_platforms_mixed"] = len(summary["baseline_platforms"]) > 1
        timing = []
        if case.get("event_time_utc"):
            event = utc_time(case["event_time_utc"])
            for item, s in selected:
                if s in eligible and s["day"] >= period["target_start"]:
                    timing.append(
                        {
                            "product_id": s["id"],
                            "start_time": item["start_time"],
                            "relative_to_approximate_event": (
                                "before" if utc_time(item["start_time"]) < event else "at_or_after"
                            ),
                        }
                    )
        cases[cid] = {
            "windows": period,
            "grid": grid,
            "intersecting_grd_products_in_case_dates": len(selected),
            "eligible_source_count": len(eligible),
            "excluded_source_ids": sorted(excluded),
            "groups": summaries,
            "target_timing_only": sorted(timing, key=lambda t: t["start_time"]),
            "quiet_ground_truth_established": False,
        }
    return {
        "kind": "offline public GRD metadata eligibility replay",
        "schema_version": 1,
        "limitations": [
            "Recorded spatial filtering is trusted; this replay does not query any catalog.",
            "ASF original products and CDSE COG counterparts do not prove EE ingestion.",
            "Metadata eligibility does not establish per-pixel mask coverage or quietness.",
            "Event timing annotates targets only; it never removes a production-eligible source.",
        ],
        "minimum_distinct_baseline_days": settings.min_baseline_observations,
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-file", type=Path, default=Path("validation/cases.json"))
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--settings", type=Path, default=Path("settings.yaml"))
    args = parser.parse_args()
    result = audit(
        json.loads(args.case_file.read_text(encoding="utf-8")),
        json.loads(args.catalog.read_text(encoding="utf-8")),
        Settings(**yaml.safe_load(args.settings.read_text(encoding="utf-8"))),
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
