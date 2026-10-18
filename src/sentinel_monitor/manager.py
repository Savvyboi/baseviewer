"""Loopback-only management UI backed by the monitor's persistent YAML list."""

import json
import logging
import mimetypes
import re
import secrets
import tempfile
import threading
import unicodedata
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

from .config import Site, load_config
from .reports import build_site, read_records


class ConflictError(ValueError):
    """A requested action conflicts with a running check or the site limit."""


class Manager:
    def __init__(self, args):
        if args.output is None:
            args.output = Path("site-manager-demo" if args.demo else "site-manager")
        self.args = args
        self.mode = "demo" if args.demo else "live"
        self.lock = threading.RLock()
        self.job = {
            "status": "idle",
            "message": (
                "Ready to run a synthetic demo check."
                if args.demo
                else "Save sites locally, then publish the list to GitHub for weekly monitoring."
            ),
        }
        self.worker = None
        self.publisher = None
        self.publish_error = None
        if not args.demo:
            from .github_sync import GitHubPublisher, PublishError

            try:
                self.publisher = GitHubPublisher(args.sites)
            except PublishError as exc:
                self.publish_error = str(exc)
        sites, _ = load_config(args.sites, args.settings)
        build_site(args.results, args.output, self.mode, sites)

    def state(self):
        with self.lock:
            sites, settings = load_config(self.args.sites, self.args.settings)
            latest = {}
            for record in read_records(self.args.results, self.mode) if self.args.demo else []:
                latest.setdefault(record["site"]["id"], record)
            published = self.publisher.snapshot() if self.publisher else None
            published_sites = {site["id"]: site for site in published["sites"]} if published else {}
            entries = []
            for site in sites:
                record = latest.get(site.id)
                current = record and all(
                    record["site"][key] == getattr(site, key)
                    for key in ("latitude", "longitude", "size_m")
                )
                status = record["status"] if current else "pending"
                if not self.args.demo:
                    status = (
                        "published" if published_sites.get(site.id) == asdict(site) else "draft"
                    )
                entries.append(
                    {
                        **asdict(site),
                        "status": status,
                        "checked_through": record["windows"]["target_end"] if current else None,
                    }
                )
            return {
                "sites": entries,
                "max_sites": settings.max_sites,
                "planned_area_m2": sum(site.size_m**2 for site in sites),
                "mode": self.mode,
                "github": self.publisher.status(sites) if self.publisher else None,
                "publish_error": self.publish_error,
                "job": dict(self.job),
            }

    def _editable(self):
        if self.job["status"] == "running":
            raise ConflictError(
                "An operation is running. Wait for it to finish before changing sites."
            )

    def _save(self, sites):
        destination = self.args.sites.resolve()
        # Replace the entire list atomically, so interrupted writes keep the old configuration.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=destination.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                yaml.safe_dump(
                    {"sites": [asdict(site) for site in sites]},
                    stream,
                    allow_unicode=True,
                    sort_keys=False,
                )
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        build_site(self.args.results, self.args.output, self.mode, sites)

    def add(self, data):
        with self.lock:
            self._editable()
            sites, settings = load_config(self.args.sites, self.args.settings)
            if len(sites) >= settings.max_sites:
                raise ConflictError(
                    f"The monitoring list is limited to {settings.max_sites} sites. "
                    "Raise max_sites in settings.yaml to add more."
                )
            if not isinstance(data, dict) or set(data) != {
                "name",
                "latitude",
                "longitude",
                "size_m",
            }:
                raise ValueError("Provide a name, latitude, longitude and width in metres.")
            name = data["name"]
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
                raise ValueError("Name must contain between 1 and 160 characters.")
            normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
            base = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")[:40] or "site"
            identifier = base
            existing = {site.id for site in sites}
            number = 2
            while identifier in existing:
                identifier = f"{base}-{number}"
                number += 1
            site = Site(
                identifier, name.strip(), data["latitude"], data["longitude"], data["size_m"]
            )
            sites.append(site)
            self._save(sites)
            return asdict(site)

    def remove(self, identifier):
        with self.lock:
            self._editable()
            sites, _ = load_config(self.args.sites, self.args.settings)
            if identifier not in {site.id for site in sites}:
                raise LookupError("Site not found.")
            self._save([site for site in sites if site.id != identifier])

    def publish(self):
        with self.lock:
            self._editable()
            if self.publisher is None:
                raise ValueError(
                    self.publish_error or "GitHub publishing is unavailable in demo mode."
                )
            self.job = {"status": "running", "message": "Submitting the saved list to GitHub…"}

            def work():
                try:
                    sites, _ = self.publisher.publish()
                    with self.lock:
                        self._save(sites)
                    job = {
                        "status": "complete",
                        "message": "List saved on GitHub. Pages is updating; weekly monitoring "
                        "will use this list when the repository schedule is enabled.",
                    }
                except Exception as exc:
                    logging.exception("GitHub site-list submission failed")
                    job = {"status": "error", "message": str(exc)}
                with self.lock:
                    self.job = job

            self.worker = threading.Thread(target=work, daemon=True)
            self.worker.start()

    def start(self):
        if not self.args.demo:
            raise ValueError("Monitoring runs on GitHub. Publish the saved list instead.")
        from .cli import parser, run

        with self.lock:
            self._editable()
            sites, settings = load_config(self.args.sites, self.args.settings)
            if not sites:
                raise ValueError("Add a site before running monitoring.")
            if len(sites) > settings.max_sites:
                raise ConflictError("The list exceeds max_sites in settings.yaml.")
            arguments = [
                "run",
                "--sites",
                str(self.args.sites),
                "--settings",
                str(self.args.settings),
                "--results",
                str(self.args.results),
                "--output",
                str(self.args.output),
            ]
            if self.args.demo:
                arguments.append("--demo")
            if self.args.project:
                arguments.extend(["--project", self.args.project])
            run_args = parser().parse_args(arguments)
            self.job = {"status": "running", "message": f"Checking {len(sites)} saved sites…"}

            def work():
                try:
                    code = run(run_args)
                    job = {
                        "status": "complete" if code == 0 else "partial_error",
                        "message": (
                            "Check complete. Open the report for results."
                            if code == 0
                            else "Check finished with errors. Open the report for details."
                        ),
                    }
                except Exception as exc:
                    logging.exception("Monitoring check failed")
                    job = {"status": "error", "message": f"Check failed: {exc}"}
                with self.lock:
                    self.job = job

            self.worker = threading.Thread(target=work, daemon=True)
            self.worker.start()


