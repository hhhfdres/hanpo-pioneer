"""Thermal control and wearer-state classification."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Tuple

from .models import ControlDecision, Telemetry, WearerMode, ZoneOutput


@dataclass(frozen=True)
class ThermalConfig:
    target_core_temp_c: float = 37.0
    zone_power_w: float = 8.34
    overheat_cutoff_c: float = 65.0
    overheat_resume_c: float = 55.0
    minimum_pid_update_s: float = 0.015
    active_duty_limit: float = 0.35
    resting_duty_limit: float = 0.55
    unconscious_duty_limit: float = 1.0


class FuzzyPID:
    """Small fuzzy gain-scheduled PID used by the reference controller.

    The production controller can replace this with a fixed-point implementation
    while preserving the same input/output contract.
    """

    def __init__(self) -> None:
        self.integral = 0.0
        self.previous_error: Optional[float] = None
        self.last_output = 0.0

    def reset(self) -> None:
        self.integral = 0.0
        self.previous_error = None
        self.last_output = 0.0

    def update(self, error: float, dt: float) -> float:
        if dt <= 0.0:
            return self.last_output

        absolute_error = abs(error)
        if absolute_error > 2.0:
            kp, ki, kd = 3.2, 0.02, 0.08
        elif absolute_error > 0.6:
            kp, ki, kd = 2.5, 0.08, 0.30
        else:
            kp, ki, kd = 1.7, 0.14, 0.55

        self.integral = max(-30.0, min(30.0, self.integral + error * dt))
        derivative = 0.0
        if self.previous_error is not None:
            derivative = (error - self.previous_error) / dt
        self.previous_error = error

        raw = kp * error + ki * self.integral + kd * derivative
        output = max(0.0, min(1.0, raw))
        self.last_output = output
        return output


class ThermalController:
    """Closed-loop controller with independent overheat lockout."""

    def __init__(self, config: Optional[ThermalConfig] = None) -> None:
        self.config = config or ThermalConfig()
        self.pid = FuzzyPID()
        self.overheat_latched = False

    def update(self, telemetry: Telemetry, mode: WearerMode) -> ControlDecision:
        if telemetry.surface_temp_c >= self.config.overheat_cutoff_c:
            self.overheat_latched = True
            self.pid.reset()
        elif (
            self.overheat_latched
            and telemetry.surface_temp_c <= self.config.overheat_resume_c
        ):
            self.overheat_latched = False

        if self.overheat_latched:
            return ControlDecision(
                mode=mode,
                zones=ZoneOutput(),
                power_w=0.0,
                overheat_latched=True,
                reason="surface temperature lockout",
                pid_output=0.0,
            )

        error = self.config.target_core_temp_c - telemetry.core_temp_c
        dt = max(self.config.minimum_pid_update_s, 0.1)
        pid_output = self.pid.update(error, dt)

        duty_limit = {
            WearerMode.ACTIVE: self.config.active_duty_limit,
            WearerMode.RESTING: self.config.resting_duty_limit,
            WearerMode.UNCONSCIOUS: self.config.unconscious_duty_limit,
        }[mode]

        ambient_boost = 0.0
        if telemetry.ambient_temp_c <= -30.0:
            ambient_boost = 0.20
        elif telemetry.ambient_temp_c <= 5.0:
            ambient_boost = 0.10

        duty = min(duty_limit, pid_output + ambient_boost)
        if mode == WearerMode.UNCONSCIOUS:
            duty = self.config.unconscious_duty_limit

        zones = ZoneOutput(
            chest=duty * 0.42,
            back=duty * 0.38,
            waist=duty * 0.20,
        )
        total_zone_duty = zones.total_duty()
        power_w = total_zone_duty * self.config.zone_power_w
        reason = "closed-loop heating"
        if ambient_boost > 0.0:
            reason = "closed-loop heating with cold-ambient compensation"
        if telemetry.core_temp_c >= self.config.target_core_temp_c:
            reason = "target temperature reached"

        return ControlDecision(
            mode=mode,
            zones=zones,
            power_w=power_w,
            overheat_latched=False,
            reason=reason,
            pid_output=pid_output,
        )


class ModeClassifier:
    """Stateful fallback classifier for normal, resting, and unconscious modes.

    The fallback is deterministic and safe for embedded use. A random-forest or
    ONNX model can be evaluated before the fallback by replacing this class.
    """

    def __init__(
        self,
        history_seconds: float = 360.0,
        unconscious_stationary_seconds: float = 300.0,
        temperature_drop_c_per_min: float = 0.10,
    ) -> None:
        self.history: Deque[Tuple[float, float, float]] = deque()
        self.history_seconds = history_seconds
        self.unconscious_stationary_seconds = unconscious_stationary_seconds
        self.temperature_drop_c_per_min = temperature_drop_c_per_min

    def _temperature_trend(self) -> float:
        if len(self.history) < 2:
            return 0.0
        first = self.history[0]
        last = self.history[-1]
        elapsed_minutes = (last[0] - first[0]) / 60.0
        if elapsed_minutes <= 0.0:
            return 0.0
        return (last[1] - first[1]) / elapsed_minutes

    def update(
        self,
        telemetry: Telemetry,
        explicit_mode: Optional[WearerMode] = None,
    ) -> WearerMode:
        self.history.append(
            (telemetry.timestamp, telemetry.core_temp_c, telemetry.motion_score)
        )
        cutoff = telemetry.timestamp - self.history_seconds
        while self.history and self.history[0][0] < cutoff:
            self.history.popleft()

        if explicit_mode is not None:
            return explicit_mode

        trend = self._temperature_trend()
        low_motion = telemetry.motion_score < 0.12
        if (
            telemetry.stationary_seconds >= self.unconscious_stationary_seconds
            and low_motion
            and trend <= -self.temperature_drop_c_per_min
        ):
            return WearerMode.UNCONSCIOUS
        if telemetry.stationary_seconds >= 120.0 and low_motion:
            return WearerMode.RESTING
        return WearerMode.ACTIVE

    def snapshot(self) -> Tuple[Tuple[float, float, float], ...]:
        return tuple(self.history)

