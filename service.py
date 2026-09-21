"""Application service coordinating devices, alerts, and rescue planning."""

from __future__ import annotations

import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from .alerting import AlertManager
from .control import ModeClassifier, ThermalController
from .energy import BatteryHealthEstimator, EnergyManager
from .models import (
    AlertLevel,
    DeviceStatus,
    GeoPoint,
    RescuePlan,
    Telemetry,
    WearerMode,
    dataclass_dict,
)
from .navigation import (
    CurrentVector,
    DriftPredictor,
    KalmanTracker,
    RescuePlanner,
    rescue_priority,
)


@dataclass
class DeviceRuntime:
    device_id: str
    name: str
    scenario: str = "normal"
    explicit_mode: Optional[WearerMode] = None
    telemetry: Optional[Telemetry] = None
    classifier: ModeClassifier = field(default_factory=ModeClassifier)
    thermal_controller: ThermalController = field(default_factory=ThermalController)
    energy_manager: EnergyManager = field(default_factory=EnergyManager)
    position_filter: KalmanTracker = field(default_factory=KalmanTracker)
    history: Deque[Telemetry] = field(default_factory=lambda: deque(maxlen=1800))
    status: Optional[DeviceStatus] = None
    event_log: Deque[str] = field(default_factory=lambda: deque(maxlen=30))
    last_alert_at: Optional[float] = None
    alert_acknowledged: bool = True


class SimulatedDevice:
    """Deterministic physics-lite simulator for demos and integration tests."""

    def __init__(
        self,
        runtime: DeviceRuntime,
        origin: GeoPoint,
        ambient_temp_c: float,
        initial_soc: float,
        seed: int,
    ) -> None:
        self.runtime = runtime
        self.origin = origin
        self.ambient_temp_c = ambient_temp_c
        self.capacitor_soc = initial_soc
        self.battery_soc = max(0.2, initial_soc - 0.2)
        self.core_temp_c = 36.8
        self.surface_temp_c = 34.0
        self.distance_from_origin_m = 0.0
        self.drift_bearing_deg = 32.0
        self.random = random.Random(seed)
        self.started_at = time.time()

    def tick(self, now: float, dt: float) -> Telemetry:
        scenario = self.runtime.scenario
        if scenario == "unconscious":
            self.runtime.explicit_mode = WearerMode.UNCONSCIOUS
            motion_score = 0.01
            stationary_seconds = max(301.0, now - self.started_at)
            heat_loss = 0.035 * dt
            drift_speed = 0.45
        elif scenario == "resting":
            self.runtime.explicit_mode = WearerMode.RESTING
            motion_score = 0.06
            stationary_seconds = max(130.0, now - self.started_at)
            heat_loss = 0.012 * dt
            drift_speed = 0.12
        elif scenario == "overheat":
            self.runtime.explicit_mode = WearerMode.ACTIVE
            motion_score = 0.45
            stationary_seconds = 0.0
            self.surface_temp_c = 66.5
            heat_loss = 0.0
            drift_speed = 0.02
        elif scenario == "cold":
            self.runtime.explicit_mode = WearerMode.ACTIVE
            motion_score = 0.70
            stationary_seconds = 0.0
            self.ambient_temp_c = min(self.ambient_temp_c, -34.0)
            heat_loss = 0.025 * dt
            drift_speed = 0.05
        else:
            self.runtime.explicit_mode = None
            motion_score = 0.72 + self.random.uniform(-0.08, 0.08)
            stationary_seconds = 0.0
            heat_loss = 0.008 * dt
            drift_speed = 0.04

        previous = self.runtime.status
        heating_power = previous.control.power_w if previous is not None else 0.0
        heat_gain = heating_power * 0.00125 * dt
        environmental_loss = max(0.0, (36.5 - self.ambient_temp_c) * 0.00018 * dt)
        self.core_temp_c += heat_gain - heat_loss - environmental_loss
        if self.core_temp_c < 30.0:
            self.core_temp_c = 30.0 + self.random.uniform(-0.03, 0.03)
        self.core_temp_c = min(38.6, self.core_temp_c)

        if scenario != "overheat":
            target_surface = self.core_temp_c + 2.0 + heating_power * 0.18
            self.surface_temp_c += (target_surface - self.surface_temp_c) * min(0.2, dt * 0.08)
        else:
            self.surface_temp_c += (66.5 - self.surface_temp_c) * 0.3

        if scenario == "unconscious":
            drain_rate = 0.012
        elif scenario == "resting":
            drain_rate = 0.004
        elif scenario == "cold":
            drain_rate = 0.016
        else:
            drain_rate = 0.006
        self.capacitor_soc = max(0.0, self.capacitor_soc - drain_rate * dt / 3600.0)
        self.battery_soc = max(0.0, self.battery_soc - drain_rate * dt / 7200.0)

        self.distance_from_origin_m += drift_speed * dt
        drift_east = self.distance_from_origin_m * math.sin(
            math.radians(self.drift_bearing_deg)
        )
        drift_north = self.distance_from_origin_m * math.cos(
            math.radians(self.drift_bearing_deg)
        )
        earth_radius_m = 6_371_000.0
        latitude = self.origin.latitude + math.degrees(drift_north / earth_radius_m)
        longitude = self.origin.longitude + math.degrees(
            drift_east
            / (earth_radius_m * math.cos(math.radians(self.origin.latitude)))
        )
        latitude += self.random.uniform(-0.00002, 0.00002)
        longitude += self.random.uniform(-0.00002, 0.00002)

        return Telemetry(
            device_id=self.runtime.device_id,
            timestamp=now,
            core_temp_c=round(self.core_temp_c, 3),
            surface_temp_c=round(self.surface_temp_c, 3),
            ambient_temp_c=round(self.ambient_temp_c, 3),
            capacitor_soc=round(self.capacitor_soc, 4),
            battery_soc=round(self.battery_soc, 4),
            latitude=round(latitude, 7),
            longitude=round(longitude, 7),
            stationary_seconds=round(stationary_seconds, 1),
            motion_score=round(motion_score, 3),
            speed_mps=drift_speed + self.random.uniform(0.0, 0.05),
            heart_rate_bpm=52.0 if scenario == "unconscious" else 72.0 + self.random.uniform(-4, 4),
            battery_voltage_v=1.2,
            battery_current_a=0.2,
            sequence=int((now - self.started_at) * 10.0),
        )


