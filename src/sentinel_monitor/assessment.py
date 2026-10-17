"""Offline private assessment of reviewer appearance observations, never truth labels."""

import hashlib
import html
import json
import math
import subprocess
import uuid
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath

from PIL import Image

from .config import Settings, Site
from .decisions import location_status

IDENTITY_FIELDS = (
    "mode",
    "case_id",
    "site_id",
    "analysis_key",
    "comparison_id",
    "record_generated_at",
    "acquisition_date",
    "sensor",
)
DECISIONS = {"unreviewed", "likely_visible_change", "no_obvious_visible_change", "unclear"}
USABLE = {"possible_change", "no_change_detected"}
STATUSES = USABLE | {"insufficient_data", "error"}
VIEWS = ("before", "after", "overlay")
PRIVATE_DIRECTORY = Path(".preview-output/private-review-assessment")
MAX_REVIEW_BYTES = 2 * 1024 * 1024
MAX_HISTORY_BYTES = 50 * 1024 * 1024
LIMITATIONS = [
    "Appearance observations are not independently established reference truth. "
    "Frozen reference labels remain separate and are never promoted by this assessment.",
    "The denominator is every science comparison in the supplied history, including "
    "insufficient data, errors and missing previews. An absent sensor has no comparison "
    "and is reported separately; it is never a detector negative.",
    "Unclear is reviewed but inconclusive. Notes alone do not complete a review. "
    "Omitted eligible export entries remain unreviewed.",
    "Detector-by-appearance counts describe this retained set only. They are not accuracy, "
    "false-positive rates, representative thresholds or evidence of quiet/change radar accuracy.",
    "Optical RGB previews omit NIR; radar VV previews omit potentially triggering VH. "
    "Display stretch, clipping, resolution, masking and baseline composition limit review.",
    "Schema 1 has no display-variant identity. Retained PNG hashes describe files read now; "
    "the export does not prove which rendering was seen. Use original immutable previews. "
    "Never attach these observations to a newly stretched or refreshed record.",
    "No benchmark, threshold calibration, live analysis, publication or browser-storage access "
    "is performed. Additional independently referenced civilian examples require separate gates.",
]


class AssessmentError(ValueError):
    """Intentionally generic: do not echo private input values into logs."""


def _require(condition):
    if not condition:
        raise AssessmentError("Invalid private assessment input or destination")


def _text(value, *, empty=False):
    _require(isinstance(value, str) and (empty or bool(value.strip())) and len(value) <= 2000)
    _require(not any(ord(char) < 32 for char in value))
    return value


