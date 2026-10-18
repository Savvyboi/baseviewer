"""Validated configuration and a fixed metric analysis grid."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, fields
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from pyproj import Transformer


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    latitude: float
    longitude: float
    size_m: int = 2000

    def __post_init__(self):
        if not isinstance(self.id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", self.id):
            raise ValueError("Site id must be a lowercase slug, at most 48 characters")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(f"{self.id}: name is required")
        for name, low, high in [("latitude", -90, 90), ("longitude", -180, 180)]:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{self.id}: {name} must be numeric")
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{self.id}: {name} must be between {low} and {high}")
        if type(self.size_m) is not int or not 30 <= self.size_m <= 20000 or self.size_m % 10:
            raise ValueError(f"{self.id}: size_m must be a multiple of 10 between 30 and 20000")

    def grid(self):
        if self.latitude >= 84:
            epsg = 32661
        elif self.latitude < -80:
            epsg = 32761
        else:
            zone = min(60, int((self.longitude + 180) / 6) + 1)
            epsg = (32600 if self.latitude >= 0 else 32700) + zone
        crs = f"EPSG:{epsg}"
        x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(
            self.longitude, self.latitude
        )
        left = round((x - self.size_m / 2) / 10) * 10
        top = round((y + self.size_m / 2) / 10) * 10
        return {
            "crs": crs,
            "transform": [10, 0, left, 0, -10, top],
            "bounds": [left, top - self.size_m, left + self.size_m, top],
            "cells": (self.size_m // 10) ** 2,
        }


@dataclass(frozen=True)
class Settings:
    analysis_version: str = "0.1.0"
    earth_engine_project: str | None = None
    optical_threshold: float = 0.10
    radar_threshold_db: float = 3.0
    cloud_score_min: float = 0.6
    min_baseline_observations: int = 2
    min_valid_coverage: float = 0.7
    min_patch_pixels: int = 9
    radar_speckle_radius_m: int = 10
    radar_min_db: float = -35
    radar_min_angle: float = 31
    radar_max_angle: float = 45
    terrain_max_slope_deg: float = 15
    dem_collection: str = "COPERNICUS/DEM/GLO30_2024_1"
    max_sites: int = 1
    max_images_per_sensor: int = 300
    request_attempts: int = 3
    preview_pixels: int = 400

    def __post_init__(self):
        if self.earth_engine_project is not None and (
            not isinstance(self.earth_engine_project, str)
            or not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", self.earth_engine_project)
        ):
            raise ValueError("earth_engine_project must be a Google Cloud project ID")
        if not isinstance(self.analysis_version, str) or not self.analysis_version.strip():
            raise ValueError("analysis_version must be a nonempty string")
        for name in ["cloud_score_min", "min_valid_coverage"]:
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        for name in ["optical_threshold", "radar_threshold_db", "terrain_max_slope_deg"]:
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        limits = {
            "min_baseline_observations": (2, 100),
            "min_patch_pixels": (1, 1024),
            "max_sites": (1, 200),
            "max_images_per_sensor": (1, 1000),
            "request_attempts": (1, 5),
            "preview_pixels": (100, 1000),
            "radar_speckle_radius_m": (0, 50),
        }
        for name, (low, high) in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")
        for name in ["radar_min_db", "radar_min_angle", "radar_max_angle"]:
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0 <= self.radar_min_angle < self.radar_max_angle <= 90:
            raise ValueError("Radar incidence angle limits must be ordered within [0, 90]")
        if not isinstance(self.dem_collection, str) or not self.dem_collection.startswith(
            "COPERNICUS/"
        ):
            raise ValueError("dem_collection must identify a Copernicus DEM collection")


def load_config(sites_path: Path, settings_path: Path):
    raw = yaml.safe_load(sites_path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or set(raw) != {"sites"} or not isinstance(raw["sites"], list):
        raise ValueError("sites.yaml must contain a sites list")
    if not raw["sites"]:
        raise ValueError("Configure at least one site")
    sites = [Site(**entry) for entry in raw["sites"]]
    if len({s.id for s in sites}) != len(sites):
        raise ValueError("Site IDs must be unique")
    data = yaml.safe_load(settings_path.read_text(encoding="utf-8-sig")) or {}
    if not isinstance(data, dict) or set(data) - {f.name for f in fields(Settings)}:
        raise ValueError("settings.yaml contains unknown settings")
    return sites, Settings(**data)


def windows(end_date: str | None = None):
    end = date.fromisoformat(end_date) if end_date else datetime.now(UTC).date()
    if end > datetime.now(UTC).date():
        raise ValueError("end-date must not include incomplete or future UTC days")
    target = end - timedelta(days=7)
    return {
        "baseline_start": (target - timedelta(days=28)).isoformat(),
        "baseline_end": target.isoformat(),
        "target_start": target.isoformat(),
        "target_end": end.isoformat(),
    }


def requested_sensors(value=None):
    """Canonical API scope; omitted/None selections default to both sensors."""
    if value is None or value == "both":
        return ["optical", "radar"]
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("Requested sensors must be optical, radar, or both")
    if any(sensor not in ("optical", "radar") for sensor in value) or len(set(value)) != len(value):
        raise ValueError("Requested sensors must be unique optical/radar values")
    return [sensor for sensor in ("optical", "radar") if sensor in value]


def record_requested_sensors(record):
    """Only an absent record field is legacy BOTH; explicit malformed fields reject."""
    if "requested_sensors" not in record:
        return ["optical", "radar"]
    value = record["requested_sensors"]
    if not isinstance(value, list):
        raise ValueError("Record requested_sensors must be a nonempty sensor list")
    scope = requested_sensors(value)
    if value != scope:
        raise ValueError("Record requested_sensors must use canonical optical/radar order")
    return scope


def validate_sensor_options(sensors, *, radar_diagnostics=False, optical_review_stretch=False):
    scope = requested_sensors(sensors)
    if radar_diagnostics and "radar" not in scope:
        raise ValueError("--radar-diagnostics requires requested radar")
    if optical_review_stretch and "optical" not in scope:
        raise ValueError("--optical-review-stretch requires requested optical")
    return scope


def signature(site: Site, settings: Settings, period: dict, mode: str, requested_sensors=None):
    data = {
        "site": asdict(site),
        "settings": {
            k: v
            for k, v in asdict(settings).items()
            if k
            not in {
                "max_sites",
                "max_images_per_sensor",
                "request_attempts",
                "preview_pixels",
                "earth_engine_project",
            }
        },
        "windows": period,
        "mode": mode,
    }
    scope = validate_sensor_options(requested_sensors)
    # Preserve all historical BOTH keys while separating either single-sensor scope.
    if scope != ["optical", "radar"]:
        data["requested_sensors"] = scope
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:20]
