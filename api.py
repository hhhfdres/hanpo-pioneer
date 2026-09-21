"""Dependency-free HTTP API and static dashboard server."""

from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .models import GeoPoint, dataclass_dict
from .service import FleetService


def dashboard_path() -> Path:
    candidates = []
    configured = os.environ.get("HANPO_DASHBOARD_DIR")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(
        [
            Path.cwd() / "apps" / "dashboard",
            Path(__file__).resolve().parents[2] / "apps" / "dashboard",
        ]
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return candidates[-1].resolve()


class HanPoRequestHandler(BaseHTTPRequestHandler):
    server_version = "HanPoPioneer/0.1"
    service: FleetService

    def log_message(self, format_string: str, *args: object) -> None:
        if self.server.verbose:  # type: ignore[attr-defined]
            super().log_message(format_string, *args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/health":
            self._json(self.service.system_health())
            return
        if parsed.path == "/api/v1/devices":
            if not self.service.list_devices():
                self.service.tick()
            self._json(self.service.serialize_device_list())
            return
        if parsed.path.startswith("/api/v1/devices/") and parsed.path.endswith("/drift"):
            self._handle_drift(parsed.path)
            return
        if parsed.path.startswith("/api/v1/devices/"):
            device_id = parsed.path.split("/")[4]
            try:
                status = self.service.get_device(device_id)
            except KeyError:
                self._error(HTTPStatus.NOT_FOUND, "device not found")
                return
            self._json(self.service.serialize_status(status))
            return
        if parsed.path == "/api/v1/rescue/plan":
            self._handle_rescue_plan(parse_qs(parsed.query))
            return
        self._static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if parsed.path == "/api/v1/telemetry":
            try:
                status = self.service.ingest(payload)
            except (KeyError, TypeError, ValueError) as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._json(self.service.serialize_status(status), HTTPStatus.CREATED)
            return
        if parsed.path == "/api/v1/simulate/tick":
            self.service.tick()
            self._json(self.service.serialize_device_list())
            return
        if parsed.path.startswith("/api/v1/devices/") and parsed.path.endswith("/scenario"):
            device_id = parsed.path.split("/")[4]
            try:
                status = self.service.set_scenario(
                    device_id, str(payload.get("scenario", "normal"))
                )
            except KeyError:
                self._error(HTTPStatus.NOT_FOUND, "device not found")
                return
            except ValueError as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._json(self.service.serialize_status(status))
            return
        if parsed.path.startswith("/api/v1/devices/") and parsed.path.endswith(
            "/acknowledge"
        ):
            device_id = parsed.path.split("/")[4]
            try:
                status = self.service.acknowledge(device_id)
            except KeyError:
                self._error(HTTPStatus.NOT_FOUND, "device not found")
                return
            self._json(self.service.serialize_status(status))
            return
        self._error(HTTPStatus.NOT_FOUND, "route not found")

    def _handle_drift(self, path: str) -> None:
        device_id = path.split("/")[4]
        try:
            points = self.service.predict_drift(device_id)
        except KeyError:
            self._error(HTTPStatus.NOT_FOUND, "device not found")
            return
        self._json(
            {
                "device_id": device_id,
                "points": [dataclass_dict(point) for point in points],
            }
        )

    def _handle_rescue_plan(self, query: Dict[str, list]) -> None:
        device_id = query.get("device_id", [""])[0]
        if not device_id:
            self._error(HTTPStatus.BAD_REQUEST, "device_id is required")
            return
        try:
            ship_position = GeoPoint(
                latitude=float(query.get("lat", ["30.3050"])[0]),
                longitude=float(query.get("lon", ["122.0850"])[0]),
            )
            speed = float(query.get("speed", ["8.0"])[0])
            plan = self.service.rescue_plan(device_id, ship_position, speed)
        except KeyError:
            self._error(HTTPStatus.NOT_FOUND, "device not found")
            return
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._json(dataclass_dict(plan))

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        if length > 1_000_000:
            raise ValueError("request body too large")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid JSON body") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _static(self, path: str) -> None:
        dashboard = dashboard_path()
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        candidate = (dashboard / relative).resolve()
        if dashboard not in candidate.parents and candidate != dashboard:
            self._error(HTTPStatus.FORBIDDEN, "invalid path")
            return
        if not candidate.is_file():
            self._error(HTTPStatus.NOT_FOUND, "file not found")
            return
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        if candidate.suffix in (".html", ".css", ".js"):
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _json(
        self,
        payload: Any,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message, "status": int(status)}, status)


class HanPoHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: Tuple[str, int],
        handler: type,
        service: FleetService,
        verbose: bool = False,
    ) -> None:
        super().__init__(server_address, handler)
        self.service = service
        self.verbose = verbose


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    service: Optional[FleetService] = None,
    verbose: bool = False,
) -> HanPoHTTPServer:
    resolved_service = service or FleetService()
    handler = type(
        "BoundHanPoRequestHandler",
        (HanPoRequestHandler,),
        {"service": resolved_service},
    )
    return HanPoHTTPServer((host, port), handler, resolved_service, verbose)
