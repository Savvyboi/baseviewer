"""Explicitly synthetic fixtures for exercising reports without Google credentials."""

from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from .decisions import comparison_status, detection_id


def patch_cells(candidates: set[tuple[int, int]], minimum: int):
    remaining = set(candidates)
    retained = set()
    while remaining:
        seed = remaining.pop()
        component, queue = {seed}, [seed]
        while queue:
            x, y = queue.pop()
            neighbours = {
                (x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy
            } & remaining
            remaining -= neighbours
            component |= neighbours
            queue.extend(neighbours)
        if len(component) >= minimum:
            retained |= component
    return retained


def analyze_demo(site, settings, period, key, assets: Path, scenario: str):
    side = site.size_m // 10
    edge = max(0, side // 2 - 1)
    patch = {(x, y) for x in range(edge, edge + 3) for y in range(edge, edge + 3)}
    candidates = patch if scenario == "change" else set()
    retained = patch_cells(candidates, settings.min_patch_pixels)
    valid = 0 if scenario == "cloudy" else side * side
    status, coverage = comparison_status(
        valid, side * side, len(retained), settings.min_valid_coverage
    )
    acquisition = (date.fromisoformat(period["target_end"]) - timedelta(days=2)).isoformat()
    baseline = [
        (date.fromisoformat(period["baseline_end"]) - timedelta(days=d)).isoformat()
        for d in (18, 6)
    ]
    comparisons = []
    for sensor in ["optical", "radar"]:
        sources = [f"synthetic:{sensor}:{acquisition}"]
        identity = detection_id(site.id, sensor, sources, key)
        comparison = {
            "id": identity,
            "sensor": sensor,
            "status": status,
            "acquisition_date": acquisition,
            "acquisition_times": [f"{acquisition}T10:00:00Z"],
            "source_ids": sources,
            "baseline_source_ids": [f"synthetic:{sensor}:{d}" for d in baseline],
            "baseline_acquisition_dates": baseline,
            "baseline_observations": 2,
            "radar_group": {"relative_orbit": 1, "pass": "ASCENDING"}
            if sensor == "radar"
            else None,
            "valid_coverage": coverage,
            "changed_area_m2": float(len(retained) * 100) if valid else 0.0,
            "changed_cells": len(retained) if valid else 0,
            "cloud_screening": "Synthetic fixture; no satellite imagery",
        }
        if status == "insufficient_data":
            comparison["reason"] = "Synthetic missing/cloudy observation"
        if status == "possible_change":
            folder = assets / identity
            folder.mkdir(parents=True, exist_ok=True)
            before = Image.new("RGB", (side, side), "#607b4d" if sensor == "optical" else "#626262")
            draw = ImageDraw.Draw(before)
            for line in range(0, side, 20):
                draw.line(
                    (line, 0, line, side), fill="#465a38" if sensor == "optical" else "#565656"
                )
            after, overlay = before.copy(), before.copy()
            for x, y in retained:
                after.putpixel((x, y), (185, 164, 116) if sensor == "optical" else (180, 180, 180))
                overlay.putpixel((x, y), (255, 101, 59))
            previews = {}
            for name, image in [("before", before), ("after", after), ("overlay", overlay)]:
                image.resize(
                    (settings.preview_pixels, settings.preview_pixels), Image.Resampling.NEAREST
                ).save(folder / f"{name}.png")
                previews[name] = f"assets/{identity}/{name}.png"
            comparison["previews"] = previews
        comparisons.append(comparison)
    area = float(len(retained) * 100) if valid else None
    return {
        "comparisons": comparisons,
        "errors": [],
        "changed_area": {"optical_m2": area, "radar_m2": area, "overlap_m2": area},
        "newest_observation": f"{acquisition}T10:00:00Z",
        "workload_tag": None,
        "demo_scenario": scenario,
    }
