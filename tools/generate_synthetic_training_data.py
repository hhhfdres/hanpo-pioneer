"""Generate synthetic data for CI and model pipeline smoke tests only."""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Dict, List


def sample(mode: str, rng: random.Random) -> Dict[str, float]:
    if mode == "active":
        base = {
            "core_temp_mean_c": rng.uniform(36.4, 37.2),
            "core_temp_slope_c_min": rng.uniform(-0.02, 0.03),
            "motion_variance": rng.uniform(0.25, 1.4),
            "stationary_seconds": rng.uniform(0, 60),
            "ambient_temp_c": rng.uniform(-35, 30),
            "surface_temp_c": rng.uniform(38, 48),
        }
    elif mode == "resting":
        base = {
            "core_temp_mean_c": rng.uniform(35.8, 36.8),
            "core_temp_slope_c_min": rng.uniform(-0.09, 0.005),
            "motion_variance": rng.uniform(0.01, 0.15),
            "stationary_seconds": rng.uniform(120, 900),
            "ambient_temp_c": rng.uniform(-35, 20),
            "surface_temp_c": rng.uniform(36, 44),
        }
    else:
        base = {
            "core_temp_mean_c": rng.uniform(32.0, 35.8),
            "core_temp_slope_c_min": rng.uniform(-0.35, -0.10),
            "motion_variance": rng.uniform(0.0, 0.08),
            "stationary_seconds": rng.uniform(300, 2400),
            "ambient_temp_c": rng.uniform(-40, 12),
            "surface_temp_c": rng.uniform(34, 42),
        }
    base["label"] = mode
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="work/mode_training.csv")
    parser.add_argument("--samples-per-class", default=1200, type=int)
    parser.add_argument("--seed", default=2026, type=int)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    rows: List[Dict[str, object]] = []
    for mode in ("active", "resting", "unconscious"):
        for _ in range(args.samples_per_class):
            rows.append(sample(mode, rng))
    rng.shuffle(rows)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

