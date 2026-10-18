"""Execute manual workflow argument construction with a stub, never imagery analysis."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from sentinel_monitor.cli import parser

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case_id", ["park-fire-event", "genoa-morandi-east-demolition"])
@pytest.mark.parametrize("sensors", ["optical", "radar", "both"])
def test_manual_imagery_shell_forwards_scope_through_both_manifest_mappings(case_id, sensors):
    workflow = yaml.load(
        (ROOT / ".github/workflows/validation.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    job = workflow["jobs"]["imagery"]
    step = next(
        step for step in job["steps"] if "sentinel-monitor review-case" in step.get("run", "")
    )
    assert step["shell"] == "bash"
    windows_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(windows_bash) if os.name == "nt" and windows_bash.is_file() else shutil.which("bash")
    if bash is None:
        pytest.skip("Bash required to execute the actual workflow shell; available in Actions")
    environment = {
        **os.environ,
        "CASE_ID": case_id,
        "SENSORS": sensors,
        "IMAGERY_DIAGNOSTICS": "false",
        "OPTICAL_REVIEW_STRETCH": "false",
    }
    # Shell function captures argument boundaries and prevents any real CLI/EE call.
    stub = 'sentinel-monitor() { printf "%s\\n" "$@"; }\n'
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-c", stub + step["run"]],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    arguments = result.stdout.splitlines()
    parsed = parser().parse_args(arguments)
    assert parsed.command == "review-case"
    assert parsed.case == case_id
    assert parsed.sensors == sensors
    assert arguments[arguments.index("--sensors") + 1] == sensors
    expected = (
        "sentinel2-cases.json" if case_id == "genoa-morandi-east-demolition" else "cases.json"
    )
    assert parsed.case_file == Path("validation") / expected
