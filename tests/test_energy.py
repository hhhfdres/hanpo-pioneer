import unittest

from hanpo.energy import BatteryHealthEstimator, EnergyManager
from hanpo.models import EnergySource, WearerMode


class EnergyManagerTests(unittest.TestCase):
    def test_capacitor_is_primary_above_thirty_percent(self):
        decision = EnergyManager().update(0.8, 0.7, 5.0, 10.0, WearerMode.ACTIVE)
        self.assertEqual(decision.source, EnergySource.CAPACITOR)

    def test_battery_takes_over_below_twenty_percent(self):
        decision = EnergyManager().update(0.19, 0.7, 5.0, 10.0, WearerMode.ACTIVE)
        self.assertEqual(decision.source, EnergySource.BATTERY)

    def test_cold_start_runs_preheat_cycle(self):
        manager = EnergyManager()
        decision = manager.update(0.8, 0.7, -40.0, 5.0, WearerMode.ACTIVE, dt=1.0)
        self.assertTrue(decision.preheating)
        self.assertEqual(decision.source, EnergySource.PREHEAT)

    def test_unconscious_mode_uses_hybrid_energy(self):
        decision = EnergyManager().update(0.8, 0.7, 5.0, 5.0, WearerMode.UNCONSCIOUS)
        self.assertEqual(decision.source, EnergySource.HYBRID)
        self.assertGreaterEqual(decision.power_budget_w, 12.0)


class BatteryHealthTests(unittest.TestCase):
    def test_soh_is_bounded(self):
        estimator = BatteryHealthEstimator()
        self.assertEqual(estimator.estimate(2.0, 2.0, 10.0, 10.0), 1.0)
        self.assertGreaterEqual(estimator.estimate(0.0, 2.0, 30.0, 10.0), 0.0)
        self.assertLessEqual(estimator.estimate(0.0, 2.0, 30.0, 10.0), 1.0)


if __name__ == "__main__":
    unittest.main()

