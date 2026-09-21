import unittest

from hanpo.alerting import AlertManager, ShortMessageCodec
from hanpo.models import AlertEvent, Telemetry


class ShortMessageTests(unittest.TestCase):
    def test_codec_round_trip(self):
        alert = AlertEvent(
            device_id="HP-A01",
            created_at=100.0,
            message="unconscious",
            latitude=30.12345,
            longitude=122.54321,
            core_temp_c=35.6,
            capacitor_soc=0.81,
            battery_soc=0.72,
        )
        decoded = ShortMessageCodec.decode(ShortMessageCodec.encode(alert), created_at=101.0)
        self.assertEqual(decoded.device_id, alert.device_id)
        self.assertAlmostEqual(decoded.latitude, alert.latitude, places=5)
        self.assertAlmostEqual(decoded.capacitor_soc, 0.81, places=2)


class AlertManagerTests(unittest.TestCase):
    def test_resend_interval_and_acknowledgement(self):
        manager = AlertManager(resend_seconds=30.0)
        telemetry = Telemetry(
            device_id="HP-A01",
            timestamp=100.0,
            core_temp_c=35.6,
            surface_temp_c=40.0,
            ambient_temp_c=5.0,
            capacitor_soc=0.81,
            battery_soc=0.72,
            latitude=30.1,
            longitude=122.2,
        )
        self.assertTrue(manager.should_send("HP-A01", 100.0, True))
        self.assertIsNotNone(manager.emit(telemetry, "unconscious"))
        self.assertFalse(manager.should_send("HP-A01", 100.0, True))
        self.assertFalse(manager.should_send("HP-A01", 120.0, True))
        self.assertTrue(manager.should_send("HP-A01", 130.0, True))
        manager.acknowledge("HP-A01")
        self.assertFalse(manager.should_send("HP-A01", 200.0, True))


if __name__ == "__main__":
    unittest.main()