def make_server(manager, port):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, content_type="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _allowed(self, mutation=False):
            # Reject DNS rebinding and browser requests from other origins.
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") not in {expected, f"localhost:{self.server.server_port}"}:
                self._send(403, {"error": "Use the local management URL."})
                return False
            if mutation and not secrets.compare_digest(
                self.headers.get("X-Sentinel-Token", ""), token
            ):
                self._send(403, {"error": "Reload the local management page and try again."})
                return False
            return True

        def do_GET(self):
            if not self._allowed():
                return
            route = urlsplit(self.path).path
            try:
                if route == "/":
                    page = (
                        files("sentinel_monitor")
                        .joinpath("templates/manage.html")
                        .read_text(encoding="utf-8")
                        .replace("__TOKEN__", token)
                    )
                    self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
                elif route == "/manager.js":
                    script = files("sentinel_monitor").joinpath("templates/manager.js").read_bytes()
                    self._send(200, script, "text/javascript; charset=utf-8")
                elif route == "/api/state":
                    self._send(200, manager.state())
                elif route.startswith("/report/"):
                    output = manager.args.output.resolve()
                    relative = unquote(route.removeprefix("/report/")) or "index.html"
                    target = (output / relative).resolve()
                    if not target.is_relative_to(output) or not target.is_file():
                        self._send(404, {"error": "Report file not found."})
                        return
                    self._send(
                        200,
                        target.read_bytes(),
                        mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                    )
                else:
                    self._send(404, {"error": "Not found."})
            except Exception:
                logging.exception("Unable to load management page")
                self._send(500, {"error": "Unable to load the list. Check the server log."})

        def do_POST(self):
            if not self._allowed(mutation=True):
                return
            try:
                route = urlsplit(self.path).path
                if route == "/api/sites":
                    if self.headers.get("Content-Type") != "application/json":
                        raise ValueError("Send the site as application/json.")
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 8192:
                        raise ValueError("Site request must be between 1 and 8192 bytes.")
                    site = manager.add(json.loads(self.rfile.read(length)))
                    self._send(201, site)
                elif route == "/api/publish":
                    manager.publish()
                    self._send(202, {"message": "Submitting sites to GitHub."})
                elif route == "/api/run":
                    manager.start()
                    self._send(202, {"message": "Monitoring started."})
                else:
                    self._send(404, {"error": "Not found."})
            except ConflictError as exc:
                self._send(409, {"error": str(exc)})
            except (ValueError, TypeError) as exc:
                self._send(400, {"error": str(exc)})
            except Exception:
                logging.exception("Unable to save sites or start monitoring")
                self._send(500, {"error": "Action failed. Check the server log."})

        def do_DELETE(self):
            if not self._allowed(mutation=True):
                return
            try:
                route = urlsplit(self.path).path
                if not route.startswith("/api/sites/"):
                    self._send(404, {"error": "Not found."})
                    return
                manager.remove(unquote(route.removeprefix("/api/sites/")))
                self._send(200, {"message": "Site removed from monitoring. History retained."})
            except ConflictError as exc:
                self._send(409, {"error": str(exc)})
            except LookupError as exc:
                self._send(404, {"error": str(exc)})
            except Exception:
                logging.exception("Unable to remove site")
                self._send(500, {"error": "Unable to remove the site. Check the server log."})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(args):
    manager = Manager(args)
    with make_server(manager, args.port) as server:
        logging.info("Manage monitoring sites at http://127.0.0.1:%s", server.server_port)
        logging.info("Changes save to %s", args.sites.resolve())
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logging.info("Stopping local manager")
        finally:
            if manager.worker is not None and manager.worker.is_alive():
                logging.info("Waiting for the current monitoring check to finish")
                manager.worker.join()
