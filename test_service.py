import json
import threading
import unittest
from urllib.request import Request, urlopen

from hanpo.api import create_server
from hanpo.service import FleetService


class FleetServiceTests(unittest.TestCase):
    def test_tick_produces_three_sorted_devices(self):
        service = FleetService(seed=1)
        statuses = service.tick(1000.0)
        self.assertEqual(len(statuses), 3)
        priorities = [status.rescue_priority for status in service.list_devices()]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_unconscious_scenario_emits_alert(self):
        service = FleetService(seed=2)
        service.tick(1000.0)
        status = service.set_scenario("HP-A01", "unconscious")
        self.assertEqual(status.mode.value, "unconscious")
        self.assertEqual(status.alert_level.value, "sos")
        self.assertFalse(status.alert_acknowledged)

    def test_rescue_plan_can_be_generated(self):
        service = FleetService(seed=3)
        service.tick(1000.0)
        plan = service.rescue_plan(
            "HP-A01",
            ship_position=service.get_device("HP-A01").telemetry.position,
        )
        self.assertEqual(plan.device_id, "HP-A01")
        self.assertGreaterEqual(len(plan.route), 2)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = FleetService(seed=4)
        cls.server = create_server("127.0.0.1", 0, service=cls.service)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_health_endpoint(self):
        with urlopen(f"{self.base_url}/api/v1/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["status"], "ok")

    def test_dashboard_is_served(self):
        with urlopen(f"{self.base_url}/", timeout=2) as response:
            body = response.read().decode("utf-8")
        self.assertIn("寒破先锋", body)

    def test_tick_endpoint(self):
        request = Request(
            f"{self.base_url}/api/v1/simulate/tick",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["summary"]["total"], 3)


if __name__ == "__main__":
    unittest.main()

