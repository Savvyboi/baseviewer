"""Atomic JSON history and a complete, self-contained static report."""

import json
import shutil
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, select_autoescape


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    temp.replace(path)


def read_records(results: Path, mode: str):
    records = []
    for file in sorted((results / mode / "records").glob("*.json")):
        record = json.loads(file.read_text(encoding="utf-8"))
        if record.get("mode") != mode:
            raise ValueError(f"Unexpected history mode in {file}")
        records.append(record)
    return sorted(
        records, key=lambda r: (r["windows"]["target_end"], r["generated_at"]), reverse=True
    )


def build_site(results: Path, output: Path, mode: str):
    records = read_records(results, mode)
    output.mkdir(parents=True, exist_ok=True)
    marker = output / ".sentinel-mode"
    if marker.exists() and marker.read_text(encoding="utf-8") != mode:
        raise ValueError("Output mode differs; choose a separate --output directory")
    marker.write_text(mode, encoding="utf-8")
    latest = {}
    for record in records:
        latest.setdefault(record["site"]["id"], record)
    assets = results / mode / "assets"
    if assets.exists():
        shutil.copytree(assets, output / "assets", dirs_exist_ok=True)
    # Public downloads contain only this mode's analysis output, never credentials.
    save_json(output / "history.json", records)
    save_json(output / "latest.json", list(latest.values()))
    env = Environment(autoescape=select_autoescape(default=True))
    template = env.from_string(
        files("sentinel_monitor").joinpath("templates/index.html").read_text(encoding="utf-8")
    )
    html = template.render(records=records, latest=list(latest.values()), mode=mode)
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / ".nojekyll").touch()
    return len(records)
