"""Shared decisions; missing observations never become a negative detection."""

import hashlib


def comparison_status(valid_cells: float, total_cells: int, changed_cells: float, minimum: float):
    coverage = valid_cells / total_cells
    if coverage < minimum:
        return "insufficient_data", coverage
    return ("possible_change" if changed_cells > 0 else "no_change_detected"), coverage


def location_status(comparisons: list[dict], errors: list[dict]):
    if any(c["status"] == "possible_change" for c in comparisons):
        return "possible_change"
    # A partial failure cannot silently become an all-clear.
    if errors:
        return "error"
    if any(c["status"] == "no_change_detected" for c in comparisons):
        return "no_change_detected"
    return "insufficient_data"


def radar_group(properties: dict):
    return properties["relativeOrbitNumber_start"], properties["orbitProperties_pass"]


def detection_id(site_id: str, sensor: str, source_ids: list[str], analysis_key: str):
    # analysis_key includes version, thresholds, AOI, window and real/demo mode.
    value = "|".join([site_id, sensor, *sorted(source_ids), analysis_key])
    return hashlib.sha256(value.encode()).hexdigest()[:24]
