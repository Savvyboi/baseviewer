"""Categories persist through management/publication; reports exclude retired radar data."""

import copy
import json
import re
from dataclasses import asdict, replace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_github_sync import publisher, write_list  # noqa: F401
from test_manager import entry, manager_at, served

from sentinel_monitor.config import Settings, Site, signature, windows
from sentinel_monitor.github_sync import merge_sites
from sentinel_monitor.manager import ConflictError, Manager
from sentinel_monitor.reports import build_site, read_records, save_json


def test_categories_survive_restart_and_relabel_cached_results(tmp_path):
    manager = manager_at(tmp_path)
    site = manager.add(entry(category="  Fields  "))
    assert site["category"] == "Fields"
    manager.start()
    manager.worker.join(timeout=20)
    assert manager.job["status"] == "complete"
    paths = list((manager.args.results / "demo/records").glob("*.json"))
    original = paths[0].read_bytes()
    manager.categorize(site["id"], {"category": "Air bases"})
    restored = Manager(manager.args)
    assert restored.state()["sites"][0]["category"] == "Air bases"
    assert restored.state()["sites"][0]["status"] == "possible_change"
    assert paths[0].read_bytes() == original
    published = json.loads((manager.args.output / "history.json").read_text())
    assert published[0]["site"]["category"] == "Air bases"
    restored.categorize(site["id"], {"category": " "})
    assert restored.state()["sites"][0]["category"] == ""
    assert "Uncategorized" in (manager.args.output / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("category", [None, 1, True, [], "a" * 81])
def test_invalid_categories_do_not_change_saved_sites(tmp_path, category):
    manager = manager_at(tmp_path)
    site = manager.add(entry())
    original = manager.args.sites.read_bytes()
    with pytest.raises(ValueError):
        manager.categorize(site["id"], {"category": category})
    with pytest.raises(ValueError):
        manager.add(entry(category=category))
    assert manager.args.sites.read_bytes() == original


def test_category_updates_obey_job_guard_and_missing_site(tmp_path):
    manager = manager_at(tmp_path)
    with pytest.raises(LookupError):
        manager.categorize("missing", {"category": "Fields"})
    manager.job["status"] = "running"
    with pytest.raises(ConflictError):
        manager.categorize("missing", {"category": "Fields"})


def test_category_api_requires_token_validates_and_persists(tmp_path):
    manager = manager_at(tmp_path)
    site = manager.add(entry())
    with served(manager) as url:
        page = urlopen(url).read().decode()
        token = re.search(r'name="sentinel-token" content="([^"]+)"', page)[1]
        request = Request(
            url + "/api/sites/" + site["id"],
            json.dumps({"category": "Air bases"}).encode(),
            {"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 403
        request.add_header("X-Sentinel-Token", token)
        with urlopen(request) as response:
            assert response.status == 200
            assert json.load(response)["category"] == "Air bases"
        request.data = json.dumps({"category": None}).encode()
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 400
        request.full_url = url + "/api/sites/missing"
        request.data = json.dumps({"category": "Fields"}).encode()
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 404
    assert Manager(manager.args).state()["sites"][0]["category"] == "Air bases"


def test_category_does_not_invalidate_science_cache():
    site = Site("field", "Field", 0, 3)
    period = windows("2026-10-12")
    assert signature(site, Settings(), period, "live") == signature(
        replace(site, category="Fields"), Settings(), period, "live"
    )


def test_category_changes_merge_with_remote_additions():
    site = asdict(Site("field", "Field", 0, 3))
    changed = {**site, "category": "Fields"}
    other = asdict(Site("other", "Other", 1, 3, category="Air bases"))
    assert merge_sites([site], [changed], [site, other]) == [changed, other]


def test_category_publishing_normalizes_old_sync_snapshot(publisher):  # noqa: F811
    publisher, local, remote = publisher
    sites, snapshot = publisher.publish()
    for site in snapshot["sites"]:
        site.pop("category")
    save_json(publisher.state_path, snapshot)
    # Upgrading an old snapshot must not mark unchanged sites as local edits.
    assert publisher.status(sites)["synced"]
    site = replace(sites[0], category="Air bases")
    write_list(local / "sites.yaml", [asdict(site)])
    published, snapshot = publisher.publish()
    assert published[0].category == "Air bases"
    assert snapshot["sites"][0]["category"] == "Air bases"
    assert publisher.status(published)["synced"]


def test_report_discards_radar_flags_errors_assets_and_uses_current_categories(tmp_path):
    manager = manager_at(tmp_path)
    site = manager.add(entry(category='<b>Fields & "farms"</b>'))
    manager.start()
    manager.worker.join(timeout=20)
    record = read_records(manager.args.results, "demo")[0]
    comparison = record["comparisons"][0]
    comparison.update(status="no_change_detected", changed_area_m2=0, changed_cells=0)
    radar = {
        **copy.deepcopy(comparison),
        "id": "old-radar",
        "sensor": "radar",
        "status": "possible_change",
        "acquisition_times": ["2026-10-19T12:00:00Z"],
        "previews": {"before": "assets/old-radar/before.png"},
    }
    record["comparisons"].append(radar)
    record["errors"] = [{"sensor": "radar", "message": "Old radar failure"}]
    record.update(status="possible_change", has_errors=True, usable_sensors=["optical", "radar"])
    record["changed_area"] = {"optical_m2": 0, "radar_m2": 900, "overlap_m2": 0}
    record["source_diagnostics"] = {"optical": {}, "radar": {"old": True}}
    record["settings"]["radar_threshold_db"] = 3
    record["radar_diagnostics_requested"] = True
    record["site"].pop("category")
    record.pop("requested_sensors", None)
    path = next((manager.args.results / "demo/records").glob("*.json"))
    save_json(path, record)
    old_asset = manager.args.output / "assets/old-radar/before.png"
    old_asset.parent.mkdir(parents=True)
    old_asset.write_bytes(b"old radar preview")
    original = path.read_bytes()
    build_site(manager.args.results, manager.args.output, "demo", [Site(**site)], optical_only=True)
    assert path.read_bytes() == original
    assert not old_asset.exists()
    published = json.loads((manager.args.output / "latest.json").read_text())[0]
    assert published["status"] == "no_change_detected" and published["has_errors"] is False
    assert published["usable_sensors"] == ["optical"]
    assert published["changed_area"] == {"optical_m2": 0}
    assert published["site"]["category"] == site["category"]
    assert "radar" not in json.dumps(published)
    assert published["newest_observation"] == comparison["acquisition_times"][0]
    html = (manager.args.output / "index.html").read_text(encoding="utf-8")
    assert "Sentinel-1" not in html and "radar" not in html
    assert '<b>Fields & "farms"</b>' not in html
    assert "&lt;b&gt;Fields &amp;" in html
    assert 'id="category-filter"' in html
    assert 'data-category="&lt;b&gt;Fields &amp;' in html
