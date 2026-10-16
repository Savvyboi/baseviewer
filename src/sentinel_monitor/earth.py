"""Server-side Earth Engine analysis; only metadata, summaries and previews leave EE."""

import logging
import re
import time
from collections import defaultdict
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import ee
import google.auth
from PIL import Image

from .config import Settings, Site
from .decisions import comparison_status, detection_id, radar_group

OPTICAL = ["B2", "B3", "B4", "B8"]
RADAR = ["VV", "VH"]
S2 = "COPERNICUS/S2_SR_HARMONIZED"
S1 = "COPERNICUS/S1_GRD"
CLOUDS = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"


def error_details(exc: Exception):
    """Keep actionable service errors without persisting credentials or signed URLs."""
    message = re.sub(
        r"-----BEGIN (?:RSA )?PRIVATE KEY-----.*?-----END (?:RSA )?PRIVATE KEY-----",
        "[REDACTED]",
        str(exc),
        flags=re.DOTALL,
    )
    message = re.sub(r"https?://[^\s]+", "[URL redacted]", message)
    message = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "Bearer [REDACTED]", message)
    message = re.sub(
        r'(?i)(["\']?(?:access_token|id_token|refresh_token|client_secret|private_key)["\']?'
        r'\s*[:=]\s*)(?:"[^"\n]*"|\'[^\'\n]*\'|[^\s,};]+)',
        r"\1[REDACTED]",
        message,
    )
    message = " ".join(message.split()) or type(exc).__name__
    return {"error": type(exc).__name__, "message": message[:2000]}


def retry(operation, attempts: int):
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            message = str(exc).lower()
            transient = (
                isinstance(exc, (TimeoutError, ConnectionError))
                or isinstance(exc, HTTPError)
                and exc.code in {408, 429, 500, 502, 503, 504}
                or any(
                    t in message
                    for t in [
                        "too many requests",
                        "rate limit",
                        "timed out",
                        "temporarily unavailable",
                        "internal error",
                    ]
                )
            )
            if not transient or attempt == attempts - 1:
                raise
            time.sleep(2**attempt)


def initialize(project: str):
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    ee.Initialize(credentials=credentials, project=project)


