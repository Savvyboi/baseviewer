"""Exercise regular monitoring's actual shell without imagery or GitHub requests."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from sentinel_monitor import cli

ROOT = Path(__file__).resolve().parents[1]
INPUT_ENVIRONMENT = (
    "DEMO",
    "END_DATE",
    "SITE_ID",
    "REFRESH",
    "SENSORS",
    "SITES_PROFILE",
    "REVIEW_PREVIEWS",
    "OPTICAL_REVIEW_STRETCH",
    "RADAR_DIAGNOSTICS",
)


@pytest.fixture
def workflow():
    return yaml.load(
        (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def _input_environment(job, inputs):
    """Resolve the workflow's simple input/fallback expressions as Actions would."""
    environment = {}
    for name in INPUT_ENVIRONMENT:
        expression = job["env"][name]
        match = re.fullmatch(
            r"\$\{\{ inputs\.([a-z_]+)(?: \|\| (false|'both'|'optical'|'configured'))? \}\}",
            expression,
        )
        assert match is not None, expression
        input_name, fallback = match.groups()
        value = inputs.get(input_name)
        if not value:
            value = fallback.strip("'") if fallback else ""
        environment[name] = str(value).lower() if isinstance(value, bool) else value
    return environment


def _execute_shell(workflow, tmp_path, inputs=None, *, status=0, built=False):
    job = workflow["jobs"]["monitor"]
    step = next(step for step in job["steps"] if step.get("id") == "analysis")
    assert step["shell"] == "bash"
    windows_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(windows_bash) if os.name == "nt" else shutil.which("bash")
    if bash is None or (os.name == "nt" and not windows_bash.is_file()):
        pytest.skip("Git Bash on Windows or Bash elsewhere required for workflow shell tests")
    output = tmp_path / "github-output"
    environment = {
        **os.environ,
        **_input_environment(job, inputs or {}),
        "GITHUB_OUTPUT": output.as_posix(),
        "STUB_STATUS": str(status),
        "STUB_BUILT": "true" if built else "false",
    }
    # Capture every argument boundary, then simulate only the report/exit contract.
    stub = r"""
sentinel-monitor() {
    printf '%s\0' "$@"
    if [[ "$STUB_BUILT" == true ]]; then
        mkdir -p site
        printf '<html>synthetic report</html>\n' > site/index.html
    fi
    return "$STUB_STATUS"
}
"""
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", stub + step["run"]],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        timeout=10,
    )
    return result, output


def _execute_analysis(workflow, tmp_path, inputs=None, *, status=0, built=False):
    result, output = _execute_shell(workflow, tmp_path, inputs, status=status, built=built)
    assert not result.stderr, result.stderr.decode("utf-8", errors="replace")
    arguments = result.stdout.decode("utf-8").split("\0")
    assert arguments.pop() == ""
    parsed = cli.parser().parse_args(arguments)
    assert parsed.command == "run"
    assert parsed.results == Path(".history")
    assert parsed.output == Path("site")
    return result, arguments, parsed, output


def test_manual_input_defaults_and_schedule_fallbacks(workflow, tmp_path):
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert inputs["sites_profile"]["type"] == "choice"
    assert inputs["sites_profile"]["options"] == ["configured", "european-ports"]
    assert inputs["sites_profile"]["default"] == "configured"
    assert workflow["jobs"]["monitor"]["env"]["SITES_PROFILE"] == (
        "${{ inputs.sites_profile || 'configured' }}"
    )
    assert inputs["sensors"]["type"] == "choice"
    assert inputs["sensors"]["options"] == ["both", "optical", "radar"]
    assert inputs["sensors"]["default"] == "optical"
    for name in ("review_previews", "optical_review_stretch"):
        assert inputs[name]["type"] == "boolean"
        assert inputs[name]["default"] == "false"
    assert inputs["demo"]["default"] == "true"
    assert inputs["refresh"]["default"] == "false"
    assert inputs["radar_diagnostics"]["default"] == "false"
    assert inputs["publish"]["default"] == "false"
    assert workflow["jobs"]["monitor"]["env"]["SENSORS"] == "${{ inputs.sensors || 'optical' }}"

    # Scheduled events have no manual inputs, so use the optical sensor and live defaults.
    result, arguments, parsed, output = _execute_analysis(workflow, tmp_path)
    assert result.returncode == 0
    assert parsed.sensors == "optical"
    assert parsed.sites == Path("sites.yaml")
    assert parsed.settings == Path("settings.yaml")
    assert arguments[arguments.index("--sensors") + 1] == "optical"
    assert not parsed.demo and not parsed.refresh and not parsed.radar_diagnostics
    assert not parsed.review_previews and not parsed.optical_review_stretch
    assert parsed.end_date is None and parsed.site_id is None
    assert not output.exists()


