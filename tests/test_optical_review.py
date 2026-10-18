"""Offline paired optical display tests; no Earth Engine or imagery network requests."""

import copy
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import ee
from ee.apitestcase import ApiTestCase
from PIL import Image

from sentinel_monitor.cli import main, parser
from sentinel_monitor.config import Settings, Site, windows
from sentinel_monitor.earth import EarthEngineAnalyzer
from sentinel_monitor.optical_review import apply_range, cache_complete, review_metadata
from sentinel_monitor.reports import read_records
from sentinel_monitor.validation import review_case

ROOT = Path(__file__).resolve().parents[1]
SITE = Site("optical-fixture", "Synthetic optical display fixture", 0, 3, 100)
PERIOD = windows("2022-07-18")
RGB = ("B4", "B3", "B2")


def sources():
    return [
        {"id": f"synthetic:{day}", "index": day, "day": day, "time": index + 1}
        for index, day in enumerate(("2022-06-13", "2022-06-18", "2022-07-13"))
    ]


def reflectance_stats():
    stats = {}
    ranges = {
        "before_B4": (0.20, 0.45, 0.22, 0.40),
        "before_B3": (0.10, 0.31, 0.12, 0.28),
        "before_B2": (0.04, 0.20, 0.05, 0.18),
        "after_B4": (0.21, 0.47, 0.23, 0.42),
        "after_B3": (0.11, 0.32, 0.13, 0.29),
        "after_B2": (0.045, 0.21, 0.06, 0.19),
    }
    for prefix, (minimum, maximum, p5, p95) in ranges.items():
        stats.update(
            {
                f"{prefix}_count": 100,
                f"{prefix}_min": minimum,
                f"{prefix}_max": maximum,
                f"{prefix}_p5": p5,
                f"{prefix}_p95": p95,
                f"{prefix}_mean": (p5 + p95) / 2,
            }
        )
    for view in ("before", "after"):
        for band in RGB:
            stats[f"{view}_low_{band}_mean"] = 0.0
            stats[f"{view}_high_{band}_mean"] = 0.5 if band == "B4" else 0.0
    return stats


def png_bytes(color):
    output = BytesIO()
    Image.new("RGB", (8, 8), color).save(output, format="PNG")
    return output.getvalue()