class EarthEngineAnalyzer:
    def __init__(
        self,
        site: Site,
        settings: Settings,
        period: dict,
        analysis_key: str,
        assets: Path,
        *,
        radar_diagnostics: bool = False,
        review_previews: bool = False,
    ):
        self.site, self.settings, self.period = site, settings, period
        self.key, self.assets = analysis_key, assets
        self.include_radar_diagnostics = radar_diagnostics
        self.include_review_previews = review_previews
        self.grid = site.grid()
        self.aoi = ee.Geometry.Rectangle(self.grid["bounds"], proj=self.grid["crs"], geodesic=False)
        self.projection = ee.Projection(self.grid["crs"], self.grid["transform"])
        self.masks = {}
        self.comparisons = []
        self.errors = []
        self.observations = []

    def request(self, operation):
        return retry(operation, self.settings.request_attempts)

    def on_grid(self, image):
        return image.reproject(crs=self.projection)

    def reduce(self, image, *, reducer=None, band_count=4):
        return image.reduceRegion(
            reducer=ee.Reducer.sum() if reducer is None else reducer,
            geometry=self.aoi,
            crs=self.grid["crs"],
            crsTransform=self.grid["transform"],
            # Bound input band-pixels without coarsening the fixed analysis grid.
            # Ordinary summaries use up to four bands; diagnostics declare their count.
            maxPixels=(self.grid["cells"] + 100) * band_count,
            tileScale=2,
        )

    def metadata(self, collection):
        limit = self.settings.max_images_per_sensor

        def describe(value):
            image = ee.Image(value)
            return ee.Dictionary(
                {
                    "id": image.id(),
                    "index": image.get("system:index"),
                    "time": image.get("system:time_start"),
                    "day": image.date().format("YYYY-MM-dd", "UTC"),
                    "relativeOrbitNumber_start": image.get("relativeOrbitNumber_start"),
                    "orbitProperties_pass": image.get("orbitProperties_pass"),
                    "optical_datatake": image.get("DATATAKE_IDENTIFIER"),
                    "radar_datatake": image.get("missionDataTakeID"),
                    "platform": image.get("platform_number"),
                }
            )

        info = self.request(
            lambda: ee.Dictionary(
                {
                    "count": collection.size(),
                    "items": collection.limit(limit + 1).toList(limit + 1).map(describe),
                }
            ).getInfo()
        )
        if info["count"] > limit:
            raise ValueError(
                f"More than {limit} source granules; narrow the AOI or raise the limit"
            )
        return info["items"]

    def optical(self, image):
        # Default nearest-neighbour sampling keeps categorical SCL classes intact.
        land = image.select("SCL").eq(4).Or(image.select("SCL").eq(5))
        score = image.select("cs_cdf")
        clear = score.gte(self.settings.cloud_score_min).unmask(1)
        mask = land.And(clear)
        reflectance = image.select(OPTICAL).multiply(0.0001).updateMask(mask)
        fallback = score.mask().Not().unmask(1).rename("cloud_fallback").updateMask(mask)
        return self.on_grid(reflectance.addBands(fallback)).copyProperties(
            image, ["system:index", "system:time_start"]
        )

    def terrain(self):
        dem = ee.ImageCollection(self.settings.dem_collection).filterBounds(self.aoi.buffer(500))
        elevation = (
            dem.select("DEM")
            .mosaic()
            .setDefaultProjection(ee.Image(dem.first()).select("DEM").projection())
        )
        return ee.Terrain.slope(elevation).lte(self.settings.terrain_max_slope_deg)

    def radar(self, image, terrain):
        db = image.select(RADAR)
        angle = image.select("angle")
        valid = (
            db.mask()
            .reduce(ee.Reducer.min())
            .And(db.reduce(ee.Reducer.min()).gt(self.settings.radar_min_db))
            .And(angle.gte(self.settings.radar_min_angle))
            .And(angle.lte(self.settings.radar_max_angle))
            .And(terrain)
        )
        # Average power, never dB; reapply original validity after neighbourhood filtering.
        power = self.on_grid(db.divide(10).multiply(2.302585092994046).exp().updateMask(valid))
        if self.settings.radar_speckle_radius_m:
            power = power.focalMean(
                radius=self.settings.radar_speckle_radius_m, kernelType="square", units="meters"
            ).updateMask(self.on_grid(valid))
        return power.copyProperties(image, ["system:index", "system:time_start"])

    def daily(self, collection, items):
        # Count distinct UTC acquisition days, not overlapping tiles/slices, as observations.
        by_day = defaultdict(list)
        for item in items:
            by_day[item["day"]].append(item)
        images = []
        for day, sources in sorted(by_day.items()):
            indices = sorted(s["index"] for s in sources)
            image = collection.filter(ee.Filter.inList("system:index", indices)).sort(
                "system:index"
            )
            images.append(
                self.on_grid(image.mosaic()).set("system:time_start", ee.Date(day).millis())
            )
        return ee.ImageCollection.fromImages(images), by_day

    def acquisitions(self, collection, items):
        # Mosaic granules/slices from the same datatake, but retain distinct acquisitions.
        groups = defaultdict(list)
        for item in items:
            key = item.get("optical_datatake")
            if not key and item.get("radar_datatake") is not None:
                key = f"{item.get('platform')}-{item['radar_datatake']}"
            groups[str(key or item["time"])].append(item)
        images = []
        for key, sources in sorted(groups.items()):
            indices = sorted(s["index"] for s in sources)
            subset = collection.filter(ee.Filter.inList("system:index", indices)).sort(
                "system:index"
            )
            images.append(self.on_grid(subset.mosaic()).set("acquisition_key", key))
        return ee.ImageCollection.fromImages(images), groups

    def compare(self, sensor, prepared, baseline_items, target_items, group=None):
        bands = OPTICAL if sensor == "optical" else RADAR
        baseline_collection, baseline_days = self.daily(prepared, baseline_items)
        targets, target_groups = self.acquisitions(prepared, target_items)
        baseline_sources = sorted(s["id"] for s in baseline_items)
        baseline_dates = sorted(baseline_days)
        if len(baseline_days) >= self.settings.min_baseline_observations:
            median = self.on_grid(baseline_collection.select(bands).median())
            counts = self.on_grid(baseline_collection.select(bands).count()).reduce(
                ee.Reducer.min()
            )
            before = median if sensor == "optical" else median.log10().multiply(10)
        for acquisition_key, items in sorted(target_groups.items()):
            day = min(s["day"] for s in items)
            sources = sorted(s["id"] for s in items)
            entry = {
                "id": detection_id(self.site.id, sensor, sources, self.key),
                "sensor": sensor,
                "acquisition_date": day,
                "acquisition_times": [
                    datetime.fromtimestamp(s["time"] / 1000, UTC).isoformat() for s in items
                ],
                "source_ids": sources,
                "baseline_source_ids": baseline_sources,
                "baseline_acquisition_dates": baseline_dates,
                "baseline_observations": len(baseline_days),
                "radar_group": group,
                "status": "insufficient_data",
                "valid_coverage": 0.0,
                "changed_area_m2": 0.0,
            }
            self.comparisons.append(entry)
            if len(baseline_days) < self.settings.min_baseline_observations:
                entry["reason"] = (
                    f"Fewer than {self.settings.min_baseline_observations} distinct baseline "
                    "acquisition days in this group"
                )
                continue
            stage = "prepare comparison"
            try:
                target = self.on_grid(
                    ee.Image(
                        targets.filter(ee.Filter.eq("acquisition_key", acquisition_key)).first()
                    )
                )
                after = target.select(bands)
                if sensor == "radar":
                    after = after.log10().multiply(10)
                common = (
                    after.mask()
                    .reduce(ee.Reducer.min())
                    .And(counts.gte(self.settings.min_baseline_observations))
                    .And(before.mask().reduce(ee.Reducer.min()))
                )
                common = self.on_grid(common.unmask(0).clip(self.aoi))
                difference = (
                    after.subtract(before)
                    .abs()
                    .reduce(ee.Reducer.mean() if sensor == "optical" else ee.Reducer.max())
                )
                threshold = (
                    self.settings.optical_threshold
                    if sensor == "optical"
                    else self.settings.radar_threshold_db
                )
                raw = self.on_grid(difference.gt(threshold).updateMask(common).clip(self.aoi))
                connected = raw.selfMask().connectedPixelCount(
                    maxSize=max(100, self.settings.min_patch_pixels), eightConnected=True
                )
                changed = self.on_grid(
                    raw.updateMask(connected.gte(self.settings.min_patch_pixels))
                    .unmask(0)
                    .clip(self.aoi)
                )
                summary = common.rename("valid_cells").addBands(changed.rename("changed_cells"))
                summary = summary.addBands(ee.Image.pixelArea().multiply(changed).rename("area"))
                if sensor == "optical":
                    fallback = (
                        target.select("cloud_fallback")
                        .unmask(0)
                        .Or(baseline_collection.select("cloud_fallback").max().unmask(0))
                    )
                    summary = summary.addBands(fallback.multiply(common).rename("fallback_cells"))
                stage = "reduce comparison"
                stats = self.request(lambda summary=summary: self.reduce(summary).getInfo())
                status, coverage = comparison_status(
                    stats.get("valid_cells") or 0,
                    self.grid["cells"],
                    stats.get("changed_cells") or 0,
                    self.settings.min_valid_coverage,
                )
                entry.update(status=status, valid_coverage=coverage)
                if sensor == "radar" and self.include_radar_diagnostics and coverage > 0:
                    self.radar_diagnostics(entry, before, after, common, baseline_collection)
                if sensor == "optical":
                    entry["cloud_screening"] = (
                        "reduced: SCL fallback in baseline or target"
                        if stats.get("fallback_cells")
                        else "SCL and Cloud Score+"
                    )
                if status == "insufficient_data":
                    entry["reason"] = "Common valid coverage is below the configured minimum"
                    continue
                entry["changed_area_m2"] = stats.get("area") or 0.0
                entry["changed_cells"] = stats.get("changed_cells") or 0
                self.masks[sensor] = self.masks.get(sensor, self.on_grid(ee.Image(0))).Or(changed)
                if status == "possible_change" or self.include_review_previews:
                    try:
                        entry["previews"] = self.previews(
                            entry["id"], sensor, before, after, changed
                        )
                    except Exception as exc:
                        details = error_details(exc)
                        entry["preview_error"] = details["error"]
                        entry["preview_error_message"] = details["message"]
                        logging.warning(
                            "Preview generation failed for %s: %s", entry["id"], details["message"]
                        )
            except Exception as exc:
                details = error_details(exc)
                entry.update(status="error", reason=f"{stage}: {details['message']}")
                self.errors.append(
                    {"sensor": sensor, "acquisition_date": day, "stage": stage, **details}
                )
                logging.error(
                    "%s/%s/%s %s failed: %s", self.site.id, sensor, day, stage, details["message"]
                )

    def radar_diagnostics(self, entry, before, after, common, baseline_collection):
        """Describe signed shifts on common cells; never alter the detection mask."""
        delta = after.subtract(before)
        # The range of independently mosaicked daily observations diagnoses baseline
        # variability; it is not an uncertainty estimate or a cause attribution.
        baseline_db = baseline_collection.select(RADAR).map(
            lambda image: image.log10().multiply(10)
        )
        spread = baseline_db.max().subtract(baseline_db.min())
        threshold = self.settings.radar_threshold_db
        positive, negative = delta.gt(threshold), delta.lt(-threshold)
        exceeded = positive.Or(negative)
        image = (
            before.rename(["before_VV", "before_VH"])
            .addBands(after.rename(["after_VV", "after_VH"]))
            .addBands(delta.rename(["delta_VV", "delta_VH"]))
            .addBands(spread.rename(["range_VV", "range_VH"]))
            .addBands(spread.gt(threshold).rename(["unstable_VV", "unstable_VH"]))
            .addBands(positive.rename(["positive_VV", "positive_VH"]))
            .addBands(negative.rename(["negative_VV", "negative_VH"]))
            .addBands(exceeded.reduce(ee.Reducer.max()).rename("either"))
            .addBands(exceeded.reduce(ee.Reducer.min()).rename("both"))
            .updateMask(common)
        )
        reducer = (
            ee.Reducer.count()
            .combine(ee.Reducer.mean(), sharedInputs=True)
            .combine(ee.Reducer.percentile([5, 50, 95]), sharedInputs=True)
        )
        try:
            stats = self.request(
                lambda: self.reduce(image, reducer=reducer, band_count=16).getInfo()
            )

            def distribution(prefix):
                return {
                    label: stats.get(f"{prefix}_{suffix}")
                    for label, suffix in [
                        ("count", "count"),
                        ("mean_db", "mean"),
                        ("p05_db", "p5"),
                        ("median_db", "p50"),
                        ("p95_db", "p95"),
                    ]
                }

            entry["radar_diagnostics"] = {
                "scope": "common valid cells, before connected-patch filtering",
                "threshold_db": threshold,
                "polarizations": {
                    band: {
                        "baseline_db": distribution(f"before_{band}"),
                        "target_db": distribution(f"after_{band}"),
                        "signed_delta_db": distribution(f"delta_{band}"),
                        "baseline_range_db": distribution(f"range_{band}"),
                        "baseline_range_exceedance_fraction": stats.get(f"unstable_{band}_mean"),
                        "positive_fraction": stats.get(f"positive_{band}_mean"),
                        "negative_fraction": stats.get(f"negative_{band}_mean"),
                    }
                    for band in RADAR
                },
                "either_fraction": stats.get("either_mean"),
                "both_fraction": stats.get("both_mean"),
            }
        except Exception as exc:
            details = error_details(exc)
            entry["radar_diagnostics_error"] = details["message"]
            self.errors.append({"sensor": "radar", "stage": "diagnostics", **details})
            logging.error("%s/radar diagnostics failed: %s", self.site.id, details["message"])

    def sensor(self, sensor):
        raw = (
            ee.ImageCollection(S2 if sensor == "optical" else S1)
            .filterBounds(self.aoi)
            .filterDate(self.period["baseline_start"], self.period["target_end"])
        )
        if sensor == "optical":
            raw = raw.select([*OPTICAL, "SCL"])
            clouds = (
                ee.ImageCollection(CLOUDS)
                .filterBounds(self.aoi)
                .filterDate(self.period["baseline_start"], self.period["target_end"])
                .select("cs_cdf")
            )
            prepared = raw.linkCollection(clouds, ["cs_cdf"]).map(self.optical)
        else:
            raw = (
                raw.filter(ee.Filter.eq("instrumentMode", "IW"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
                .select([*RADAR, "angle"])
            )
            terrain = self.terrain()
            prepared = raw.map(lambda image: self.radar(image, terrain))
        items = self.metadata(raw)
        self.observations.extend(items)
        groups = defaultdict(list)
        for item in items:
            key = radar_group(item) if sensor == "radar" else None
            groups[key].append(item)
        for group, sources in groups.items():
            baseline = [s for s in sources if s["day"] < self.period["target_start"]]
            target = [s for s in sources if s["day"] >= self.period["target_start"]]
            if target:
                group_metadata = {"relative_orbit": group[0], "pass": group[1]} if group else None
                self.compare(sensor, prepared, baseline, target, group_metadata)

    def previews(self, identity, sensor, before, after, changed):
        folder = self.assets / identity
        folder.mkdir(parents=True, exist_ok=True)
        stretch = (
            {"bands": ["B4", "B3", "B2"], "min": 0, "max": 0.3, "gamma": 1.2}
            if sensor == "optical"
            else {"bands": ["VV"], "min": -25, "max": 0}
        )
        images = {"before": before.visualize(**stretch), "after": after.visualize(**stretch)}
        images["overlay"] = images["after"].blend(
            changed.selfMask().visualize(palette=["ff653b"], min=0, max=1)
        )
        paths = {}
        for name, image in images.items():
            params = {
                "region": self.aoi,
                "dimensions": self.settings.preview_pixels,
                "format": "png",
                "crs": self.grid["crs"],
            }
            url = self.request(
                lambda image=image, params=params: self.on_grid(image).getThumbURL(params)
            )

            def download(url=url):
                with urlopen(url, timeout=120) as response:
                    data = response.read(8 * 1024 * 1024 + 1)
                if len(data) > 8 * 1024 * 1024:
                    raise ValueError("Preview exceeded size limit")
                return data

            destination = folder / f"{name}.png"
            data = self.request(download)
            with Image.open(BytesIO(data)) as check:
                if check.format != "PNG":
                    raise ValueError("Expected a PNG preview")
                check.verify()
            destination.write_bytes(data)
            paths[name] = f"assets/{identity}/{name}.png"
        return paths

    def analyze(self):
        ee.data.setWorkloadTag(f"sentinel-{self.key}")
        for sensor in ["optical", "radar"]:
            try:
                self.sensor(sensor)
            except Exception as exc:
                details = error_details(exc)
                self.errors.append({"sensor": sensor, **details})
                logging.error("%s/%s failed: %s", self.site.id, sensor, details["message"])
        area = {"optical_m2": None, "radar_m2": None, "overlap_m2": None}
        if self.masks:
            try:
                zero = self.on_grid(ee.Image(0))
                optical = self.masks.get("optical", zero)
                radar = self.masks.get("radar", zero)
                images = (
                    ee.Image.pixelArea()
                    .multiply(optical)
                    .rename("optical_m2")
                    .addBands(ee.Image.pixelArea().multiply(radar).rename("radar_m2"))
                    .addBands(
                        ee.Image.pixelArea().multiply(optical.And(radar)).rename("overlap_m2")
                    )
                )
                summary = self.request(lambda: self.reduce(images).getInfo())
                for sensor in ["optical", "radar"]:
                    if sensor in self.masks:
                        area[f"{sensor}_m2"] = summary.get(f"{sensor}_m2") or 0.0
                if len(self.masks) == 2:
                    area["overlap_m2"] = summary.get("overlap_m2") or 0.0
            except Exception as exc:
                details = error_details(exc)
                self.errors.append({"sensor": "summary", **details})
                logging.error("%s/summary failed: %s", self.site.id, details["message"])
        return {
            "comparisons": self.comparisons,
            "errors": self.errors,
            "changed_area": area,
            "newest_observation": (
                datetime.fromtimestamp(
                    max(s["time"] for s in self.observations) / 1000, UTC
                ).isoformat()
                if self.observations
                else None
            ),
            "workload_tag": f"sentinel-{self.key}",
        }
