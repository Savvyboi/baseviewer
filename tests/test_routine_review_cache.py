"""Exercise opt-in preview cache repair with synthetic analyzers; never contact EE."""

import json
from pathlib import Path

import pytest
from PIL import Image
from test_assessment import comparison, export

from sentinel_monitor import earth
from sentinel_monitor.assessment import assess
from sentinel_monitor.cli import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def synthetic_engine(monkeypatch):
    state = {"calls": 0, "status": "no_change_detected"}
    monkeypatch.setattr(earth, "initialize", lambda project: None)

    class Analyzer:
        def __init__(self, site, settings, period, key, assets, **options):
            self.assets = assets
            self.options = options
            self.key = key

        def analyze(self):
            state["calls"] += 1
            comparisons = []
            for sensor in self.options["requested_sensors"]:
                item = comparison(f"synthetic-{sensor}", state["status"], sensor)
                if state["status"] == "insufficient_data":
                    item["reason"] = "SYNTHETIC missing common coverage"
                else:
                    item["previews"] = {
                        view: f"assets/{item['id']}/{view}.png"
                        for view in ("before", "after", "overlay")
                    }
                    for relative in item["previews"].values():
                        target = self.assets.parent / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        Image.new("RGB", (16, 16), (80, 100, 120)).save(target)
                comparisons.append(item)
            return {
                "comparisons": comparisons,
                "errors": [],
                "changed_area": {
                    "optical_m2": 0 if "optical" in self.options["requested_sensors"] else None,
                    "radar_m2": 0 if "radar" in self.options["requested_sensors"] else None,
                    "overlap_m2": 0 if len(self.options["requested_sensors"]) == 2 else None,
                },
                "newest_observation": "2020-01-29T12:00:00+00:00",
                "workload_tag": "synthetic:" + self.key,
            }

    monkeypatch.setattr(earth, "EarthEngineAnalyzer", Analyzer)
    return state


def arguments(tmp_path, scope="optical"):
    return [
        "run",
        "--sensors",
        scope,
        "--review-previews",
        "--project",
        "synthetic-no-service",
        "--end-date",
        "2020-02-03",
        "--sites",
        str(ROOT / "tests" / "fixtures" / "sites.yaml"),
        "--settings",
        str(ROOT / "settings.yaml"),
        "--results",
        str(tmp_path / "results"),
        "--output",
        str(tmp_path / "site"),
    ]


def retained(tmp_path):
    path = next((tmp_path / "results/live/records").glob("*.json"))
    return path, json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scope", ["optical", "radar", "both"])
@pytest.mark.parametrize("view", ["before", "after", "overlay"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_opt_in_rerun_repairs_fixed_sources_and_refreshes_identity(
    tmp_path, synthetic_engine, scope, view, damage
):
    args = arguments(tmp_path, scope)
    assert main(args) == 0
    path, old = retained(tmp_path)
    original_record = path.read_bytes()
    assert main(args) == 0
    assert synthetic_engine["calls"] == 1
    assert path.read_bytes() == original_record
    item = old["comparisons"][0]
    relative = item["previews"][view]
    source = tmp_path / "results/live" / relative
    if damage == "missing":
        source.unlink()
    else:
        source.write_bytes(b"SYNTHETIC corrupt PNG")
    # The copied output is still present; it must not certify source cache readiness.
    assert (tmp_path / "site" / relative).is_file()
    assert main(args) == 0
    _, refreshed = retained(tmp_path)
    assert synthetic_engine["calls"] == 2
    assert refreshed["analysis_key"] == old["analysis_key"]
    assert refreshed["generated_at"] != old["generated_at"]
    with Image.open(source) as image:
        image.verify()
    if scope == "optical":
        old_review = {
            "mode": old["mode"],
            "case_id": "",
            "site_id": old["site"]["id"],
            "analysis_key": old["analysis_key"],
            "comparison_id": item["id"],
            "record_generated_at": old["generated_at"],
            "acquisition_date": item["acquisition_date"],
            "sensor": item["sensor"],
            "decision": "unclear",
            "note": "SYNTHETIC ONLY",
            "reviewed_at": "2026-10-18T00:00:00+00:00",
        }
        result = assess([refreshed], export(old_review), tmp_path / "results/live/assets")
        assert result["excluded_review_counts"] == {"stale_record": 1}
        assert result["denominators"]["reviewed_including_unclear"] == 0


def test_insufficient_opt_in_cache_needs_no_fabricated_pngs(tmp_path, synthetic_engine):
    synthetic_engine["status"] = "insufficient_data"
    args = arguments(tmp_path)
    assert main(args) == 0
    path, original = retained(tmp_path)
    assert original["comparisons"][0]["status"] == "insufficient_data"
    before = path.read_bytes()
    assert main(args) == 0
    assert synthetic_engine["calls"] == 1
    assert path.read_bytes() == before
