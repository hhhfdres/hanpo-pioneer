"""SOS event emission and constrained Beidou short-message encoding."""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import AlertEvent, Telemetry


class ShortMessageCodec:
    """Encode a compact status frame without depending on a radio vendor."""

    prefix = "HP1"

    @classmethod
    def encode(cls, alert: AlertEvent) -> str:
        return (
            f"{cls.prefix}|{alert.device_id}|{alert.latitude:.5f}|"
            f"{alert.longitude:.5f}|{alert.core_temp_c:.1f}|"
            f"{alert.capacitor_soc * 100:.0f}|{alert.battery_soc * 100:.0f}"
        )

    @classmethod
    def decode(cls, message: str, created_at: float = 0.0) -> AlertEvent:
        parts = message.split("|")
        if len(parts) != 7 or parts[0] != cls.prefix:
            raise ValueError("invalid HanPo short message")
        return AlertEvent(
            device_id=parts[1],
            created_at=created_at,
            message=message,
            latitude=float(parts[2]),
            longitude=float(parts[3]),
            core_temp_c=float(parts[4]),
            capacitor_soc=float(parts[5]) / 100.0,
            battery_soc=float(parts[6]) / 100.0,
        )


class AlertManager:
    """Rate-limit emergency transmissions and track rescue acknowledgement."""

    def __init__(self, resend_seconds: float = 30.0) -> None:
        self.resend_seconds = resend_seconds
        self.last_sent: Dict[str, float] = {}
        self.acknowledged: Dict[str, bool] = {}
        self.events: List[AlertEvent] = []

    def should_send(self, device_id: str, now: float, unconscious: bool) -> bool:
        if not unconscious:
            return False
        if self.acknowledged.get(device_id, False):
            return False
        previous = self.last_sent.get(device_id)
        return previous is None or now - previous >= self.resend_seconds

    def emit(self, telemetry: Telemetry, reason: str) -> Optional[AlertEvent]:
        if not self.should_send(telemetry.device_id, telemetry.timestamp, True):
            return None
        alert = AlertEvent(
            device_id=telemetry.device_id,
            created_at=telemetry.timestamp,
            message=reason,
            latitude=telemetry.latitude,
            longitude=telemetry.longitude,
            core_temp_c=telemetry.core_temp_c,
            capacitor_soc=telemetry.capacitor_soc,
            battery_soc=telemetry.battery_soc,
        )
        self.last_sent[telemetry.device_id] = telemetry.timestamp
        self.acknowledged[telemetry.device_id] = False
        self.events.append(alert)
        return alert

    def acknowledge(self, device_id: str) -> None:
        self.acknowledged[device_id] = True

    def latest_for(self, device_id: str) -> Optional[AlertEvent]:
        for event in reversed(self.events):
            if event.device_id == device_id:
                return event
        return None