class TestOpticalReviewGraphs(ApiTestCase):
    """Actual EE expression graphs with synthetic reduction and image responses."""

    def setUp(self):
        super().setUp()
        self.graphs = []
        self.summary = {"valid_cells": 100, "changed_cells": 9, "area": 900, "fallback_cells": 0}
        self.reflectance = reflectance_stats()
        self.fail_stats = False

        def compute(obj):
            graph = obj.serialize()
            self.graphs.append(graph)
            if '"before_B4"' in graph and "Reducer.percentile" in graph:
                if self.fail_stats:
                    raise ee.EEException(
                        "Display statistics failed access_token=private https://invalid/x"
                    )
                return self.reflectance
            return self.summary

        ee.data.computeValue = compute

    def analyzer(self, enabled=True, assets=Path("unused")):
        analyzer = EarthEngineAnalyzer(
            SITE,
            Settings(request_attempts=1),
            PERIOD,
            "synthetic-key",
            assets,
            review_previews=True,
            optical_review_stretch=enabled,
        )
        analyzer.metadata = lambda collection: sources()
        self.preview_calls = []

        def previews(identity, sensor, before, after, changed, **kwargs):
            self.preview_calls.append(
                {
                    "identity": identity,
                    "sensor": sensor,
                    "before": before.serialize(),
                    "after": after.serialize(),
                    "changed": changed.serialize(),
                    "options": kwargs,
                }
            )
            suffix = "/optical-review" if kwargs.get("variant") else ""
            return {
                name: f"assets/{identity}{suffix}/{name}.png"
                for name in ("before", "after", "overlay")
            }

        analyzer.previews = previews
        return analyzer

    def test_opt_in_preserves_science_graph_original_calls_and_comparison_identity(self):
        ordinary = self.analyzer(enabled=False)
        ordinary.sensor("optical")
        original = copy.deepcopy(ordinary.comparisons[0])
        original_graph = self.graphs[0]
        original_call = copy.deepcopy(self.preview_calls[0])
        original_mask = ordinary.masks["optical"].serialize()
        self.graphs.clear()
        alternate = self.analyzer()
        alternate.sensor("optical")
        entry = copy.deepcopy(alternate.comparisons[0])
        metadata = entry.pop("optical_review")
        assert entry == original
        assert alternate.masks["optical"].serialize() == original_mask
        assert self.graphs[0] == original_graph
        assert self.preview_calls[0] == original_call
        assert len(self.preview_calls) == 2
        assert self.preview_calls[1]["identity"] == original["id"]
        assert "Image.updateMask" in self.preview_calls[1]["changed"]
        assert metadata["status"] == "complete" and alternate.errors == []

    def test_range_is_single_scalar_envelope_for_both_dates_all_rgb_bands(self):
        analyzer = self.analyzer()
        analyzer.sensor("optical")
        metadata = analyzer.comparisons[0]["optical_review"]
        assert metadata["schema_version"] == 1
        assert metadata["method"] == "shared_rgb_quantile_envelope"
        assert metadata["common_valid_cells"] == 100
        assert metadata["scope"]
        assert metadata["applied_stretch"] == {
            "bands": ["B4", "B3", "B2"],
            "min": 0.05,
            "max": 0.42,
            "gamma": 1.2,
        }
        assert self.preview_calls[1]["options"] == {
            "stretch": metadata["applied_stretch"],
            "variant": "optical-review",
        }
        assert metadata["reflectance_stats"]["before_high_B4_mean"] == 0.5
        assert metadata["reflectance_stats"]["after_B2_p5"] == 0.06
        assert metadata["previews"]["before"].endswith("/optical-review/before.png")
        graph = self.graphs[1]
        for operation in (
            "Image.updateMask",
            "Image.lte",
            "Image.gte",
            "Reducer.count",
            "Reducer.minMax",
            "Reducer.percentile",
        ):
            assert operation in graph
        assert '"maxPixels": {"constantValue": 3600}' in graph  # 18 bands at 100 cells + margin.
        assert '"percentiles": {"constantValue": [5, 95]}' in graph
        assert "crsTransform" in graph and "bestEffort" not in graph

    def test_optical_option_does_not_add_radar_display_work(self):
        analyzer = self.analyzer()
        items = sources()
        for item in items:
            item.update(relativeOrbitNumber_start=1, orbitProperties_pass="ASCENDING")
        analyzer.metadata = lambda collection: items
        analyzer.sensor("radar")
        assert "optical_review" not in analyzer.comparisons[0]
        assert len(self.preview_calls) == 1 and self.preview_calls[0]["options"] == {}
        assert len(self.graphs) == 1

    def test_insufficient_coverage_and_no_common_cells_skip_alternate_reduction(self):
        for cells in (0, 60):
            with self.subTest(cells=cells):
                self.summary["valid_cells"] = cells
                self.graphs.clear()
                analyzer = self.analyzer()
                analyzer.sensor("optical")
                entry = analyzer.comparisons[0]
                assert entry["status"] == "insufficient_data"
                metadata = entry["optical_review"]
                assert metadata["status"] == "unavailable" and metadata["reason"]
                assert metadata["common_valid_cells"] == cells
                assert "previews" not in metadata and self.preview_calls == []
                assert len(self.graphs) == 1

    def test_missing_baseline_days_have_explicit_unavailable_metadata_without_reduction(self):
        analyzer = self.analyzer()
        analyzer.metadata = lambda collection: sources()[1:]
        analyzer.sensor("optical")
        entry = analyzer.comparisons[0]
        assert entry["status"] == "insufficient_data"
        assert entry["optical_review"]["status"] == "unavailable"
        assert entry["optical_review"]["reason"]
        assert cache_complete(
            {"optical_review_stretch_requested": True, "comparisons": [entry]}, Path("unused")
        )
        assert self.graphs == [] and self.preview_calls == []

    def test_invalid_distribution_never_creates_alternate_previews(self):
        invalid = [
            ("before_B4_count", None),
            ("after_B2_count", 99),
            ("before_B3_count", True),
            ("after_B4_p95", float("nan")),
            ("before_B2_p5", float("inf")),
            ("after_B3_p5", None),
            ("after_B4_p95", 0.1),
        ]
        for key, value in invalid:
            with self.subTest(key=key, value=value):
                self.reflectance = reflectance_stats()
                self.reflectance[key] = value
                analyzer = self.analyzer()
                analyzer.sensor("optical")
                entry = analyzer.comparisons[0]
                assert entry["status"] == "possible_change" and entry["changed_cells"] == 9
                metadata = entry["optical_review"]
                assert metadata["status"] == "error" and metadata["error"]["message"]
                assert "previews" not in metadata
                assert analyzer.errors == []
                assert len(self.preview_calls) == 1
                # Invalid server values must not make the saved JSON unserializable.
                json.dumps(metadata, allow_nan=False)

    def test_degenerate_envelope_is_unavailable_and_keeps_fixed_previews(self):
        for key in list(self.reflectance):
            if key.endswith(("_p5", "_p95", "_min", "_max")):
                self.reflectance[key] = 0.2
        analyzer = self.analyzer()
        analyzer.sensor("optical")
        entry = analyzer.comparisons[0]
        assert entry["optical_review"]["status"] == "unavailable"
        assert entry["optical_review"]["reason"] and entry["previews"]
        assert len(self.preview_calls) == 1

    def test_stats_failure_is_retryable_without_changing_detection_or_fixed_previews(self):
        self.fail_stats = True
        analyzer = self.analyzer()
        analyzer.sensor("optical")
        entry = analyzer.comparisons[0]
        assert entry["status"] == "possible_change" and entry["changed_cells"] == 9
        assert entry["previews"] and "optical" in analyzer.masks
        assert entry["optical_review"]["status"] == "error"
        assert len(self.preview_calls) == 1 and analyzer.errors == []
        assert entry["optical_review"]["error"]["message"]
        serialized = json.dumps(entry) + json.dumps(analyzer.errors)
        assert "private" not in serialized and "https://invalid" not in serialized

    def test_alternate_thumbnail_failure_does_not_remove_original_paths(self):
        analyzer = self.analyzer()
        original_previews = analyzer.previews

        def fail_alternate(*args, **kwargs):
            if kwargs.get("variant"):
                raise OSError("Synthetic alternate storage failure")
            return original_previews(*args, **kwargs)

        analyzer.previews = fail_alternate
        analyzer.sensor("optical")
        entry = analyzer.comparisons[0]
        assert entry["status"] == "possible_change" and entry["changed_cells"] == 9
        assert entry["optical_review"]["status"] == "error" and analyzer.errors == []
        assert entry["optical_review"]["error"]["message"]
        assert all("optical-review" not in path for path in entry["previews"].values())
        assert "previews" not in entry["optical_review"]

    def test_actual_thumbnail_path_keeps_original_png_bytes_through_partial_failure(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            assets = Path(temporary) / "assets"
            analyzer = self.analyzer(assets=assets)
            analyzer.previews = EarthEngineAnalyzer.previews.__get__(analyzer)
            before = ee.Image.constant([0.2, 0.15, 0.1]).rename(RGB)
            after = ee.Image.constant([0.21, 0.16, 0.11]).rename(RGB)
            changed = ee.Image(0)
            fixed = png_bytes((255, 200, 150))
            alternate = png_bytes((210, 140, 100))
            with (
                patch.object(
                    ee.Image, "getThumbURL", return_value="https://synthetic.invalid/image"
                ),
                patch(
                    "sentinel_monitor.earth.urlopen",
                    side_effect=lambda *args, **kwargs: BytesIO(fixed),
                ),
            ):
                original_paths = analyzer.previews("identity", "optical", before, after, changed)
            originals = {
                name: (assets.parent / path).read_bytes() for name, path in original_paths.items()
            }
            options = {"bands": list(RGB), "min": 0.05, "max": 0.42, "gamma": 1.2}
            with (
                patch.object(
                    ee.Image, "getThumbURL", return_value="https://synthetic.invalid/image"
                ),
                patch(
                    "sentinel_monitor.earth.urlopen",
                    side_effect=[BytesIO(alternate), OSError("Synthetic network failure")],
                ),
            ):
                try:
                    analyzer.previews(
                        "identity",
                        "optical",
                        before,
                        after,
                        changed,
                        stretch=options,
                        variant="optical-review",
                    )
                except OSError:
                    pass
                else:
                    self.fail("Partial thumbnail failure must surface")
            assert all(
                (assets.parent / original_paths[name]).read_bytes() == value
                for name, value in originals.items()
            )
            with (
                patch.object(
                    ee.Image, "getThumbURL", return_value="https://synthetic.invalid/image"
                ),
                patch(
                    "sentinel_monitor.earth.urlopen",
                    side_effect=lambda *args, **kwargs: BytesIO(alternate),
                ),
            ):
                alternate_paths = analyzer.previews(
                    "identity",
                    "optical",
                    before,
                    after,
                    changed,
                    stretch=options,
                    variant="optical-review",
                )
            assert all(
                path == f"assets/identity/optical-review/{name}.png"
                for name, path in alternate_paths.items()
            )
            assert all(
                (assets.parent / path).read_bytes() == alternate
                for path in alternate_paths.values()
            )
            assert all(
                (assets.parent / original_paths[name]).read_bytes() == value
                for name, value in originals.items()
            )

    def test_real_alternate_storage_failure_is_partial_and_keeps_fixed_bytes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            analyzer = self.analyzer(assets=Path(temporary) / "assets")
            analyzer.previews = EarthEngineAnalyzer.previews.__get__(analyzer)
            payload = png_bytes((255, 180, 120))
            original_write = Path.write_bytes

            def write(destination, data):
                if destination.name == "after.png.tmp":
                    raise OSError("Synthetic partial alternate storage failure")
                return original_write(destination, data)

            with (
                patch.object(ee.Image, "getThumbURL", return_value="https://synthetic.invalid/png"),
                patch(
                    "sentinel_monitor.earth.urlopen", side_effect=lambda *a, **kw: BytesIO(payload)
                ),
                patch.object(Path, "write_bytes", write),
            ):
                analyzer.sensor("optical")
            entry = analyzer.comparisons[0]
            assert entry["status"] == "possible_change" and analyzer.errors == []
            assert entry["optical_review"]["status"] == "error"
            assert "previews" not in entry["optical_review"]
            assert all(
                (analyzer.assets.parent / p).read_bytes() == payload
                for p in entry["previews"].values()
            )
            assert not list(analyzer.assets.rglob("*.tmp"))


def test_cli_requires_review_previews_and_rejects_demo_before_authentication():
    with patch("sentinel_monitor.earth.initialize") as initialize:
        assert main(["run", "--optical-review-stretch"]) == 1
        assert main(["run", "--demo", "--review-previews", "--optical-review-stretch"]) == 1
    initialize.assert_not_called()


def test_frozen_case_forwards_optical_flag_and_records_request(tmp_path):
    arguments = [
        "review-case",
        "--case",
        "gobabeb-quiet-reference",
        "--case-file",
        str(ROOT / "validation/cases.json"),
        "--settings",
        str(ROOT / "settings.yaml"),
        "--results",
        str(tmp_path / "results"),
        "--output",
        str(tmp_path / "site"),
    ]
    for flags in ([], ["--optical-review-stretch"]):
        args = parser().parse_args([*arguments, *flags])
        with patch("sentinel_monitor.cli.main", return_value=2) as invoke:
            assert review_case(args) == 2
        forwarded = invoke.call_args.args[0]
        assert ("--optical-review-stretch" in forwarded) == bool(flags)
        assert "--review-previews" in forwarded
        manifest = json.loads(
            (tmp_path / "site/gobabeb-quiet-reference/validation-case.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["optical_review_stretch_requested"] == bool(flags)


def test_cache_upgrade_reanalyzes_fresh_record_retries_error_then_reuses_complete(tmp_path):
    comparison = {
        "id": "synthetic-comparison",
        "sensor": "optical",
        "acquisition_date": "2022-07-13",
        "status": "no_change_detected",
        "changed_area_m2": 0,
        "changed_cells": 0,
        "valid_coverage": 1,
        "baseline_acquisition_dates": ["2022-06-13", "2022-06-18"],
        "source_ids": [],
        "baseline_source_ids": [],
        "previews": {
            name: f"assets/synthetic-comparison/{name}.png"
            for name in ("before", "after", "overlay")
        },
    }
    result = {
        "comparisons": [comparison],
        "errors": [],
        "changed_area": {"optical_m2": 0, "radar_m2": None, "overlap_m2": None},
        "newest_observation": None,
        "workload_tag": "synthetic",
    }
    args = [
        "run",
        "--sites",
        str(ROOT / "tests" / "fixtures" / "sites.yaml"),
        "--settings",
        str(ROOT / "settings.yaml"),
        "--end-date",
        "2022-07-18",
        "--review-previews",
        "--results",
        str(tmp_path / "results"),
        "--output",
        str(tmp_path / "site"),
    ]
    failed = copy.deepcopy(result)
    failed["comparisons"][0]["optical_review"] = {
        **review_metadata(100),
        "status": "error",
        "error": {"error": "OSError", "message": "Synthetic thumbnail failure"},
    }
    complete = copy.deepcopy(result)
    metadata = review_metadata(100)
    apply_range(metadata, reflectance_stats())
    metadata.update(
        status="complete",
        previews={
            name: f"assets/synthetic-comparison/optical-review/{name}.png"
            for name in ("before", "after", "overlay")
        },
    )
    complete["comparisons"][0]["optical_review"] = metadata
    for paths in (comparison["previews"], complete["comparisons"][0]["optical_review"]["previews"]):
        for relative in paths.values():
            path = tmp_path / "results/live" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png_bytes((50, 100, 150)))
    with (
        patch("sentinel_monitor.earth.initialize"),
        patch.object(EarthEngineAnalyzer, "__init__", return_value=None) as initialize,
        patch.object(
            EarthEngineAnalyzer, "analyze", side_effect=[result, failed, complete]
        ) as analyze,
        patch("sentinel_monitor.cli.build_site"),
    ):
        assert main(args) == 0
        first = read_records(tmp_path / "results", "live")[0]
        assert main([*args, "--optical-review-stretch"]) == 2
        failed_record = read_records(tmp_path / "results", "live")[0]
        failure_summary = json.loads(
            (tmp_path / "results/run-summary.json").read_text(encoding="utf-8")
        )
        assert failed_record["errors"] == []
        assert failed_record["status"] == first["status"]
        assert (
            failure_summary["sites"][0]["optical_review_errors"][0]["message"]
            == "Synthetic thumbnail failure"
        )
        assert main([*args, "--optical-review-stretch"]) == 0
        final = read_records(tmp_path / "results", "live")[0]
        assert main([*args, "--optical-review-stretch"]) == 0
        assert analyze.call_count == 3
        assert initialize.call_args.kwargs["optical_review_stretch"] is True
    assert first["analysis_key"] == final["analysis_key"]
    assert first["comparisons"][0]["id"] == final["comparisons"][0]["id"]
    assert first["generated_at"] != failed_record["generated_at"] != final["generated_at"]
    assert final["optical_review_stretch_requested"] is True
    assert len(list((tmp_path / "results/live/records").glob("*.json"))) == 1


def complete_cache_record(tmp_path):
    assets = tmp_path / "live/assets"
    metadata = review_metadata(100)
    apply_range(metadata, reflectance_stats())
    metadata.update(
        status="complete",
        previews={
            view: f"assets/synthetic-comparison/optical-review/{view}.png"
            for view in ("before", "after", "overlay")
        },
    )
    for relative in metadata["previews"].values():
        path = assets.parent / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png_bytes((100, 110, 120)))
    return assets, {
        "optical_review_stretch_requested": True,
        "comparisons": [
            {"id": "synthetic-comparison", "sensor": "optical", "optical_review": metadata}
        ],
    }


def test_cache_requires_complete_current_policy_metadata_and_stored_image_triple(tmp_path):
    assets, record = complete_cache_record(tmp_path)
    assert cache_complete(record, assets)
    for missing in (
        "schema_version",
        "scope",
        "reflectance_stats",
        "applied_stretch",
        "policy_version",
    ):
        broken = copy.deepcopy(record)
        del broken["comparisons"][0]["optical_review"][missing]
        assert not cache_complete(broken, assets), missing
    for key, value in (
        ("min", float("nan")),
        ("max", -1),
        ("gamma", 0),
        ("bands", ["B4", "B2", "B3"]),
    ):
        broken = copy.deepcopy(record)
        broken["comparisons"][0]["optical_review"]["applied_stretch"][key] = value
        assert not cache_complete(broken, assets), key
    path = assets / "synthetic-comparison/optical-review/after.png"
    original = path.read_bytes()
    path.unlink()
    assert not cache_complete(record, assets)
    path.write_bytes(b"not a PNG")
    assert not cache_complete(record, assets)
    path.write_bytes(original)
    assert cache_complete(record, assets)


def test_cache_never_confuses_fixed_original_files_with_alternate_assets(tmp_path):
    assets, record = complete_cache_record(tmp_path)
    fixed = assets / "synthetic-comparison/after.png"
    fixed.parent.mkdir(parents=True, exist_ok=True)
    fixed.write_bytes(png_bytes((255, 200, 150)))
    record["comparisons"][0]["optical_review"]["previews"]["after"] = (
        "assets/synthetic-comparison/after.png"
    )
    assert not cache_complete(record, assets)


def test_documented_unavailable_result_reuses_cache_but_error_and_pending_retry(tmp_path):
    assets, record = complete_cache_record(tmp_path)
    record["comparisons"][0]["optical_review"] = review_metadata(0, "No common valid cells")
    assert cache_complete(record, assets)
    for status in ("error", "pending"):
        record["comparisons"][0]["optical_review"]["status"] = status
        assert not cache_complete(record, assets)


def test_malformed_unavailable_statistics_never_satisfy_cache(tmp_path):
    assets, record = complete_cache_record(tmp_path)
    for reason in (
        "Missing or non-finite reflectance statistics",
        "Reflectance counts do not match common valid cells",
        "Inconsistent reflectance statistics",
        "Arbitrary incomplete metadata",
    ):
        record["comparisons"][0]["optical_review"] = review_metadata(100, reason)
        assert not cache_complete(record, assets)
    # Finite degenerate evidence is a legitimate terminal display limitation.
    stats = reflectance_stats()
    for key in stats:
        if key.endswith(("_min", "_max", "_p5", "_p95")):
            stats[key] = 0.2
    metadata = review_metadata(100)
    apply_range(metadata, stats)
    record["comparisons"][0]["optical_review"] = metadata
    assert cache_complete(record, assets)
    del metadata["reflectance_stats"]
    assert not cache_complete(record, assets)


def test_fixed_and_shared_endpoint_measurements_have_separate_scope(tmp_path):
    from sentinel_monitor.reports import preview_display_info

    assets = tmp_path / "assets"
    assets.mkdir()
    Image.new("RGB", (8, 8), (255, 200, 150)).save(assets / "fixed.png")
    Image.new("RGB", (8, 8), (150, 0, 90)).save(assets / "shared.png")
    comparison = {"sensor": "optical", "previews": {"before": "assets/fixed.png"}}
    fixed = preview_display_info(tmp_path, comparison)
    shared = preview_display_info(tmp_path, comparison, {"before": "assets/shared.png"})
    assert fixed["limits"][0]["channel"] == "Red"
    assert fixed["limits"][0]["endpoint"] == "maximum"
    assert shared["limits"][0]["channel"] == "Green"
    assert shared["limits"][0]["endpoint"] == "minimum"
    assert shared["opaque_pixels"] == {"before": 64}
    assert preview_display_info(tmp_path, comparison, {})["opaque_pixels"] == {}


def test_shared_endpoint_notice_requires_both_valid_opaque_views(tmp_path):
    from sentinel_monitor.reports import build_site, save_json

    sites = tmp_path / "sites.yaml"
    sites.write_text(
        "sites:\n  - id: synthetic-civilian\n    name: Synthetic civilian QA\n"
        "    latitude: 0\n    longitude: 3\n    size_m: 100\n",
        encoding="utf-8",
    )
    results = tmp_path / "results"
    assert (
        main(
            [
                "run",
                "--demo",
                "--sites",
                str(sites),
                "--settings",
                str(ROOT / "settings.yaml"),
                "--end-date",
                "2022-07-18",
                "--results",
                str(results),
                "--output",
                str(tmp_path / "initial"),
            ]
        )
        == 0
    )
    record = read_records(results, "demo")[0]
    record["review_previews_requested"] = True
    record["validation_case"] = {
        "id": "synthetic-only",
        "label": "Synthetic QA only",
        "review_status": "unreviewed",
    }
    comparison = next(c for c in record["comparisons"] if c["sensor"] == "optical")
    metadata = review_metadata(100)
    apply_range(metadata, reflectance_stats())
    paths = {
        v: f"assets/{comparison['id']}/optical-review/{v}.png"
        for v in ("before", "after", "overlay")
    }
    metadata.update(status="complete", previews=paths)
    comparison["optical_review"] = metadata
    for relative in comparison["previews"].values():
        Image.new("RGB", (8, 8), (255, 200, 150)).save(results / "demo" / relative)
    for relative in paths.values():
        path = results / "demo" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8), (150, 110, 90)).save(path)
    record_path = next((results / "demo/records").glob("*.json"))
    save_json(record_path, record)
    build_site(results, tmp_path / "complete", "demo")
    complete_html = (tmp_path / "complete/index.html").read_text(encoding="utf-8")
    assert "Fixed original PNG display limits" in complete_html
    assert "Shared-range PNG endpoint check: no channel" in complete_html
    target = results / "demo" / paths["after"]
    for state in ("missing", "invalid", "transparent"):
        target.unlink(missing_ok=True)
        if state == "invalid":
            target.write_bytes(b"not a PNG")
        elif state == "transparent":
            Image.new("RGBA", (8, 8), (255, 255, 255, 0)).save(target)
        output = tmp_path / state
        build_site(results, output, "demo")
        html = (output / "index.html").read_text(encoding="utf-8")
        assert "Shared-range PNG endpoint check is incomplete" in html
        assert "Shared-range PNG endpoint check: no channel" not in html
        assert "Fixed original PNG display limits" in html
    # Saturation of the alternate has its own heading and does not replace fixed notice.
    Image.new("RGB", (8, 8), (100, 0, 120)).save(target)
    build_site(results, tmp_path / "shared-saturated", "demo")
    html = (tmp_path / "shared-saturated/index.html").read_text(encoding="utf-8")
    assert "Shared-range PNG display limits" in html
    assert "Fixed original PNG display limits" in html
