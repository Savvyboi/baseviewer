"""Optional paired optical display policy; never supplies detector inputs."""

import math
from pathlib import Path

from PIL import Image

from .diagnostics import OPTICAL_STRETCH

POLICY = "optical-shared-v1"
METHOD = "shared_rgb_quantile_envelope"
SCOPE = "prepared RGB reflectance of both views on identical common valid analysis cells"


def review_metadata(common_cells, reason=None):
    return {
        "schema_version": 1,
        "policy_version": POLICY,
        "method": METHOD,
        "scope": SCOPE,
        "quantiles": [5, 95],
        "common_valid_cells": common_cells,
        "fixed_stretch": OPTICAL_STRETCH,
        "status": "unavailable",
        **({"reason": reason} if reason else {}),
    }


def review_values(before, after, common):
    """Six RGB distributions plus fixed-display endpoint support, on the fixed grid."""
    image = None
    for view, source in (("before", before), ("after", after)):
        rgb = source.select(OPTICAL_STRETCH["bands"])
        values = (
            rgb.rename([f"{view}_{b}" for b in OPTICAL_STRETCH["bands"]])
            .addBands(rgb.lte(0).rename([f"{view}_low_{b}" for b in OPTICAL_STRETCH["bands"]]))
            .addBands(rgb.gte(0.3).rename([f"{view}_high_{b}" for b in OPTICAL_STRETCH["bands"]]))
        )
        image = values if image is None else image.addBands(values)
    return image.updateMask(common)


def apply_range(metadata, stats):
    """Envelope of six per-view band quantiles, explicitly not a pooled percentile."""
    prefixes = [
        f"{view}_{band}" for view in ("before", "after") for band in OPTICAL_STRETCH["bands"]
    ]
    required = [f"{p}_{stat}" for p in prefixes for stat in ("count", "min", "max", "p5", "p95")]
    required += [
        f"{view}_{end}_{b}_mean"
        for view in ("before", "after")
        for end in ("low", "high")
        for b in OPTICAL_STRETCH["bands"]
    ]
    if any(
        not isinstance(stats.get(k), (float, int))
        or isinstance(stats[k], bool)
        or not math.isfinite(stats[k])
        for k in required
    ):
        raise ValueError("Missing or non-finite reflectance statistics")
    if metadata["common_valid_cells"] <= 0 or any(
        stats[f"{p}_count"] != metadata["common_valid_cells"] for p in prefixes
    ):
        raise ValueError("Reflectance counts do not match common valid cells")
    if any(
        not stats[f"{p}_min"] <= stats[f"{p}_p5"] <= stats[f"{p}_p95"] <= stats[f"{p}_max"]
        for p in prefixes
    ) or any(not 0 <= stats[k] <= 1 for k in required if k.endswith("_mean")):
        raise ValueError("Inconsistent reflectance statistics")
    # Save only the finite, relevant evidence; JSON must never contain NaN/Infinity.
    metadata["reflectance_stats"] = {k: stats[k] for k in required}
    metadata["fixed_endpoint_fractions"] = {
        view: {
            b: {
                "at_or_below_min": stats[f"{view}_low_{b}_mean"],
                "at_or_above_max": stats[f"{view}_high_{b}_mean"],
            }
            for b in OPTICAL_STRETCH["bands"]
        }
        for view in ("before", "after")
    }
    low = min(stats[f"{p}_p5"] for p in prefixes)
    high = max(stats[f"{p}_p95"] for p in prefixes)
    if high - low <= 1e-12:
        metadata["reason"] = "Degenerate shared reflectance range"
        return
    metadata["applied_stretch"] = {
        "bands": OPTICAL_STRETCH["bands"],
        "min": low,
        "max": high,
        "gamma": OPTICAL_STRETCH["gamma"],
    }
    metadata["status"] = "pending"


def cache_complete(record, assets: Path):
    """A requested flag alone cannot certify a policy upgrade or intact image triple."""
    if not record.get("optical_review_stretch_requested"):
        return False
    for comparison in record["comparisons"]:
        if comparison["sensor"] != "optical":
            continue
        review = comparison.get("optical_review") or {}
        if (
            review.get("schema_version") != 1
            or review.get("policy_version") != POLICY
            or review.get("method") != METHOD
            or review.get("scope") != SCOPE
            or review.get("quantiles") != [5, 95]
            or review.get("fixed_stretch") != OPTICAL_STRETCH
        ):
            return False
        count = review.get("common_valid_cells")
        if (
            not isinstance(count, (int, float))
            or isinstance(count, bool)
            or not math.isfinite(count)
            or count < 0
        ):
            return False
        if review.get("status") == "unavailable":
            reason = review.get("reason", "")
            if reason == "No common valid cells" and count == 0:
                continue
            if comparison.get("status") == "insufficient_data" and (
                reason == "Insufficient common valid coverage" or reason.startswith("Fewer than ")
            ):
                continue
            if reason != "Degenerate shared reflectance range":
                return False
            evidence = review_metadata(count)
            try:
                apply_range(evidence, review.get("reflectance_stats") or {})
            except (ValueError, TypeError, AttributeError):
                return False
            if evidence.get("reason") == reason:
                continue
            return False
        if review.get("status") != "complete" or not review.get("applied_stretch"):
            return False
        evidence = review_metadata(count)
        try:
            apply_range(evidence, review.get("reflectance_stats") or {})
        except (ValueError, TypeError, AttributeError):
            return False
        if (
            evidence["status"] != "pending"
            or evidence.get("applied_stretch") != review["applied_stretch"]
            or evidence.get("fixed_endpoint_fractions") != review.get("fixed_endpoint_fractions")
        ):
            return False
        for view in ("before", "after", "overlay"):
            relative = (review.get("previews") or {}).get(view)
            if relative != f"assets/{comparison['id']}/optical-review/{view}.png":
                return False
            path = (assets.parent / relative).resolve()
            if not path.is_relative_to(assets.resolve()):
                return False
            try:
                with Image.open(path) as image:
                    if image.format != "PNG":
                        return False
                    image.verify()
            except (OSError, ValueError):
                return False
    return True
