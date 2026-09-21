"""Multi-source energy policy and battery-health estimation."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Optional

from .models import EnergyDecision, EnergySource, WearerMode


@dataclass(frozen=True)
class EnergyConfig:
    capacitor_low_soc: float = 0.20
    capacitor_primary_soc: float = 0.30
    preheat_ambient_c: float = -30.0
    preheat_power_w: float = 2.0
    preheat_seconds: float = 300.0
    max_continuous_power_w: float = 25.0


class EnergyManager:
    def __init__(self, config: Optional[EnergyConfig] = None) -> None:
        self.config = config or EnergyConfig()
        self.preheat_elapsed_s = 0.0
        self.preheat_complete = False
        self.last_ambient_c: Optional[float] = None

    def update(
        self,
        capacitor_soc: float,
        battery_soc: float,
        ambient_temp_c: float,
        requested_power_w: float,
        mode: WearerMode,
        dt: float = 1.0,
    ) -> EnergyDecision:
        capacitor_soc = max(0.0, min(1.0, capacitor_soc))
        battery_soc = max(0.0, min(1.0, battery_soc))
        requested_power_w = max(0.0, min(self.config.max_continuous_power_w, requested_power_w))

        if (
            self.last_ambient_c is not None
            and ambient_temp_c > self.config.preheat_ambient_c + 5.0
        ):
            self.preheat_complete = False
            self.preheat_elapsed_s = 0.0
        self.last_ambient_c = ambient_temp_c

        if (
            ambient_temp_c <= self.config.preheat_ambient_c
            and not self.preheat_complete
        ):
            self.preheat_elapsed_s += max(0.0, dt)
            if self.preheat_elapsed_s >= self.config.preheat_seconds:
                self.preheat_complete = True
            return EnergyDecision(
                source=EnergySource.PREHEAT,
                power_budget_w=max(self.config.preheat_power_w, requested_power_w * 0.25),
                preheating=True,
                reason="electrolyte preheat cycle",
            )

        if mode == WearerMode.UNCONSCIOUS:
            source = EnergySource.HYBRID
            power_budget = min(
                self.config.max_continuous_power_w,
                max(requested_power_w, 12.0),
            )
            reason = "unconscious safeguard uses both sources"
        elif capacitor_soc < self.config.capacitor_low_soc and battery_soc > 0.02:
            source = EnergySource.BATTERY
            power_budget = requested_power_w
            reason = "capacitor SOC below 20 percent"
        elif capacitor_soc >= self.config.capacitor_primary_soc:
            source = EnergySource.CAPACITOR
            power_budget = requested_power_w
            reason = "capacitor primary operating range"
        elif battery_soc > 0.02:
            source = EnergySource.HYBRID
            power_budget = requested_power_w
            reason = "capacitor transition band"
        else:
            source = EnergySource.CAPACITOR
            power_budget = min(requested_power_w, 6.0)
            reason = "battery unavailable; load shedding"

        return EnergyDecision(
            source=source,
            power_budget_w=power_budget,
            preheating=False,
            reason=reason,
        )


class BatteryHealthEstimator:
    """Lightweight SOH estimate; replaceable by the SVM/ONNX reference model."""

    def estimate(
        self,
        measured_capacity_ah: float,
        rated_capacity_ah: float,
        internal_resistance_mohm: float,
        nominal_resistance_mohm: float,
    ) -> float:
        if rated_capacity_ah <= 0.0 or nominal_resistance_mohm <= 0.0:
            raise ValueError("rated capacity and nominal resistance must be positive")
        capacity_ratio = max(0.0, min(1.2, measured_capacity_ah / rated_capacity_ah))
        resistance_penalty = max(
            0.0,
            min(0.5, (internal_resistance_mohm / nominal_resistance_mohm - 1.0) * 0.2),
        )
        soh = capacity_ratio - resistance_penalty
        return max(0.0, min(1.0, soh))

    @staticmethod
    def failure_probability(soh: float, cycles: int) -> float:
        soh = max(0.0, min(1.0, soh))
        cycle_term = max(0.0, cycles - 5000) / 5000.0
        raw = (1.0 - soh) * 4.0 + cycle_term
        return 1.0 / (1.0 + exp(-raw))

