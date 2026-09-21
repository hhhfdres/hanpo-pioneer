"""Train an SVM battery-SOH regressor from a tabular dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--target", default="soh")
    parser.add_argument("--output", default="models/soh_svm.joblib")
    parser.add_argument("--seed", default=2026, type=int)
    args = parser.parse_args()

    frame = pd.read_csv(args.data)
    if args.target not in frame.columns:
        raise SystemExit(f"target column not found: {args.target}")
    features = frame.drop(columns=[args.target])
    target = frame[args.target]
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.25,
        random_state=args.seed,
    )
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("svr", SVR(kernel="rbf", C=8.0, epsilon=0.01)),
        ]
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": list(features.columns)}, output)
    print(f"model: {output}")
    print(f"mae: {mean_absolute_error(y_test, predictions):.5f}")
    print(f"r2: {r2_score(y_test, predictions):.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

