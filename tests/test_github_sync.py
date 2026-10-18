"""Only monitoring-list changes are published; independent GitHub edits survive."""

from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from sentinel_monitor.config import Site, load_sites
from sentinel_monitor.github_sync import GitHubPublisher, PublishError, git, merge_sites

FIRST = asdict(Site("first", "First", 10, 20, 1000))
SECOND = asdict(Site("second", "Second", 30, 40, 2000))
THIRD = asdict(Site("third", "Third", 50, 60, 3000))


def write_list(path, entries):
    path.write_text(yaml.safe_dump({"sites": entries}), encoding="utf-8")


@pytest.fixture
def publisher(tmp_path):
    local, remote = tmp_path / "local", tmp_path / "remote.git"
    local.mkdir()
    remote.mkdir()
    git(local, "init", "--initial-branch=main", "--quiet")
    git(local, "config", "user.name", "Test")
    git(local, "config", "user.email", "test@example.com")
    write_list(local / "sites.yaml", [FIRST])
    (local / "settings.yaml").write_text("max_sites: 20\n", encoding="utf-8")
    workflow = local / ".github/workflows/monitor.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("jobs:\n  list-publish: {}\n", encoding="utf-8")
    (local / "unrelated.txt").write_text("unchanged", encoding="utf-8")
    git(local, "add", ".")
    git(local, "commit", "--quiet", "-m", "Initial")
    git(remote, "init", "--bare", "--quiet")
    git(local, "remote", "add", "origin", str(remote))
    git(local, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    git(local, "remote", "set-url", "origin", "https://github.com/Example/monitor.git")
    publisher = GitHubPublisher(local / "sites.yaml")
    publisher.remote = str(remote)
    return publisher, local, remote


def test_publish_commits_only_sites_without_changing_local_branch(publisher):
    publisher, local, remote = publisher
    original_head = git(local, "rev-parse", "HEAD")
    (local / "unrelated.txt").write_text("private local work", encoding="utf-8")
    write_list(local / "sites.yaml", [FIRST, SECOND])
    sites, state = publisher.publish()
    assert [site.id for site in sites] == ["first", "second"]
    assert git(remote, "show", "main:unrelated.txt") == "unchanged"
    assert git(remote, "diff-tree", "--no-commit-id", "--name-only", "-r", "main") == "sites.yaml"
    assert git(local, "rev-parse", "HEAD") == original_head
    assert publisher.status(load_sites(local / "sites.yaml"))["synced"]
    assert state["commit_url"].startswith("https://github.com/Example/monitor/commit/")
    remote_head = git(remote, "rev-parse", "main")
    publisher.publish()
    assert git(remote, "rev-parse", "main") == remote_head
    write_list(local / "sites.yaml", [FIRST])
    publisher.publish()
    assert "second" not in git(remote, "show", "main:sites.yaml")


def test_three_way_merge_preserves_remote_additions_and_edits():
    changed = {**FIRST, "name": "Updated on GitHub"}
    assert merge_sites([FIRST], [FIRST, SECOND], [changed, THIRD]) == [changed, THIRD, SECOND]
    assert merge_sites([FIRST], [], [FIRST, THIRD]) == [THIRD]
    assert merge_sites([FIRST], [FIRST], []) == []
    assert merge_sites([], [SECOND], [SECOND]) == [SECOND]


@pytest.mark.parametrize(
    "local,remote",
    [
        ([{**FIRST, "size_m": 3000}], [{**FIRST, "size_m": 2000}]),
        ([], [{**FIRST, "name": "Renamed remotely"}]),
        ([{**FIRST, "latitude": 11}], []),
    ],
)
def test_conflicting_edits_are_rejected(local, remote):
    with pytest.raises(PublishError, match="changed on GitHub and locally"):
        merge_sites([FIRST], local, remote)


def test_missing_remote_workflow_blocks_submission(publisher):
    publisher, local, remote = publisher
    workflow = local / ".github/workflows/monitor.yml"
    workflow.write_text("jobs: {}\n", encoding="utf-8")
    git(local, "add", ".github/workflows/monitor.yml")
    git(local, "commit", "--quiet", "-m", "Older workflow")
    git(local, "push", "--quiet", publisher.remote, "HEAD:refs/heads/main")
    before = git(remote, "rev-parse", "main")
    write_list(local / "sites.yaml", [FIRST, SECOND])
    with pytest.raises(PublishError, match="not installed"):
        publisher.publish()
    assert git(remote, "rev-parse", "main") == before
    assert not publisher.state_path.exists()


def test_remote_site_limit_is_enforced(publisher):
    publisher, local, remote = publisher
    (local / "settings.yaml").write_text("max_sites: 1\n", encoding="utf-8")
    git(local, "add", "settings.yaml")
    git(local, "commit", "--quiet", "-m", "Reduce limit")
    git(local, "push", "--quiet", publisher.remote, "HEAD:refs/heads/main")
    before = git(remote, "rev-parse", "main")
    write_list(local / "sites.yaml", [FIRST, SECOND])
    with pytest.raises(PublishError, match="exceeds GitHub's 1-site limit"):
        publisher.publish()
    assert git(remote, "rev-parse", "main") == before


def test_workflow_publishes_list_without_google_and_keeps_schedule_gate():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/monitor.yml").read_text())
    jobs = workflow["jobs"]
    registry = jobs["list-publish"]
    assert "push" in registry["if"]
    assert any("sentinel-monitor build" in step.get("run", "") for step in registry["steps"])
    assert not any(
        "google-github-actions/auth" in step.get("uses", "") for step in registry["steps"]
    )
    assert "vars.MONITOR_ENABLED == 'true'" in jobs["monitor"]["if"]
    assert jobs["deploy"]["needs"] == ["monitor", "list-publish"]
