"""Bounded, optional imagery diagnostics; never supply a detection decision."""

import ee

SOURCE_EXAMPLE_LIMIT = 10
OPTICAL_STRETCH = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 0.3, "gamma": 1.2}
RADAR_STRETCH = {"bands": ["VV"], "min": -25, "max": 0}


def acquisition_key(item):
    key = item.get("optical_datatake")
    if not key and item.get("radar_datatake") is not None:
        key = f"{item.get('platform')}-{item['radar_datatake']}"
    return str(key or item["time"])


def radar_filters():
    return [
        ("IW", ee.Filter.eq("instrumentMode", "IW")),
        ("VV", ee.Filter.listContains("transmitterReceiverPolarisation", "VV")),
        ("VH", ee.Filter.listContains("transmitterReceiverPolarisation", "VH")),
    ]


def source_inventory(raw, sensor, period):
    """One metadata request, exact cascade counts and bounded examples per rejection."""
    filters = radar_filters() if sensor == "radar" else []

    def describe(value):
        image = ee.Image(value)
        return ee.Dictionary(
            {
                "id": image.id(),
                "day": image.date().format("YYYY-MM-dd", "UTC"),
                "instrument_mode": image.get("instrumentMode"),
                "polarizations": image.get("transmitterReceiverPolarisation"),
                "relative_orbit": image.get("relativeOrbitNumber_start"),
                "pass": image.get("orbitProperties_pass"),
                "platform": image.get("platform_number"),
            }
        )

    windows = {}
    for window in ("baseline", "target"):
        current = raw.filterDate(period[f"{window}_start"], period[f"{window}_end"])
        counts = {"intersecting": current.size()}
        exclusions = {}
        for name, condition in filters:
            previous = current
            current = current.filter(condition)
            count = previous.size().subtract(current.size())
            rejected = previous.filter(condition.Not()).sort("system:index")
            exclusions[name] = ee.Dictionary(
                {
                    "count": count,
                    "examples": rejected.toList(SOURCE_EXAMPLE_LIMIT).map(describe),
                    "examples_truncated": count.gt(SOURCE_EXAMPLE_LIMIT),
                }
            )
            counts[name] = current.size()
        windows[window] = ee.Dictionary(
            {"stage_counts": ee.Dictionary(counts), "exclusions": ee.Dictionary(exclusions)}
        )
    return ee.Dictionary(windows)


def group_eligibility(groups, target_start, minimum_days):
    result = []
    for group, items in sorted(groups.items(), key=lambda pair: str(pair[0])):
        baseline = [s for s in items if s["day"] < target_start]
        target = [s for s in items if s["day"] >= target_start]
        days = sorted({s["day"] for s in baseline})
        result.append(
            {
                "radar_group": {"relative_orbit": group[0], "pass": group[1]} if group else None,
                "baseline_source_ids": sorted(s["id"] for s in baseline),
                "target_source_ids": sorted(s["id"] for s in target),
                "baseline_acquisition_dates": days,
                "target_acquisitions": len({acquisition_key(s) for s in target}),
                "eligibility": (
                    "no_target_acquisitions"
                    if not target
                    else "insufficient_baseline_days"
                    if len(days) < minimum_days
                    else "metadata_eligible"
                ),
            }
        )
    return result


def optical_values(before, after, common, bands):
    """Prepared reflectance and pre-patch differences, restricted to common valid cells."""
    difference = after.subtract(before).abs().reduce(ee.Reducer.mean())
    image = (
        before.rename([f"before_{b}" for b in bands])
        .addBands(after.rename([f"after_{b}" for b in bands]))
        .addBands(difference.rename("mean_abs_difference"))
    )
    for view, values in (("before", before), ("after", after)):
        rgb = values.select(OPTICAL_STRETCH["bands"])
        image = image.addBands(
            rgb.lte(OPTICAL_STRETCH["min"]).rename(
                [f"{view}_low_{b}" for b in OPTICAL_STRETCH["bands"]]
            )
        ).addBands(
            rgb.gte(OPTICAL_STRETCH["max"]).rename(
                [f"{view}_high_{b}" for b in OPTICAL_STRETCH["bands"]]
            )
        )
    return image.updateMask(common)


def optical_summary(stats, bands):
    def distribution(prefix):
        return {
            name: stats.get(f"{prefix}_{suffix}")
            for name, suffix in (
                ("count", "count"),
                ("mean", "mean"),
                ("min", "min"),
                ("max", "max"),
                ("p05", "p5"),
                ("median", "p50"),
                ("p95", "p95"),
            )
        }

    return {
        "scope": "prepared reflectance on common valid cells; not unmasked source radiometry",
        "units": "reflectance",
        "baseline": {b: distribution(f"before_{b}") for b in bands},
        "target": {b: distribution(f"after_{b}") for b in bands},
        "mean_absolute_difference": distribution("mean_abs_difference"),
        "display_stretch": OPTICAL_STRETCH,
        "display_endpoint_fractions": {
            view: {
                b: {
                    "at_or_below_min": stats.get(f"{view}_low_{b}_mean"),
                    "at_or_above_max": stats.get(f"{view}_high_{b}_mean"),
                }
                for b in OPTICAL_STRETCH["bands"]
            }
            for view in ("before", "after")
        },
    }
