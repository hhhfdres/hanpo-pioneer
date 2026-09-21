import unittest

from hanpo.models import GeoPoint
from hanpo.navigation import CurrentVector, DriftPredictor, KalmanTracker, RescuePlanner


class KalmanTrackerTests(unittest.TestCase):
    def test_filter_initializes_and_tracks_a_moving_target(self):
        tracker = KalmanTracker(measurement_noise_m=5.0)
        first = GeoPoint(30.0, 122.0)
        self.assertEqual(tracker.update(first, 1.0), first)
        second = GeoPoint(30.0001, 122.0001)
        filtered = tracker.update(second, 1.0)
        self.assertLess(abs(filtered.latitude - second.latitude), 0.001)
        self.assertLess(abs(filtered.longitude - second.longitude), 0.001)


class DriftPredictorTests(unittest.TestCase):
    def test_positive_current_moves_prediction_east_and_north(self):
        predictor = DriftPredictor()
        origin = GeoPoint(30.0, 122.0)
        points = predictor.predict(
            origin,
            CurrentVector(east_mps=1.0, north_mps=1.0),
            CurrentVector(),
            hours=(1, 2),
        )
        self.assertEqual(points[0], origin)
        self.assertGreater(points[-1].longitude, origin.longitude)
        self.assertGreater(points[-1].latitude, origin.latitude)


class RescuePlannerTests(unittest.TestCase):
    def test_planner_returns_bounded_route_and_eta(self):
        planner = RescuePlanner(max_nodes=1000)
        start = GeoPoint(30.30, 122.08)
        goal = GeoPoint(30.24, 122.20)
        route, distance, eta = planner.plan(start, goal, ship_speed_mps=8.0)
        self.assertGreaterEqual(len(route), 2)
        self.assertEqual(route[0], start)
        self.assertEqual(route[-1], goal)
        self.assertGreater(distance, 0.0)
        self.assertGreater(eta, 0.0)


if __name__ == "__main__":
    unittest.main()

