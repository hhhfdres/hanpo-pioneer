"""Shared domain models for telemetry, control, and rescue workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, List, Optional


class WearerMode(str, Enum):
    ACTIVE = "active"
    RESTING = "resting"
    UNCONSCIOUS = "unconscious"


class AlertLevel(str, Enum):
    NORMAL = "normal"
    WATCH = "watch"
    SOS = "sos"


class EnergySource(str, Enum):
    CAPACITOR = "capacitor"
    BATTERY = "battery"
    HYBRID = "hybrid"
    PREHEAT = "preheat"


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float

    def distance_to(self, other: "GeoPoint") -> float:
        """Return great-circle distance in meters."""
        earth_radius_m = 6_371_000.0
        lat1 = radians(self.latitude)
        lat2 = radians(other.latitude)
        delta_lat = lat2 - lat1
        delta_lon = radians(other.longitude - self.longitude)
        value = (
            sin(delta_lat / 2.0) ** 2
            + cos(lat1) * cos(lat2) * sin(delta_lon / 2.0) ** 2
        )
        return 2.0 * earth_radius_m * asin(min(1.0, sqrt(value)))


@dataclass
class Telemetry:
    device_id: str
    timestamp: float
    core_temp_c: float
    surface_temp_c: float
    ambient_temp_c: float
    capacitor_soc: float
    battery_soc: float
    latitude: float
    longitude: float
    stationary_seconds: float = 0.0
    motion_score: float = 0.0
    speed_mps: float = 0.0
    heart_rate_bpm: Optional[float] = None
    battery_voltage_v: float = 1.2
    battery_current_a: float = 0.0
    sequence: int = 0

    @property
    def position(self) -> GeoPoint:
        return GeoPoint(self.latitude, self.longitude)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Telemetry":
        required = {
            "device_id",
            "timestamp",
            "core_temp_c",
            "surface_temp_c",
            "ambient_temp_c",
            "capacitor_soc",
            "battery_soc",
            "latitude",
            "longitude",
        }
        missing = sorted(required.difference(payload))
        if missing:
            raise ValueError("missing telemetry fields: " + ", ".join(missing))
        return cls(
            device_id=str(payload["device_id"]),
            timestamp=float(payload["timestamp"]),
            core_temp_c=float(payload["core_temp_c"]),
            surface_temp_c=float(payload["surface_temp_c"]),
            ambient_temp_c=float(payload["ambient_temp_c"]),
            capacitor_soc=float(payload["capacitor_soc"]),
            battery_soc=float(payload["battery_soc"]),
            latitude=float(payload["latitude"]),
            longitude=float(payload["longitude"]),
            stationary_seconds=float(payload.get("stationary_seconds", 0.0)),
            motion_score=float(payload.get("motion_score", 0.0)),
            speed_mps=float(payload.get("speed_mps", 0.0)),
            heart_rate_bpm=(
                float(payload["heart_rate_bpm"])
                if payload.get("heart_rate_bpm") is not None
                else None
            ),
            battery_voltage_v=float(payload.get("battery_voltage_v", 1.2)),
            battery_current_a=float(payload.get("battery_current_a", 0.0)),
            sequence=int(payload.get("sequence", 0)),
        )


@dataclass
class ZoneOutput:
    chest: float = 0.0
    back: float = 0.0
    waist: float = 0.0

    def total_duty(self) -> float:
        return self.chest + self.back + self.waist

    def scaled(self, factor: float) -> "ZoneOutput":
        bounded = max(0.0, min(1.0, factor))
        return ZoneOutput(
            chest=max(0.0, min(1.0, self.chest * bounded)),
            back=max(0.0, min(1.0, self.back * bounded)),
            waist=max(0.0, min(1.0, self.waist * bounded)),
        )


@dataclass
class ControlDecision:
    mode: WearerMode
    zones: ZoneOutput
    power_w: float
    overheat_latched: bool
    reason: str
    pid_output: float


@dataclass
class EnergyDecision:
    source: EnergySource
    power_budget_w: float
    preheating: bool
    reason: str


@dataclass
class AlertEvent:
    device_id: str
    created_at: float
    message: str
    latitude: float
    longitude: float
    core_temp_c: float
    capacitor_soc: float
    battery_soc: float
    acknowledged: bool = False


@dataclass
class RescuePlan:
    device_id: str
    generated_at: float
    route: List[GeoPoint]
    distance_m: float
    eta_minutes: float
    priority_score: float
    rationale: str


@dataclass
class DeviceStatus:
    telemetry: Telemetry
    mode: WearerMode
    alert_level: AlertLevel
    control: ControlDecision
    energy: EnergyDecision
    rescue_priority: float
    last_alert_at: Optional[float] = None
    alert_acknowledged: bool = True
    event_log: List[str] = field(default_factory=list)


def dataclass_dict(value: Any) -> Dict[str, Any]:
    """Convert nested dataclasses to dictionaries, including enum values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [dataclass_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: dataclass_dict(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {key: dataclass_dict(item) for key, item in asdict(value).items()}
    return value

