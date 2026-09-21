import unittest

from hanpo.control import ModeClassifier, ThermalController
from hanpo.models import Telemetry, WearerMode


def telemetry(**overrides):
    values = {
        "device_id": "HP-T01",
        "timestamp": 1000.0,
        "core_temp_c": 36.5,
        "surface_temp_c": 38.0,
        "ambient_temp_c": 5.0,
        "capacitor_soc": 0.8,
        "battery_soc": 0.7,
        "latitude": 30.2,
        "longitude": 122.2,
        "stationary_seconds": 0.0,
        "motion_score": 0.8,
    }
    values.update(overrides)
    return Telemetry(**values)


class ThermalControllerTests(unittest.TestCase):
    def test_controller_heats_without_exceeding_mode_limit(self):
        controller = ThermalController()
        decision = controller.update(telemetry(core_temp_c=35.0), WearerMode.ACTIVE)
        self.assertGreater(decision.power_w, 0.0)
        self.assertLessEqual(decision.zones.total_duty(), controller.config.active_duty_limit)

    def test_overheat_lockout_requires_resume_temperature(self):
        controller = ThermalController()
        hot = controller.update(telemetry(surface_temp_c=66.0), WearerMode.ACTIVE)
        self.assertTrue(hot.overheat_latched)
        self.assertEqual(hot.power_w, 0.0)

        still_hot = controller.update(telemetry(surface_temp_c=60.0), WearerMode.ACTIVE)
        self.assertTrue(still_hot.overheat_latched)
        cooled = controller.update(telemetry(surface_temp_c=54.0), WearerMode.ACTIVE)
        self.assertFalse(cooled.overheat_latched)

    def test_unconscious_mode_uses_full_duty(self):
        controller = ThermalController()
        decision = controller.update(telemetry(core_temp_c=35.5), WearerMode.UNCONSCIOUS)
        self.assertAlmostEqual(decision.zones.total_duty(), 1.0, places=6)


class ModeClassifierTests(unittest.TestCase):
    def test_detects_unconscious_after_stationary_and_temperature_drop(self):
        classifier = ModeClassifier()
        classifier.update(telemetry(timestamp=0.0, core_temp_c=36.8, motion_score=0.02))
        mode = classifier.update(
            telemetry(
                timestamp=360.0,
                core_temp_c=36.1,
                stationary_seconds=360.0,
                motion_score=0.02,
            )
        )
        self.assertEqual(mode, WearerMode.UNCONSCIOUS)

    def test_active_person_is_not_marked_unconscious(self):
        classifier = ModeClassifier()
        mode = classifier.update(telemetry(stationary_seconds=0.0, motion_score=0.7))
        self.assertEqual(mode, WearerMode.ACTIVE)


if __name__ == "__main__":
    unittest.main()