@pytest.mark.parametrize("sensors", ["both", "optical", "radar"])
@pytest.mark.parametrize("review_previews", [False, True])
def test_sensor_choices_and_independent_review_previews(
    workflow, tmp_path, sensors, review_previews
):
    result, arguments, parsed, _ = _execute_analysis(
        workflow,
        tmp_path,
        {"demo": False, "sensors": sensors, "review_previews": review_previews},
    )
    assert result.returncode == 0
    assert parsed.sensors == sensors
    assert arguments[arguments.index("--sensors") + 1] == sensors
    assert parsed.review_previews is review_previews
    assert not parsed.optical_review_stretch
    assert not parsed.demo


@pytest.mark.parametrize("sensors", ["both", "optical"])
def test_shared_optical_review_and_existing_options_preserve_argument_boundaries(
    workflow, tmp_path, sensors
):
    site_id = "synthetic site; $(must-stay-an-argument)"
    result, _, parsed, _ = _execute_analysis(
        workflow,
        tmp_path,
        {
            "sensors": sensors,
            "review_previews": True,
            "optical_review_stretch": True,
            "end_date": "2026-10-12",
            "site_id": site_id,
            "refresh": True,
        },
    )
    assert result.returncode == 0
    assert parsed.review_previews and parsed.optical_review_stretch
    assert parsed.sensors == sensors
    assert parsed.end_date == "2026-10-12"
    assert parsed.site_id == [site_id]
    assert parsed.refresh


@pytest.mark.parametrize("sensors", ["both", "radar"])
def test_existing_radar_diagnostics_forwarding(workflow, tmp_path, sensors):
    result, _, parsed, _ = _execute_analysis(
        workflow, tmp_path, {"sensors": sensors, "radar_diagnostics": True}
    )
    assert result.returncode == 0
    assert parsed.sensors == sensors
    assert parsed.radar_diagnostics


def test_manual_demo_default_is_forwarded(workflow, tmp_path):
    defaults = {
        name: value["default"]
        for name, value in workflow["on"]["workflow_dispatch"]["inputs"].items()
        if "default" in value
    }
    result, _, parsed, _ = _execute_analysis(workflow, tmp_path, defaults)
    assert result.returncode == 0
    assert parsed.demo and parsed.sensors == "optical"
    assert not parsed.review_previews and not parsed.optical_review_stretch


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"optical_review_stretch": True}, "requires --review-previews"),
        (
            {"sensors": "radar", "review_previews": True, "optical_review_stretch": True},
            "requires requested optical",
        ),
        ({"sensors": "optical", "radar_diagnostics": True}, "requires requested radar"),
        ({"demo": True, "review_previews": True}, "require live imagery"),
        (
            {"demo": True, "review_previews": True, "optical_review_stretch": True},
            "require live imagery",
        ),
        ({"demo": True, "sensors": "both", "radar_diagnostics": True}, "require live imagery"),
    ],
)
def test_invalid_combinations_reach_existing_cli_validation(workflow, tmp_path, inputs, message):
    _, _, parsed, _ = _execute_analysis(workflow, tmp_path, inputs)
    with (
        patch("sentinel_monitor.cli.load_config") as load_config,
        patch("sentinel_monitor.earth.initialize") as initialize,
        pytest.raises(ValueError, match=message),
    ):
        cli.run(parsed)
    load_config.assert_not_called()
    initialize.assert_not_called()


