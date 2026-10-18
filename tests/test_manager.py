"""Persistent site management and actual monitor integration over loopback HTTP."""

import json
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from sentinel_monitor.cli import main, parser
from sentinel_monitor.config import load_sites
from sentinel_monitor.manager import ConflictError, Manager, make_server
from sentinel_monitor.reports import read_records

ROOT = Path(__file__).resolve().parents[1]


def manager_at(tmp_path):
    sites = tmp_path / "sites.yaml"
    sites.write_text("sites: []\n", encoding="utf-8")
    args = parser().parse_args(
        [
            "manage",
            "--sites",
            str(sites),
            "--settings",
            str(ROOT / "settings.yaml"),
            "--results",
            str(tmp_path / "results"),
            "--output",
            str(tmp_path / "report"),
            "--demo",
        ]
    )
    return Manager(args)


def entry(**changes):
    return {"name": "North field", "latitude": 51.2, "longitude": 46.1, "size_m": 1000, **changes}


def test_saved_sites_are_monitored_and_survive_restart(tmp_path):
    manager = manager_at(tmp_path)
    assert manager.state()["sites"] == []
    first = manager.add(entry())
    second = manager.add(entry(name="North field", size_m=2000))
    assert first["id"] != second["id"]
    assert manager.state()["planned_area_m2"] == 5_000_000
    assert all(site["status"] == "pending" for site in manager.state()["sites"])
    restored = Manager(manager.args)
    assert len(restored.state()["sites"]) == 2
    restored.start()
    restored.worker.join(timeout=20)
    assert restored.job["status"] == "complete"
    records = read_records(restored.args.results, "demo")
    assert {record["site"]["id"] for record in records} == {first["id"], second["id"]}
    assert all(site["status"] == "possible_change" for site in restored.state()["sites"])
    restored.remove(first["id"])
    assert len(load_sites(restored.args.sites)) == 1
    assert len(read_records(restored.args.results, "demo")) == 2
    latest = json.loads((restored.args.output / "latest.json").read_text())
    assert [record["site"]["id"] for record in latest] == [second["id"]]
    restored.remove(second["id"])
    assert Manager(restored.args).state()["sites"] == []
    with pytest.raises(ValueError, match="Add a site"):
        restored.start()


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "  "},
        {"name": "a" * 161},
        {"latitude": 91},
        {"longitude": -181},
        {"latitude": True},
        {"latitude": float("nan")},
        {"size_m": 31},
        {"size_m": 20001},
        {"size_m": 1000.5},
        {"size_m": True},
    ],
)
def test_invalid_sites_do_not_change_saved_list(tmp_path, changes):
    manager = manager_at(tmp_path)
    before = manager.args.sites.read_bytes()
    with pytest.raises(ValueError):
        manager.add(entry(**changes))
    assert manager.args.sites.read_bytes() == before


def test_site_limit_and_running_guard(tmp_path):
    manager = manager_at(tmp_path)
    settings = tmp_path / "settings.yaml"
    settings.write_text("max_sites: 1\n", encoding="utf-8")
    manager.args.settings = settings
    manager.add(entry())
    with pytest.raises(ConflictError, match="limited to 1"):
        manager.add(entry())
    manager.job["status"] = "running"
    with pytest.raises(ConflictError, match="running"):
        manager.remove("north-field")
    with pytest.raises(ConflictError, match="running"):
        manager.start()


def test_changed_coordinates_are_pending_and_report_escapes_names(tmp_path):
    manager = manager_at(tmp_path)
    site = manager.add(entry(name="<script>alert(1)</script>"))
    manager.start()
    manager.worker.join(timeout=20)
    assert manager.job["status"] == "complete"
    data = manager.args.sites.read_text(encoding="utf-8").replace(
        "latitude: 51.2", "latitude: 51.3"
    )
    manager.args.sites.write_text(data, encoding="utf-8")
    restored = Manager(manager.args)
    assert restored.state()["sites"][0]["id"] == site["id"]
    assert restored.state()["sites"][0]["status"] == "pending"
    html = (restored.args.output / "index.html").read_text(encoding="utf-8")
    assert "Awaiting first check" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@contextmanager
def served(manager):
    server = make_server(manager, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_persists_entries_blocks_foreign_writes_and_serves_report(tmp_path):
    manager = manager_at(tmp_path)
    with served(manager) as url:
        with urlopen(url) as response:
            page = response.read().decode("utf-8")
        token = re.search(r'name="sentinel-token" content="([^"]+)"', page)[1]
        request = Request(
            url + "/api/sites",
            json.dumps(entry()).encode(),
            {"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(request)
        assert exc.value.code == 403
        request.add_header("X-Sentinel-Token", token)
        with urlopen(request) as response:
            assert response.status == 201
            site = json.load(response)
        with urlopen(url + "/api/state") as response:
            assert json.load(response)["sites"][0]["status"] == "pending"
        with urlopen(url + "/report/index.html") as response:
            assert b"North field" in response.read()
        start = Request(url + "/api/run", headers={"X-Sentinel-Token": token}, method="POST")
        with urlopen(start) as response:
            assert response.status == 202
        manager.worker.join(timeout=20)
        with urlopen(url + "/api/state") as response:
            state = json.load(response)
            assert state["job"]["status"] == "complete"
            assert state["sites"][0]["status"] == "possible_change"
        foreign = Request(url + "/api/state", headers={"Host": "foreign.example"})
        with pytest.raises(HTTPError) as exc:
            urlopen(foreign)
        assert exc.value.code == 403
        with pytest.raises(HTTPError) as exc:
            urlopen(url + "/report/../sites.yaml")
        assert exc.value.code == 404
        invalid = Request(
            url + "/api/sites",
            json.dumps(entry(latitude=91)).encode(),
            {"Content-Type": "application/json", "X-Sentinel-Token": token},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(invalid)
        assert exc.value.code == 400
        remove = Request(
            url + "/api/sites/" + site["id"], headers={"X-Sentinel-Token": token}, method="DELETE"
        )
        with urlopen(remove) as response:
            assert response.status == 200
        assert load_sites(manager.args.sites) == []


def test_empty_list_can_build_and_run_without_earth_engine(tmp_path):
    manager = manager_at(tmp_path)
    arguments = [
        "--sites",
        str(manager.args.sites),
        "--results",
        str(manager.args.results),
        "--output",
        str(manager.args.output),
        "--demo",
    ]
    assert main(["build", *arguments]) == 0
    assert main(["run", *arguments, "--settings", str(manager.args.settings)]) == 0
    summary = json.loads((manager.args.results / "run-summary.json").read_text())
    assert summary["site_count"] == 0
