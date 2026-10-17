"""Atomic JSON history and a complete, self-contained static report."""

import json
import shutil
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, select_autoescape
from PIL import Image


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    temp.replace(path)


def read_records(results: Path, mode: str):
    records = []
    for file in sorted((results / mode / "records").glob("*.json")):
        record = json.loads(file.read_text(encoding="utf-8"))
        if record.get("mode") != mode:
            raise ValueError(f"Unexpected history mode in {file}")
        records.append(record)
    return sorted(
        records, key=lambda r: (r["windows"]["target_end"], r["generated_at"]), reverse=True
    )


def preview_display_info(output: Path, comparison, previews=None):
    """Inspect local display PNGs only; keep science records and imagery unchanged."""
    dimensions = {}
    opaque_pixels = {}
    limits = []
    channels = (
        [(0, "VV grey")]
        if comparison["sensor"] == "radar"
        else list(enumerate(("Red", "Green", "Blue")))
    )
    asset_root = (output / "assets").resolve()
    if previews is None:
        previews = comparison.get("previews") or {}
    for view in ("before", "after"):
        relative = previews.get(view)
        if not relative:
            continue
        path = (output / relative).resolve()
        if not path.is_relative_to(asset_root):
            continue
        try:
            with Image.open(path) as original:
                dimensions[view] = {"width": original.width, "height": original.height}
                rgba = original.convert("RGBA")
            opaque = rgba.getchannel("A").point(lambda alpha: 255 if alpha == 255 else 0)
            count = opaque.histogram()[255]
            opaque_pixels[view] = count
            if not count:
                continue
            bands = rgba.split()
            for index, name in channels:
                histogram = bands[index].histogram(mask=opaque)
                for value, endpoint in ((0, "minimum"), (255, "maximum")):
                    fraction = histogram[value] / count
                    if fraction >= 0.95:
                        limits.append(
                            {
                                "view": "Baseline" if view == "before" else "Target",
                                "channel": name,
                                "endpoint": endpoint,
                                "fraction": fraction,
                            }
                        )
        except (OSError, ValueError):
            # A missing/invalid preview must not prevent displaying retained measurements.
            continue
    return {"dimensions": dimensions, "limits": limits, "opaque_pixels": opaque_pixels}


def build_site(results: Path, output: Path, mode: str):
    records = read_records(results, mode)
    output.mkdir(parents=True, exist_ok=True)
    marker = output / ".sentinel-mode"
    if marker.exists() and marker.read_text(encoding="utf-8") != mode:
        raise ValueError("Output mode differs; choose a separate --output directory")
    marker.write_text(mode, encoding="utf-8")
    latest = {}
    for record in records:
        latest.setdefault(record["site"]["id"], record)
    assets = results / mode / "assets"
    if assets.exists():
        shutil.copytree(assets, output / "assets", dirs_exist_ok=True)
    # Public downloads contain only this mode's analysis output, never credentials.
    save_json(output / "history.json", records)
    save_json(output / "latest.json", list(latest.values()))
    env = Environment(autoescape=select_autoescape(default=True))
    template = env.from_string(
        files("sentinel_monitor").joinpath("templates/index.html").read_text(encoding="utf-8")
    )
    review_workbench = any(
        r.get("validation_case") and r.get("review_previews_requested") for r in records
    )
    review_queue = []
    review_image_info = {}
    for record_index, record in enumerate(records):
        if not (record.get("validation_case") and record.get("review_previews_requested")):
            continue
        for comparison_index, comparison in enumerate(record["comparisons"]):
            if comparison["status"] not in {"possible_change", "no_change_detected"}:
                continue
            previews = comparison.get("previews") or {}
            target = f"observation-{record_index}-{comparison_index}"
            review_image_info[target] = preview_display_info(output, comparison)
            optical_review = comparison.get("optical_review") or {}
            if optical_review.get("status") == "complete":
                review_image_info[target]["alternate"] = preview_display_info(
                    output, comparison, optical_review.get("previews") or {}
                )
            review_queue.append(
                {
                    "record": record,
                    "comparison": comparison,
                    "target": target,
                    "ready": all(previews.get(view) for view in ("before", "after", "overlay")),
                }
            )
    if review_workbench:
        (output / "review.js").write_text(
            files("sentinel_monitor").joinpath("templates/review.js").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    html = template.render(
        records=records,
        latest=list(latest.values()),
        mode=mode,
        review_workbench=review_workbench,
        review_queue=review_queue,
        review_image_info=review_image_info,
        review_mode=any(r.get("review_previews_requested") for r in records),
    )
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / ".nojekyll").touch()
    return len(records)
