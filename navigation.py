"""Position smoothing, drift prediction, and rescue route planning."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .models import GeoPoint


Matrix = List[List[float]]


class KalmanTracker:
    """Constant-velocity Kalman tracker operating in local ENU meters."""

    def __init__(
        self,
        process_noise: float = 0.8,
        measurement_noise_m: float = 8.0,
    ) -> None:
        self.initialized = False
        self.origin = GeoPoint(0.0, 0.0)
        self.state = [0.0, 0.0, 0.0, 0.0]
        self.covariance: Matrix = [
            [100.0, 0.0, 0.0, 0.0],
            [0.0, 100.0, 0.0, 0.0],
            [0.0, 0.0, 25.0, 0.0],
            [0.0, 0.0, 0.0, 25.0],
        ]
        self.process_noise = process_noise
        self.measurement_noise_m = measurement_noise_m

    @staticmethod
    def _identity(size: int) -> Matrix:
        return [[1.0 if row == col else 0.0 for col in range(size)] for row in range(size)]

    @staticmethod
    def _matmul(left: Matrix, right: Matrix) -> Matrix:
        rows = len(left)
        shared = len(right)
        cols = len(right[0])
        result = [[0.0 for _ in range(cols)] for _ in range(rows)]
        for row in range(rows):
            for item in range(shared):
                value = left[row][item]
                if value == 0.0:
                    continue
                for col in range(cols):
                    result[row][col] += value * right[item][col]
        return result

    @staticmethod
    def _transpose(matrix: Matrix) -> Matrix:
        return [list(row) for row in zip(*matrix)]

    @staticmethod
    def _add(left: Matrix, right: Matrix) -> Matrix:
        return [
            [left[row][col] + right[row][col] for col in range(len(left[0]))]
            for row in range(len(left))
        ]

    @staticmethod
    def _subtract(left: Matrix, right: Matrix) -> Matrix:
        return [
            [left[row][col] - right[row][col] for col in range(len(left[0]))]
            for row in range(len(left))
        ]

    @staticmethod
    def _inverse_2x2(matrix: Matrix) -> Matrix:
        determinant = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
        if abs(determinant) < 1e-12:
            raise ValueError("singular measurement matrix")
        return [
            [matrix[1][1] / determinant, -matrix[0][1] / determinant],
            [-matrix[1][0] / determinant, matrix[0][0] / determinant],
        ]

    @staticmethod
    def _offset(origin: GeoPoint, latitude: float, longitude: float) -> Tuple[float, float]:
        earth_radius_m = 6_371_000.0
        north = math.radians(latitude - origin.latitude) * earth_radius_m
        east = (
            math.radians(longitude - origin.longitude)
            * earth_radius_m
            * math.cos(math.radians(origin.latitude))
        )
        return east, north

    @staticmethod
    def _to_geo(origin: GeoPoint, east: float, north: float) -> GeoPoint:
        earth_radius_m = 6_371_000.0
        latitude = origin.latitude + math.degrees(north / earth_radius_m)
        longitude = origin.longitude + math.degrees(
            east / (earth_radius_m * math.cos(math.radians(origin.latitude)))
        )
        return GeoPoint(latitude, longitude)

    def update(self, point: GeoPoint, dt: float) -> GeoPoint:
        if dt <= 0.0:
            raise ValueError("dt must be positive")
        if not self.initialized:
            self.initialized = True
            self.origin = point
            self.state = [0.0, 0.0, 0.0, 0.0]
            return point

        transition = [
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        process = [
            [dt**4 / 4.0, 0.0, dt**3 / 2.0, 0.0],
            [0.0, dt**4 / 4.0, 0.0, dt**3 / 2.0],
            [dt**3 / 2.0, 0.0, dt**2, 0.0],
            [0.0, dt**3 / 2.0, 0.0, dt**2],
        ]
        process = [
            [value * self.process_noise for value in row] for row in process
        ]
        self.state = [
            sum(transition[row][col] * self.state[col] for col in range(4))
            for row in range(4)
        ]
        self.covariance = self._add(
            self._matmul(self._matmul(transition, self.covariance), self._transpose(transition)),
            process,
        )

        east, north = self._offset(self.origin, point.latitude, point.longitude)
        measurement = [east, north]
        observation = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ]
        innovation = [
            measurement[row]
            - sum(observation[row][col] * self.state[col] for col in range(4))
            for row in range(2)
        ]
        measurement_covariance = [
            [self.measurement_noise_m**2, 0.0],
            [0.0, self.measurement_noise_m**2],
        ]
        innovation_covariance = self._add(
            self._matmul(
                self._matmul(observation, self.covariance),
                self._transpose(observation),
            ),
            measurement_covariance,
        )
        gain = self._matmul(
            self._matmul(self.covariance, self._transpose(observation)),
            self._inverse_2x2(innovation_covariance),
        )
        for row in range(4):
            self.state[row] += gain[row][0] * innovation[0] + gain[row][1] * innovation[1]

        identity = self._identity(4)
        residual = self._subtract(identity, self._matmul(gain, observation))
        self.covariance = self._matmul(residual, self.covariance)
        return self._to_geo(self.origin, self.state[0], self.state[1])


@dataclass(frozen=True)
class CurrentVector:
    east_mps: float = 0.0
    north_mps: float = 0.0


class DriftPredictor:
    """Physics-informed baseline drift forecast.

    This module provides the deterministic fallback for an LSTM model. It
    combines surface current with a small windage coefficient.
    """

    def __init__(self, windage_factor: float = 0.035) -> None:
        self.windage_factor = windage_factor

    def predict(
        self,
        origin: GeoPoint,
        current: CurrentVector,
        wind: CurrentVector,
        hours: Iterable[int] = (1, 2, 3, 4, 5, 6),
    ) -> List[GeoPoint]:
        points: List[GeoPoint] = [origin]
        previous = origin
        for hour in hours:
            if hour <= 0:
                raise ValueError("prediction hours must be positive")
            seconds = 3600.0
            east_speed = current.east_mps + wind.east_mps * self.windage_factor
            north_speed = current.north_mps + wind.north_mps * self.windage_factor
            east = east_speed * seconds
            north = north_speed * seconds
            point = self._translate(previous, east, north)
            points.append(point)
            previous = point
        return points

    @staticmethod
    def _translate(origin: GeoPoint, east_m: float, north_m: float) -> GeoPoint:
        earth_radius_m = 6_371_000.0
        latitude = origin.latitude + math.degrees(north_m / earth_radius_m)
        longitude = origin.longitude + math.degrees(
            east_m / (earth_radius_m * math.cos(math.radians(origin.latitude)))
        )
        return GeoPoint(latitude, longitude)


class RescuePlanner:
    """Eight-neighbor A* planner adjusted for current and wind resistance."""

    def __init__(self, max_nodes: int = 3500) -> None:
        self.max_nodes = max_nodes

    def plan(
        self,
        start: GeoPoint,
        goal: GeoPoint,
        ship_speed_mps: float = 8.0,
        current: CurrentVector = CurrentVector(),
        wind: CurrentVector = CurrentVector(),
    ) -> Tuple[List[GeoPoint], float, float]:
        ship_speed_mps = max(0.5, ship_speed_mps)
        distance = start.distance_to(goal)
        if distance < 1.0:
            return [start, goal], distance, 0.0

        grid_size = max(100.0, min(1000.0, distance / 30.0))
        north_span = max(grid_size * 4.0, abs(goal.latitude - start.latitude) * 111_320.0)
        east_span = max(grid_size * 4.0, abs(goal.longitude - start.longitude) * 111_320.0)
        rows = min(48, max(4, int(north_span / grid_size) + 2))
        cols = min(48, max(4, int(east_span / grid_size) + 2))

        south = min(start.latitude, goal.latitude) - grid_size / 111_320.0
        west = min(start.longitude, goal.longitude) - grid_size / (
            111_320.0 * max(0.2, math.cos(math.radians(start.latitude)))
        )

        def point_for(node: Tuple[int, int]) -> GeoPoint:
            latitude = south + node[0] * grid_size / 111_320.0
            longitude = west + node[1] * grid_size / (
                111_320.0 * max(0.2, math.cos(math.radians(start.latitude)))
            )
            return GeoPoint(latitude, longitude)

        def nearest_node(point: GeoPoint) -> Tuple[int, int]:
            row = int(round((point.latitude - south) * 111_320.0 / grid_size))
            col = int(
                round(
                    (point.longitude - west)
                    * 111_320.0
                    * max(0.2, math.cos(math.radians(start.latitude)))
                    / grid_size
                )
            )
            return max(0, min(rows - 1, row)), max(0, min(cols - 1, col))

        start_node = nearest_node(start)
        goal_node = nearest_node(goal)
        open_heap: List[Tuple[float, Tuple[int, int]]] = [(0.0, start_node)]
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start_node: 0.0}
        visited = 0
        directions = [
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ]

        while open_heap and visited < self.max_nodes:
            _, current_node = heapq.heappop(open_heap)
            visited += 1
            if current_node == goal_node:
                break
            current_point = point_for(current_node)
            for delta_row, delta_col in directions:
                neighbor = (
                    current_node[0] + delta_row,
                    current_node[1] + delta_col,
                )
                if not (0 <= neighbor[0] < rows and 0 <= neighbor[1] < cols):
                    continue
                neighbor_point = point_for(neighbor)
                leg_m = current_point.distance_to(neighbor_point)
                unit_east = (
                    neighbor_point.longitude - current_point.longitude
                ) * 111_320.0 * math.cos(math.radians(start.latitude))
                unit_north = (
                    neighbor_point.latitude - current_point.latitude
                ) * 111_320.0
                unit_length = math.hypot(unit_east, unit_north)
                if unit_length <= 0.0:
                    continue
                unit_east /= unit_length
                unit_north /= unit_length
                adverse_current = max(
                    0.0,
                    -(unit_east * current.east_mps + unit_north * current.north_mps),
                )
                adverse_wind = max(
                    0.0,
                    -(unit_east * wind.east_mps + unit_north * wind.north_mps),
                )
                effective_speed = max(
                    0.6,
                    ship_speed_mps - adverse_current - adverse_wind * 0.08,
                )
                tentative = g_score[current_node] + leg_m / effective_speed
                if tentative < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current_node
                    g_score[neighbor] = tentative
                    heuristic = neighbor_point.distance_to(goal) / ship_speed_mps
                    heapq.heappush(open_heap, (tentative + heuristic, neighbor))

        if goal_node not in g_score:
            return [start, goal], distance, distance / ship_speed_mps / 60.0

        nodes = [goal_node]
        while nodes[-1] != start_node:
            nodes.append(came_from[nodes[-1]])
        nodes.reverse()
        route = [start]
        route.extend(point_for(node) for node in nodes[1:-1])
        route.append(goal)
        route_distance = sum(
            route[index].distance_to(route[index + 1]) for index in range(len(route) - 1)
        )
        return route, route_distance, route_distance / ship_speed_mps / 60.0


def rescue_priority(
    alert_level: str,
    core_temp_c: float,
    capacitor_soc: float,
    battery_soc: float,
    stationary_seconds: float,
) -> float:
    """Return a bounded 0-100 priority score."""
    alert_component = 45.0 if alert_level == "sos" else 12.0 if alert_level == "watch" else 0.0
    temperature_component = max(0.0, min(30.0, (37.0 - core_temp_c) * 10.0))
    energy_component = (1.0 - max(capacitor_soc, battery_soc)) * 15.0
    immobility_component = min(10.0, stationary_seconds / 60.0)
    return max(
        0.0,
        min(100.0, alert_component + temperature_component + energy_component + immobility_component),
    )