class FleetService:
    def __init__(self, seed: int = 2026) -> None:
        self.seed = seed
        self.started_at = time.time()
        self.last_tick = self.started_at
        self.runtimes: Dict[str, DeviceRuntime] = {}
        self.simulators: Dict[str, SimulatedDevice] = {}
        self.alert_manager = AlertManager()
        self.drift_predictor = DriftPredictor()
        self.rescue_planner = RescuePlanner()
        self.soh_estimator = BatteryHealthEstimator()
        self._create_demo_fleet()

    def _create_demo_fleet(self) -> None:
        configurations = [
            (
                "HP-A01",
                "东海搜救 01",
                GeoPoint(30.2762, 122.3180),
                9.0,
                0.88,
                "normal",
            ),
            (
                "HP-B07",
                "边防巡护 07",
                GeoPoint(30.2310, 122.1740),
                -41.0,
                0.62,
                "cold",
            ),
            (
                "HP-C12",
                "海上平台 12",
                GeoPoint(30.1840, 122.2960),
                5.0,
                0.43,
                "resting",
            ),
        ]
        for index, (device_id, name, origin, ambient, soc, scenario) in enumerate(
            configurations
        ):
            runtime = DeviceRuntime(
                device_id=device_id,
                name=name,
                scenario=scenario,
            )
            self.runtimes[device_id] = runtime
            self.simulators[device_id] = SimulatedDevice(
                runtime=runtime,
                origin=origin,
                ambient_temp_c=ambient,
                initial_soc=soc,
                seed=self.seed + index * 17,
            )

    def tick(self, now: Optional[float] = None) -> List[DeviceStatus]:
        now = now or time.time()
        dt = max(0.2, min(10.0, now - self.last_tick))
        self.last_tick = now
        statuses: List[DeviceStatus] = []
        for device_id, simulator in self.simulators.items():
            telemetry = simulator.tick(now, dt)
            statuses.append(self._process_telemetry(telemetry, now))
        return statuses

    def _process_telemetry(self, telemetry: Telemetry, now: float) -> DeviceStatus:
        runtime = self.runtimes.get(telemetry.device_id)
        if runtime is None:
            runtime = DeviceRuntime(device_id=telemetry.device_id, name=telemetry.device_id)
            self.runtimes[telemetry.device_id] = runtime

        filtered_position = runtime.position_filter.update(telemetry.position, max(0.1, 1.0))
        telemetry.latitude = filtered_position.latitude
        telemetry.longitude = filtered_position.longitude

        mode = runtime.classifier.update(telemetry, runtime.explicit_mode)
        control = runtime.thermal_controller.update(telemetry, mode)
        energy = runtime.energy_manager.update(
            capacitor_soc=telemetry.capacitor_soc,
            battery_soc=telemetry.battery_soc,
            ambient_temp_c=telemetry.ambient_temp_c,
            requested_power_w=control.power_w,
            mode=mode,
            dt=1.0,
        )

        alert_level = AlertLevel.NORMAL
        if mode == WearerMode.UNCONSCIOUS or telemetry.core_temp_c < 34.0:
            alert_level = AlertLevel.SOS
        elif telemetry.core_temp_c < 35.5 or control.overheat_latched:
            alert_level = AlertLevel.WATCH

        if alert_level == AlertLevel.SOS and self.alert_manager.should_send(
            telemetry.device_id, now, True
        ):
            reason = "unconscious safeguard" if mode == WearerMode.UNCONSCIOUS else "low body temperature"
            alert = self.alert_manager.emit(telemetry, reason)
            if alert is not None:
                runtime.last_alert_at = now
                runtime.alert_acknowledged = False
                runtime.event_log.appendleft(
                    f"{time.strftime('%H:%M:%S', time.localtime(now))} SOS sent: {reason}"
                )
        elif alert_level == AlertLevel.WATCH and (
            not runtime.event_log or not runtime.event_log[0].startswith("Watch")
        ):
            runtime.event_log.appendleft(
                f"Watch: {control.reason if control.overheat_latched else 'temperature trend'}"
            )

        priority = rescue_priority(
            alert_level.value,
            telemetry.core_temp_c,
            telemetry.capacitor_soc,
            telemetry.battery_soc,
            telemetry.stationary_seconds,
        )
        if control.overheat_latched:
            priority = min(100.0, priority + 15.0)

        status = DeviceStatus(
            telemetry=telemetry,
            mode=mode,
            alert_level=alert_level,
            control=control,
            energy=energy,
            rescue_priority=round(priority, 1),
            last_alert_at=runtime.last_alert_at,
            alert_acknowledged=runtime.alert_acknowledged,
            event_log=list(runtime.event_log),
        )
        runtime.telemetry = telemetry
        runtime.history.append(telemetry)
        runtime.status = status
        return status

    def list_devices(self) -> List[DeviceStatus]:
        statuses = [
            runtime.status
            for runtime in self.runtimes.values()
            if runtime.status is not None
        ]
        return sorted(statuses, key=lambda item: item.rescue_priority, reverse=True)

    def get_device(self, device_id: str) -> DeviceStatus:
        runtime = self.runtimes.get(device_id)
        if runtime is None or runtime.status is None:
            raise KeyError(device_id)
        return runtime.status

    def ingest(self, payload: Dict[str, object]) -> DeviceStatus:
        telemetry = Telemetry.from_dict(payload)
        return self._process_telemetry(telemetry, telemetry.timestamp)

    def set_scenario(self, device_id: str, scenario: str) -> DeviceStatus:
        allowed = {"normal", "resting", "unconscious", "overheat", "cold"}
        if scenario not in allowed:
            raise ValueError("unsupported scenario")
        runtime = self.runtimes.get(device_id)
        if runtime is None:
            raise KeyError(device_id)
        runtime.scenario = scenario
        runtime.explicit_mode = None
        runtime.classifier = ModeClassifier()
        runtime.thermal_controller = ThermalController()
        if scenario != "overheat" and device_id in self.simulators:
            self.simulators[device_id].surface_temp_c = min(
                50.0, self.simulators[device_id].surface_temp_c
            )
        self.tick()
        return self.get_device(device_id)

    def acknowledge(self, device_id: str) -> DeviceStatus:
        if device_id not in self.runtimes:
            raise KeyError(device_id)
        self.alert_manager.acknowledge(device_id)
        runtime = self.runtimes[device_id]
        runtime.alert_acknowledged = True
        runtime.event_log.appendleft(
            f"{time.strftime('%H:%M:%S')} Rescue centre acknowledged"
        )
        if runtime.status is not None:
            runtime.status.alert_acknowledged = True
            runtime.status.event_log = list(runtime.event_log)
        return self.get_device(device_id)

    def predict_drift(
        self,
        device_id: str,
        current: CurrentVector = CurrentVector(east_mps=0.33, north_mps=0.12),
        wind: CurrentVector = CurrentVector(east_mps=8.0, north_mps=2.0),
    ) -> List[GeoPoint]:
        status = self.get_device(device_id)
        return self.drift_predictor.predict(status.telemetry.position, current, wind)

    def rescue_plan(
        self,
        device_id: str,
        ship_position: GeoPoint,
        ship_speed_mps: float = 8.0,
    ) -> RescuePlan:
        status = self.get_device(device_id)
        route, distance_m, eta_minutes = self.rescue_planner.plan(
            start=ship_position,
            goal=status.telemetry.position,
            ship_speed_mps=ship_speed_mps,
            current=CurrentVector(east_mps=0.32, north_mps=0.08),
            wind=CurrentVector(east_mps=7.5, north_mps=1.0),
        )
        conditions = []
        if status.alert_level == AlertLevel.SOS:
            conditions.append("active SOS")
        if status.control.overheat_latched:
            conditions.append("thermal lockout")
        if status.telemetry.capacitor_soc < 0.20:
            conditions.append("capacitor below 20%")
        rationale = ", ".join(conditions) if conditions else "routine recovery route"
        return RescuePlan(
            device_id=device_id,
            generated_at=time.time(),
            route=route,
            distance_m=round(distance_m, 1),
            eta_minutes=round(eta_minutes, 1),
            priority_score=status.rescue_priority,
            rationale=rationale,
        )

    def system_health(self) -> Dict[str, object]:
        return {
            "status": "ok",
            "devices": len(self.runtimes),
            "alerts": sum(
                1
                for runtime in self.runtimes.values()
                if runtime.status is not None
                and runtime.status.alert_level == AlertLevel.SOS
            ),
            "server_time": time.time(),
            "source": "reference-simulator",
        }

    def serialize_status(self, status: DeviceStatus) -> Dict[str, object]:
        payload = dataclass_dict(status)
        runtime = self.runtimes[status.telemetry.device_id]
        payload["name"] = runtime.name
        payload["scenario"] = runtime.scenario
        payload["history"] = [
            {
                "timestamp": item.timestamp,
                "core_temp_c": item.core_temp_c,
                "surface_temp_c": item.surface_temp_c,
                "capacitor_soc": item.capacitor_soc,
            }
            for item in list(runtime.history)[-120:]
        ]
        return payload

    def serialize_device_list(self) -> Dict[str, object]:
        devices = [self.serialize_status(status) for status in self.list_devices()]
        return {
            "generated_at": time.time(),
            "devices": devices,
            "summary": {
                "total": len(devices),
                "sos": sum(1 for item in devices if item["alert_level"] == AlertLevel.SOS.value),
                "watch": sum(
                    1 for item in devices if item["alert_level"] == AlertLevel.WATCH.value
                ),
                "unacknowledged": sum(
                    1
                    for item in devices
                    if item["alert_level"] == AlertLevel.SOS.value
                    and not item["alert_acknowledged"]
                ),
            },
        }
