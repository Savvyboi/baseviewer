"""Submit only site-list edits through an isolated Git checkout."""

import json
import os
import re
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

import yaml

from .config import Site, load_config, load_sites
from .reports import save_json


class PublishError(ValueError):
    """A submission cannot be safely applied to the hosted monitoring list."""


def decode_sites(content):
    raw = yaml.safe_load(content)
    if not isinstance(raw, dict) or set(raw) != {"sites"} or not isinstance(raw["sites"], list):
        raise PublishError("Invalid sites list.")
    sites = [Site(**entry) for entry in raw["sites"]]
    if len({site.id for site in sites}) != len(sites):
        raise PublishError("Site IDs must be unique.")
    return [asdict(site) for site in sites]


def merge_sites(base, local, remote):
    """Apply local edits without overwriting independent edits on GitHub."""
    before = {site["id"]: site for site in base}
    wanted = {site["id"]: site for site in local}
    merged = {site["id"]: site for site in remote}
    for identifier in before.keys() | wanted.keys():
        previous, updated = before.get(identifier), wanted.get(identifier)
        if previous == updated:
            continue
        existing = merged.get(identifier)
        if existing != previous and existing != updated:
            raise PublishError(
                f"Site '{identifier}' changed on GitHub and locally. "
                "Resolve the differing entries before publishing."
            )
        if updated is None:
            merged.pop(identifier, None)
        else:
            merged[identifier] = updated
    return list(merged.values())


def git(directory, *arguments):
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PublishError(
            "Git is unavailable or the GitHub request timed out. Retry publishing."
        ) from exc
    if result.returncode:
        raise PublishError(
            f"Git {arguments[0]} failed. Check your GitHub access and network, "
            "then retry. No unrelated local files were submitted."
        )
    return result.stdout.strip()


class GitHubPublisher:
    def __init__(self, sites_path):
        self.sites_path = sites_path.resolve()
        self.root = Path(git(self.sites_path.parent, "rev-parse", "--show-toplevel"))
        self.relative = self.sites_path.relative_to(self.root).as_posix()
        if self.relative != "sites.yaml":
            raise PublishError("GitHub submission currently requires the repository's sites.yaml.")
        self.remote = git(self.root, "remote", "get-url", "origin")
        match = re.fullmatch(
            r"(?:https://github\.com/|git@github\.com:)([\w.-]+)/([\w.-]+?)(?:\.git)?",
            self.remote,
        )
        if not match:
            raise PublishError("Set origin to this project's GitHub repository before publishing.")
        self.owner, self.repository = match.groups()
        self.state_path = self.sites_path.with_suffix(".github-sync.json")
        self.branch = "main"
        self.repository_url = f"https://github.com/{self.owner}/{self.repository}"
        self.pages_url = f"https://{self.owner.lower()}.github.io/{self.repository}/"
        self.actions_url = self.repository_url + "/actions/workflows/monitor.yml"

    def snapshot(self):
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if data.get("repository") == self.repository_url and data.get("branch") == self.branch:
                return data
        return None

    def status(self, sites):
        previous = self.snapshot()
        return {
            "repository_url": self.repository_url,
            "pages_url": self.pages_url,
            "actions_url": self.actions_url,
            "synced": bool(previous and previous["sites"] == [asdict(site) for site in sites]),
            "commit_url": previous.get("commit_url") if previous else None,
        }

    def publish(self):
        local = [asdict(site) for site in load_sites(self.sites_path)]
        previous = self.snapshot()
        base = (
            previous["sites"]
            if previous
            else decode_sites(git(self.root, "show", f"HEAD:{self.relative}"))
        )
        with tempfile.TemporaryDirectory(prefix="sentinel-sites-") as directory:
            checkout = Path(directory)
            git(checkout, "init", "--quiet")
            git(checkout, "remote", "add", "origin", self.remote)
            git(checkout, "fetch", "--quiet", "--depth=1", "origin", self.branch)
            git(checkout, "checkout", "--quiet", "--detach", "FETCH_HEAD")
            workflow = checkout / ".github/workflows/monitor.yml"
            if not workflow.exists() or "list-publish:" not in workflow.read_text(encoding="utf-8"):
                raise PublishError(
                    "The site-list publishing workflow is not installed on GitHub main yet. "
                    "Merge the setup changes first, then retry publishing."
                )
            remote = [asdict(site) for site in load_sites(checkout / self.relative)]
            merged = merge_sites(base, local, remote)
            target = checkout / self.relative
            target.write_text(
                yaml.safe_dump({"sites": merged}, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            sites, settings = load_config(target, checkout / "settings.yaml")
            if len(sites) > settings.max_sites:
                raise PublishError(
                    f"The merged list exceeds GitHub's {settings.max_sites}-site limit."
                )
            if merged != remote:
                git(checkout, "add", "--", self.relative)
                git(
                    checkout,
                    "-c",
                    "user.name=Sentinel site manager",
                    "-c",
                    f"user.email=site-manager@{self.owner.lower()}.users.noreply.github.com",
                    "commit",
                    "--quiet",
                    "-m",
                    "Update monitoring site list",
                )
                # A normal push refuses concurrent updates rather than overwriting them.
                git(checkout, "push", "--quiet", "origin", f"HEAD:refs/heads/{self.branch}")
            commit = git(checkout, "rev-parse", "HEAD")
            state = {
                "repository": self.repository_url,
                "branch": self.branch,
                "sites": merged,
                "commit_url": self.repository_url + "/commit/" + commit,
            }
            save_json(self.state_path, state)
            return sites, state