def _timestamp(value):
    _text(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require(parsed.tzinfo is not None and parsed.utcoffset() is not None)
    except (ValueError, TypeError, OverflowError):
        raise AssessmentError("Invalid private assessment timestamp") from None


def identity(entry):
    """Validate and preserve exact strings, including timestamp spelling."""
    _require(isinstance(entry, dict))
    for field in IDENTITY_FIELDS:
        _text(entry.get(field), empty=field == "case_id")
    _require(entry["mode"] in {"live", "demo"})
    _require(entry["sensor"] in {"optical", "radar"})
    _timestamp(entry["record_generated_at"])
    try:
        _require(
            date.fromisoformat(entry["acquisition_date"]).isoformat() == entry["acquisition_date"]
        )
    except (ValueError, TypeError):
        raise AssessmentError("Invalid private assessment date") from None
    return tuple(entry[field] for field in IDENTITY_FIELDS)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _finite_json(value):
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise AssessmentError("Invalid private assessment Unicode") from None
    elif isinstance(value, float):
        _require(math.isfinite(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            _finite_json(key)
            _finite_json(item)
    elif isinstance(value, list):
        for item in value:
            _finite_json(item)


def _read_json(path, limit):
    _require(path.is_file() and path.stat().st_size <= limit)
    raw = path.read_bytes()
    _require(len(raw) <= limit)
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=lambda _: _require(False)
        )
    except (ValueError, UnicodeError, RecursionError):
        raise AssessmentError("Invalid private assessment JSON") from None
    _finite_json(value)
    return value, hashlib.sha256(raw).hexdigest()


def validate_reviews(payload):
    _finite_json(payload)
    _require(
        isinstance(payload, dict)
        and type(payload.get("schema_version")) is int
        and payload["schema_version"] == 1
        and payload.get("kind") == "human imagery review observations"
        and isinstance(payload.get("reviews"), list)
        and len(payload["reviews"]) <= 5000
    )
    if "exported_at" in payload:
        _timestamp(payload["exported_at"])
    result = {}
    for entry in payload["reviews"]:
        key = identity(entry)
        _require(
            key not in result
            and isinstance(entry.get("decision"), str)
            and entry["decision"] in DECISIONS
        )
        note = entry.get("note")
        _require(isinstance(note, str))
        try:
            _require(len(note.encode("utf-16-le")) // 2 <= 2000)
        except UnicodeError:
            raise AssessmentError("Invalid private assessment note") from None
        _require("reviewed_at" in entry)
        if entry["reviewed_at"] is not None:
            _timestamp(entry["reviewed_at"])
        result[key] = {
            field: entry[field] for field in (*IDENTITY_FIELDS, "decision", "note", "reviewed_at")
        }
    return result


def _preview(path, asset_root):
    """Only relative local assets; no URLs, traversal, or resolved-root escapes."""
    _text(path)
    relative = PurePosixPath(path)
    _require(
        not relative.is_absolute()
        and bool(relative.parts)
        and relative.parts[0] == "assets"
        and len(relative.parts) > 1
        and ".." not in relative.parts
        and not any(char in path for char in ("\\", ":", "?", "#"))
    )
    target = asset_root.joinpath(*relative.parts[1:]).resolve()
    _require(target.is_relative_to(asset_root))
    if not target.is_file():
        return {"path": path, "state": "missing_file", "sha256": None}
    _require(target.stat().st_size <= 20 * 1024 * 1024)
    raw = target.read_bytes()
    result = {"path": path, "state": "present", "sha256": hashlib.sha256(raw).hexdigest()}
    try:
        import io

        with Image.open(io.BytesIO(raw)) as image:
            _require(image.format == "PNG")
            result["dimensions"] = [image.width, image.height]
            image.verify()
    except (OSError, ValueError, Image.DecompressionBombError):
        result["state"] = "unreadable_file"
    return result


def _number(value, low=0, high=None, *, integer=False):
    _require(type(value) in (int, float) and math.isfinite(value) and value >= low)
    _require(high is None or value <= high)
    _require(not integer or value == int(value))
    return value


def _day(value):
    _text(value)
    try:
        parsed = date.fromisoformat(value)
        _require(parsed.isoformat() == value)
        return parsed
    except (ValueError, TypeError):
        raise AssessmentError("Invalid private assessment date") from None


def _source_provenance(record):
    for field in ("settings", "grid", "windows"):
        _require(isinstance(record.get(field), dict) and bool(record[field]))
    settings = record["settings"]
    _require(
        {
            "analysis_version",
            "optical_threshold",
            "radar_threshold_db",
            "min_valid_coverage",
            "min_patch_pixels",
            "min_baseline_observations",
        }.issubset(settings)
    )
    _require("size_m" in record["site"])
    try:
        site = Site(**record["site"])
        configured = Settings(**settings)
    except (TypeError, ValueError):
        raise AssessmentError("Invalid private assessment source provenance") from None
    _text(record.get("analysis_version"))
    _require(record["analysis_version"] == configured.analysis_version)
    grid = record["grid"]
    cells = _number(grid.get("cells"), 1, integer=True)
    _require(cells == (site.size_m // 10) ** 2)
    _text(grid.get("crs"))
    _require(grid["crs"].startswith("EPSG:") and grid["crs"][5:].isdigit())
    for field, length in (("transform", 6), ("bounds", 4)):
        _require(isinstance(grid.get(field), list) and len(grid[field]) == length)
        for value in grid[field]:
            _number(value, low=-float("inf"))
    transform, bounds = grid["transform"], grid["bounds"]
    _require(transform[0:2] == [10, 0] and transform[3:5] == [0, -10])
    _require(
        bounds[0] == transform[2]
        and bounds[3] == transform[5]
        and bounds[2] - bounds[0] == site.size_m
        and bounds[3] - bounds[1] == site.size_m
    )
    period = record["windows"]
    baseline_start, baseline_end, target_start, target_end = (
        _day(period.get(field))
        for field in ("baseline_start", "baseline_end", "target_start", "target_end")
    )
    _require(
        baseline_start < baseline_end == target_start < target_end
        and (baseline_end - baseline_start).days == 28
        and (target_end - target_start).days == 7
    )
    return cells, configured


def _science_comparison(comparison, record, cells, configured):
    coverage = _number(comparison.get("valid_coverage"), 0, 1)
    common_cells = coverage * cells
    _require(math.isclose(common_cells, round(common_cells), abs_tol=1e-6))
    changed = comparison.get("changed_cells")
    if "changed_cells" in comparison:
        _number(changed, 0, round(common_cells), integer=True)
    area = comparison.get("changed_area_m2")
    if area is not None:
        _number(area)
    status = comparison["status"]
    if status in USABLE:
        _require(
            changed is not None and area is not None and coverage >= configured.min_valid_coverage
        )
        if status == "possible_change":
            _require(changed >= configured.min_patch_pixels)
            # Broad physical sanity bounds, not an area recomputation or calibration.
            # EE pixelArea differs from nominal projected 10 x 10 m cells.
            _require(changed * 50 <= area <= changed * 200)
        else:
            _require(changed == 0 and area == 0)
    elif status == "insufficient_data":
        _require(coverage < configured.min_valid_coverage)
    period = record["windows"]
    _require(period["target_start"] <= comparison["acquisition_date"] < period["target_end"])
    for field in ("source_ids", "baseline_source_ids", "baseline_acquisition_dates"):
        _require(isinstance(comparison.get(field), list))
        for value in comparison[field]:
            _text(value)
    _require(bool(comparison["source_ids"]))
    for value in comparison["baseline_acquisition_dates"]:
        _day(value)
        _require(period["baseline_start"] <= value < period["baseline_end"])
    observations = comparison.get("baseline_observations")
    _number(observations, 0, integer=True)
    _require(
        observations == len(set(comparison["baseline_acquisition_dates"]))
        and len(comparison["baseline_source_ids"]) >= observations
    )
    if status in USABLE:
        _require(observations >= configured.min_baseline_observations)


def validate_history(history, asset_root):
    _finite_json(history)
    _require(isinstance(history, list) and len(history) <= 10000)
    rows = {}
    records = []
    record_keys = set()
    for record in history:
        _require(
            isinstance(record, dict)
            and type(record.get("schema_version")) is int
            and record["schema_version"] == 1
            and isinstance(record.get("site"), dict)
            and isinstance(record.get("comparisons"), list)
        )
        case = record.get("validation_case", {})
        _require(isinstance(case, dict))
        base = {
            "mode": record.get("mode"),
            "case_id": case.get("id", ""),
            "site_id": record["site"].get("id"),
            "analysis_key": record.get("analysis_key"),
            "record_generated_at": record.get("generated_at"),
        }
        for field, value in base.items():
            _text(value, empty=field == "case_id")
        _require(base["mode"] in {"live", "demo"})
        _timestamp(base["record_generated_at"])
        record_key = tuple(base.values())
        _require(record_key not in record_keys)
        record_keys.add(record_key)
        _require(isinstance(record.get("status"), str) and record["status"] in STATUSES)
        cells, configured = _source_provenance(record)
        _require(isinstance(record.get("errors"), list))
        _require(type(record.get("review_previews_requested", False)) is bool)
        sensors = set()
        for comparison in record["comparisons"]:
            _require(isinstance(comparison, dict))
            entry = {
                **base,
                "comparison_id": comparison.get("id"),
                "acquisition_date": comparison.get("acquisition_date"),
                "sensor": comparison.get("sensor"),
            }
            key = identity(entry)
            _require(key not in rows and len(rows) < 100000)
            _require(isinstance(comparison.get("status"), str) and comparison["status"] in STATUSES)
            _science_comparison(comparison, record, cells, configured)
            paths = comparison.get("previews", {})
            _require(isinstance(paths, dict))
            previews = {}
            for view in VIEWS:
                path = paths.get(view)
                if path is None or path == "":
                    previews[view] = {"path": path, "state": "missing_path", "sha256": None}
                else:
                    previews[view] = _preview(path, asset_root)
            eligible = bool(
                case
                and record.get("review_previews_requested")
                and comparison["status"] in USABLE
                and all(paths.get(view) for view in VIEWS)
            )
            states = {value["state"] for value in previews.values()}
            preview_state = (
                "missing_paths"
                if "missing_path" in states
                else "missing_or_unreadable_files"
                if states != {"present"}
                else "ready"
            )
            rows[key] = {
                "identity": entry,
                "detector_status": comparison["status"],
                "science_comparison": comparison,
                "review_eligible": eligible,
                "preview_state": preview_state,
                "retained_render": previews,
                "reference_context": case,
                "reference_truth": "not_established",
            }
            sensors.add(comparison["sensor"])
        _require(record["status"] == location_status(record["comparisons"], record["errors"]))
        records.append(
            {
                "identity": base,
                "detector_status": record["status"],
                "settings": record.get("settings", {}),
                "grid": record.get("grid", {}),
                "windows": record.get("windows", {}),
                "errors": record.get("errors", []),
                "reference_context": case,
                "reference_truth": "not_established",
                "absent_sensors": sorted({"optical", "radar"} - sensors),
                "original_source_record": record,
            }
        )
    return rows, records


def assess(history, reviews, asset_root):
    """Return private data in memory. Callers must never publish or log this value."""
    incoming = validate_reviews(reviews)
    rows, records = validate_history(history, asset_root.resolve())
    # Timestamp is the only field ignored for *classification* of excluded stale reviews.
    # This relaxed key is never used to transfer or pool any review.
    timestamp_index = {key[:5] + key[6:] for key in rows}
    excluded = []
    joined = {}
    for key, review in incoming.items():
        if key in rows and rows[key]["review_eligible"]:
            joined[key] = review
        else:
            reason = (
                "source_not_review_eligible"
                if key in rows
                else "stale_record"
                if key[:5] + key[6:] in timestamp_index
                else "out_of_report"
            )
            excluded.append({"reason": reason, "review": review})
    counts = Counter()
    matrix = {
        status: {decision: 0 for decision in sorted(DECISIONS)} for status in sorted(STATUSES)
    }
    for key, row in rows.items():
        review = joined.get(key)
        decision = review["decision"] if review else "unreviewed"
        state = (
            "unclear"
            if decision == "unclear"
            else ("unreviewed" if decision == "unreviewed" else "reviewed")
        )
        row.update(
            {
                "review_state": state,
                "appearance_decision": decision,
                "observation": review,
                "export_presence": "matched" if review else "omitted_or_ineligible",
            }
        )
        counts[state] += 1
        counts["usable" if row["detector_status"] in USABLE else row["detector_status"]] += 1
        counts["preview_" + row["preview_state"]] += 1
        counts["review_eligible"] += int(row["review_eligible"])
        counts["not_review_eligible"] += int(not row["review_eligible"])
        counts["eligible_unreviewed"] += int(row["review_eligible"] and state == "unreviewed")
        counts["awaiting_previews"] += int(
            row["detector_status"] in USABLE and row["preview_state"] != "ready"
        )
        matrix[row["detector_status"]][decision] += 1
    return {
        "schema_version": 1,
        "classification": "PRIVATE_LOCAL_REVIEW_ASSESSMENT_DO_NOT_PUBLISH",
        "created_at": datetime.now(UTC).isoformat(),
        "limitations": LIMITATIONS,
        "denominators": {
            "all_science_comparisons": len(rows),
            "source_records": len(records),
            **{
                name: counts[name]
                for name in (
                    "usable",
                    "insufficient_data",
                    "error",
                    "review_eligible",
                    "not_review_eligible",
                    "eligible_unreviewed",
                    "awaiting_previews",
                    "reviewed",
                    "unclear",
                    "unreviewed",
                    "preview_ready",
                    "preview_missing_paths",
                    "preview_missing_or_unreadable_files",
                )
            },
            "reviewed_including_unclear": counts["reviewed"] + counts["unclear"],
        },
        "excluded_review_counts": dict(Counter(item["reason"] for item in excluded)),
        "detector_by_appearance_counts": matrix,
        "accuracy": {"available": False, "reason": "No independently adjudicated truth labels"},
        "source_records": records,
        "comparisons": list(rows.values()),
        "excluded_reviews": excluded,
    }


def _render(result):
    def escape(value):
        return html.escape(str(value), quote=True)

    tables = []
    for title, values in (
        ("Denominators", result["denominators"]),
        ("Excluded reviews", result["excluded_review_counts"]),
    ):
        body = "".join(
            f"<tr><th>{escape(key)}</th><td>{value}</td></tr>" for key, value in values.items()
        )
        tables.append(f"<h2>{title}</h2><table>{body}</table>")
    matrix_rows = "".join(
        "<tr><th>"
        + escape(status)
        + "</th>"
        + "".join(f"<td>{values[decision]}</td>" for decision in sorted(DECISIONS))
        + "</tr>"
        for status, values in result["detector_by_appearance_counts"].items()
    )
    matrix = (
        "<table><tr><th>Detector status</th>"
        + "".join(f"<th>{escape(decision)}</th>" for decision in sorted(DECISIONS))
        + "</tr>"
        + matrix_rows
    )
    cards = []
    for row in result["comparisons"]:
        entry = row["identity"]
        observation = row["observation"]
        note = observation["note"] if observation else ""
        reviewed_at = observation["reviewed_at"] if observation else None
        heading = " · ".join(entry[field] for field in ("case_id", "sensor", "acquisition_date"))
        detail = json.dumps(
            {key: value for key, value in row.items() if key != "observation"},
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        cards.append(
            f"<article><h3>{escape(heading)}</h3>"
            f"<p>Detector: {escape(row['detector_status'])}. "
            f"Review: {escape(row['review_state'])} / "
            f"{escape(row['appearance_decision'])}. "
            f"Previews: {escape(row['preview_state'])}.</p>"
            f"<p>Original review timestamp: {escape(reviewed_at)}</p>"
            f"<pre>{escape(note)}</pre><details><summary>Identity, science, reference "
            f"context and retained render hashes</summary><pre>{escape(detail)}</pre>"
            "</details></article>"
        )
    exclusions = escape(json.dumps(result["excluded_reviews"], indent=2, ensure_ascii=False))
    records = escape(json.dumps(result["source_records"], indent=2, ensure_ascii=False))
    provenance = escape(json.dumps(result["provenance"], indent=2, ensure_ascii=False))
    limits = "".join(f"<li>{escape(item)}</li>" for item in result["limitations"])
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>Private local imagery assessment</title><style>"
        "body{font:16px system-ui;margin:2rem auto;padding:0 1rem;max-width:1100px}"
        "table{border-collapse:collapse;display:block;overflow:auto}"
        "td,th{border:1px solid #aaa;text-align:left;padding:.5rem}"
        "article{border-top:1px solid #aaa;margin-top:2rem}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f4f4;padding:1rem}"
        "li{margin:.5rem 0}</style><h1>Private local imagery assessment</h1>"
        "<p>Keep this report and its companion JSON local. They contain private observations "
        "and derived summaries. No verified reference truth is established.</p>"
        "<p>Reviewed and unclear are disjoint below; reviewed_including_unclear includes both. "
        "Unreviewed includes ineligible science rows; eligible_unreviewed is the review backlog. "
        "All science rows, including unavailable observations, remain in the denominator.</p>"
        + "".join(tables)
        + "<h2>Detector × human-visible appearance</h2>"
        "<p>Descriptive counts only; no accuracy or false-positive rate is available.</p>"
        + matrix
        + "</table><h2>Interpretation and limits</h2><ul>"
        + limits
        + "</ul>"
        "<h2>All science comparisons</h2>"
        + "".join(cards)
        + "<h2>Source records and absent sensors</h2><pre>"
        + records
        + "</pre>"
        "<h2>Excluded observations</h2><pre>" + exclusions + "</pre>"
        "<h2>Private provenance receipt</h2><pre>" + provenance + "</pre></html>"
    )


def _private_root(workspace, names):
    workspace = workspace.resolve(strict=True)
    top = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    _require(Path(top.stdout.strip()).resolve() == workspace)
    root = (workspace / PRIVATE_DIRECTORY).resolve()
    _require(root.is_relative_to(workspace) and root == workspace / PRIVATE_DIRECTORY)
    # Check final and staging files, not a probe that could match narrower ignore rules.
    for name in names:
        for filename in ("report.html", "assessment.json"):
            target = root / name / filename
            ignored = subprocess.run(
                ["git", "-C", str(workspace), "check-ignore", "--quiet", str(target)],
                capture_output=True,
            )
            _require(ignored.returncode == 0)
    return root


def write_assessment(history_path, reviews_path, workspace, asset_root=None):
    """Validate everything, then atomically publish one new ignored private directory."""
    history_path, reviews_path = history_path.resolve(), reviews_path.resolve()
    history, history_hash = _read_json(history_path, MAX_HISTORY_BYTES)
    reviews, reviews_hash = _read_json(reviews_path, MAX_REVIEW_BYTES)
    asset_root = (asset_root or history_path.parent / "assets").resolve()
    result = assess(history, reviews, asset_root)
    name = "assessment-" + uuid.uuid4().hex
    staging_name = ".assessment-" + uuid.uuid4().hex
    root = _private_root(workspace, (name, staging_name))
    result["provenance"] = {
        "history_path": str(history_path),
        "history_sha256": history_hash,
        "review_export_path": str(reviews_path),
        "review_export_sha256": reviews_hash,
        "exported_at": reviews.get("exported_at"),
        "asset_root": str(asset_root),
        "identity_fields": list(IDENTITY_FIELDS),
        "render_binding": "Schema 1 has no render hashes; original immutable assets required",
    }
    # Recheck input snapshots before any output creation; sources are never opened for writing.
    _require(
        hashlib.sha256(history_path.read_bytes()).hexdigest() == history_hash
        and hashlib.sha256(reviews_path.read_bytes()).hexdigest() == reviews_hash
    )
    serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    rendered = _render(result)
    # Encode before creating directories so invalid Unicode fails without partial output.
    serialized.encode("utf-8")
    rendered.encode("utf-8")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    final, stage = root / name, root / staging_name
    stage.mkdir(mode=0o700)
    try:
        (stage / "assessment.json").write_text(serialized, encoding="utf-8", newline="\n")
        (stage / "report.html").write_text(rendered, encoding="utf-8", newline="\n")
        stage.rename(final)
    finally:
        if stage.exists():
            for filename in ("report.html", "assessment.json"):
                (stage / filename).unlink(missing_ok=True)
            stage.rmdir()
    return final / "report.html"
