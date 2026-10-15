"""Commands: validate, run, build and benchmark."""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .config import load_config, signature, windows
from .decisions import location_status
from .reports import build_site, save_json


def parser():
    root = argparse.ArgumentParser(description="Sentinel possible ground-change monitor")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ["validate", "run"]:
        command = commands.add_parser(name)
        command.add_argument("--sites", type=Path, default=Path("sites.yaml"))
        command.add_argument("--settings", type=Path, default=Path("settings.yaml"))
        command.add_argument("--end-date", help="Exclusive UTC end date, YYYY-MM-DD")
        command.add_argument("--site-id", action="append", help="Select a site; repeat for several")
    run = commands.choices["run"]
    run.add_argument("--project", default=os.environ.get("EE_PROJECT_ID"))
    run.add_argument(
        "--demo", action="store_true", help="Use synthetic fixtures; no Earth Engine calls"
    )
    run.add_argument("--demo-scenario", choices=["change", "quiet", "cloudy"], default="change")
    run.add_argument("--results", type=Path, default=Path("results"))
    run.add_argument("--output", type=Path, default=Path("site"))
    run.add_argument(
        "--refresh", action="store_true", help="Recompute a cached week for late imagery"
    )
    build = commands.add_parser("build")
    build.add_argument("--results", type=Path, default=Path("results"))
    build.add_argument("--output", type=Path, default=Path("site"))
    build.add_argument("--demo", action="store_true")
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--measured-eecu-hours", type=float, required=True)
    benchmark.add_argument("--measured-sites", type=int, default=20)
    benchmark.add_argument("--target-sites", type=int, default=200)
    benchmark.add_argument("--monthly-runs", type=int, default=5)
    return root


def run(args):
    mode = "demo" if args.demo else "live"
    sites, settings = load_config(args.sites, args.settings)
    if args.site_id:
        unknown = set(args.site_id) - {s.id for s in sites}
        if unknown:
            raise ValueError(f"Unknown site IDs: {', '.join(sorted(unknown))}")
        sites = [s for s in sites if s.id in args.site_id]
    if len(sites) > settings.max_sites:
        raise ValueError(
            f"Selected {len(sites)} sites exceeds max_sites={settings.max_sites}; "
            "select fewer sites or raise the limit after benchmarking"
        )
    period = windows(args.end_date)
    analyzer = None
    records = []
    has_errors = False
    for site in sites:
        key = signature(site, settings, period, f"demo:{args.demo_scenario}" if args.demo else mode)
        path = args.results / mode / "records" / f"{site.id}-{period['target_end']}-{key}.json"
        if path.exists() and not args.refresh:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not existing["errors"] and not any(
                c.get("preview_error") for c in existing["comparisons"]
            ):
                logging.info("Reusing completed result for %s", site.id)
                records.append(existing)
                continue
        started = time.monotonic()
        if args.demo:
            from .demo import analyze_demo

            result = analyze_demo(
                site, settings, period, key, args.results / mode / "assets", args.demo_scenario
            )
        else:
            from .earth import EarthEngineAnalyzer, initialize

            if analyzer is None:
                project = args.project or settings.earth_engine_project
                if not project:
                    raise ValueError(
                        "Set EE_PROJECT_ID or --project to an Earth Engine registered project"
                    )
                initialize(project)
                analyzer = EarthEngineAnalyzer
            result = analyzer(site, settings, period, key, args.results / mode / "assets").analyze()
        record = {
            "schema_version": 1,
            "analysis_version": settings.analysis_version,
            "analysis_key": key,
            "site": asdict(site),
            "grid": site.grid(),
            "windows": period,
            "mode": mode,
            "generated_at": datetime.now(UTC).isoformat(),
            "settings": asdict(settings),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            **result,
        }
        record["status"] = location_status(record["comparisons"], record["errors"])
        record["usable_sensors"] = sorted(
            {
                c["sensor"]
                for c in record["comparisons"]
                if c["status"] in {"possible_change", "no_change_detected"}
            }
        )
        record["has_errors"] = bool(
            record["errors"] or any(c.get("preview_error") for c in record["comparisons"])
        )
        has_errors |= record["has_errors"]
        save_json(path, record)
        records.append(record)
        logging.info("%s: %s", site.id, record["status"])
    build_site(args.results, args.output, mode)
    # This manifest is for this invocation only; history remains in records/.
    save_json(
        args.results / "run-summary.json",
        {
            "mode": mode,
            "windows": period,
            "site_count": len(records),
            "planned_area_m2": sum(s.size_m**2 for s in sites),
            "has_errors": has_errors,
            "sites": [
                {
                    "id": r["site"]["id"],
                    "status": r["status"],
                    "errors": r["errors"],
                    "preview_errors": [
                        {
                            "id": c["id"],
                            "error": c["preview_error"],
                            "message": c.get("preview_error_message", c["preview_error"]),
                        }
                        for c in r["comparisons"]
                        if c.get("preview_error")
                    ],
                    "workload_tag": r["workload_tag"],
                    "elapsed_seconds": r["elapsed_seconds"],
                }
                for r in records
            ],
        },
    )
    # Caller can preserve/publish useful partial results and still flag the failed run.
    return 2 if has_errors else 0


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            sites, settings = load_config(args.sites, args.settings)
            if args.site_id:
                if set(args.site_id) - {s.id for s in sites}:
                    raise ValueError("Unknown site-id")
                sites = [s for s in sites if s.id in args.site_id]
            print(
                json.dumps(
                    {
                        "sites": [{**asdict(s), "grid": s.grid()} for s in sites],
                        "windows": windows(args.end_date),
                        "max_sites": settings.max_sites,
                        "planned_area_m2": sum(s.size_m**2 for s in sites),
                    },
                    indent=2,
                )
            )
        elif args.command == "build":
            build_site(args.results, args.output, "demo" if args.demo else "live")
        elif args.command == "benchmark":
            import math

            if not math.isfinite(args.measured_eecu_hours) or args.measured_eecu_hours <= 0:
                raise ValueError("Measured EECU-hours must be positive and finite")
            if min(args.measured_sites, args.target_sites, args.monthly_runs) < 1:
                raise ValueError("Site and run counts must be positive")
            estimate = (
                args.measured_eecu_hours
                / args.measured_sites
                * args.target_sites
                * args.monthly_runs
            )
            print(
                json.dumps(
                    {
                        "estimated_monthly_eecu_hours": estimate,
                        "within_100_hour_planning_budget": estimate <= 100,
                        "note": "Extrapolation only. Input must include both sensors, baseline "
                        "work, summaries and previews; wall time is not EECU usage.",
                    },
                    indent=2,
                )
            )
        else:
            return run(args)
        return 0
    except Exception as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