@pytest.mark.parametrize("status", [0, 2])
@pytest.mark.parametrize("built", [False, True])
def test_partial_failure_status_and_report_ready_output(workflow, tmp_path, status, built):
    result, _, _, output = _execute_analysis(workflow, tmp_path, status=status, built=built)
    assert result.returncode == status
    if built:
        assert output.read_text(encoding="utf-8") == "built=true\n"
    else:
        assert not output.exists()
    job = workflow["jobs"]["monitor"]
    analysis = next(step for step in job["steps"] if step.get("id") == "analysis")
    assert analysis["continue-on-error"] == "true"
    save = next(step for step in job["steps"] if step.get("name", "").startswith("Save live"))
    assert save["if"] == "steps.analysis.outputs.built == 'true' && env.DEMO != 'true'"
    upload = next(
        step for step in job["steps"] if step.get("with", {}).get("name") == "monitoring-report"
    )
    assert upload["if"] == "always() && steps.analysis.outputs.built == 'true'"
    assert upload["with"]["path"].splitlines() == ["site/", ".history/run-summary.json"]


@pytest.mark.parametrize("profile", [None, "configured", "european-ports"])
def test_fixed_sites_profiles_map_only_known_paths(workflow, tmp_path, profile):
    inputs = {
        "sensors": "optical",
        "review_previews": True,
        "optical_review_stretch": True,
        "site_id": "synthetic-port",
        "end_date": "2026-10-12",
        "refresh": True,
    }
    if profile is not None:
        inputs["sites_profile"] = profile
    result, arguments, parsed, _ = _execute_analysis(workflow, tmp_path, inputs)
    assert result.returncode == 0
    if profile == "european-ports":
        assert parsed.sites == Path("pilots/european-ports/sites.yaml")
        assert parsed.settings == Path("pilots/european-ports/settings.yaml")
        assert arguments[arguments.index("--sites") + 1] == "pilots/european-ports/sites.yaml"
        assert arguments[arguments.index("--settings") + 1] == "pilots/european-ports/settings.yaml"
    else:
        assert parsed.sites == Path("sites.yaml")
        assert parsed.settings == Path("settings.yaml")
        assert "--sites" not in arguments and "--settings" not in arguments
    assert parsed.site_id == ["synthetic-port"]
    assert parsed.end_date == "2026-10-12" and parsed.refresh
    assert parsed.sensors == "optical"
    assert parsed.review_previews and parsed.optical_review_stretch


@pytest.mark.parametrize("profile", ["unknown", "../../outside", "european-ports; echo invalid"])
def test_unknown_sites_profile_fails_before_cli_or_report(workflow, tmp_path, profile):
    result, output = _execute_shell(workflow, tmp_path, {"sites_profile": profile}, built=True)
    assert result.returncode == 1
    assert result.stderr.decode("utf-8") == f"Unknown sites profile: {profile}\n"
    assert not result.stdout
    assert not output.exists()
    assert not (tmp_path / "site").exists()


def test_european_ports_profile_loads_with_bounded_site_selection(workflow, tmp_path):
    profile = ROOT / "pilots/european-ports"
    assert (profile / "sites.yaml").is_file()
    assert (profile / "settings.yaml").is_file()
    result, _, parsed, _ = _execute_analysis(
        workflow, tmp_path, {"sites_profile": "european-ports"}
    )
    assert result.returncode == 0
    sites, settings = cli.load_config(ROOT / parsed.sites, ROOT / parsed.settings)
    from dataclasses import replace

    _, active_settings = cli.load_config(
        ROOT / "tests" / "fixtures" / "sites.yaml", ROOT / "settings.yaml"
    )
    assert settings == replace(active_settings, max_sites=3)
    assert len(sites) == 3
    assert len(sites) <= settings.max_sites
    assert len({site.id for site in sites}) == len(sites)
    for site in sites:
        _, _, selected, _ = _execute_analysis(
            workflow,
            tmp_path,
            {"sites_profile": "european-ports", "site_id": site.id},
        )
        assert selected.site_id == [site.id]
        assert [item for item in sites if item.id in selected.site_id] == [site]
