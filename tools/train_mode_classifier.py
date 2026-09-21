"""Train a random-forest wearer-mode classifier from tabular telemetry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="work/mode_training.csv")
    parser.add_argument("--output", default="models/mode_classifier.joblib")
    parser.add_argument("--metrics", default="work/mode_metrics.json")
    parser.add_argument("--seed", default=2026, type=int)
    args = parser.parse_args()

    frame = pd.read_csv(args.data)
    if "label" not in frame.columns:
        raise SystemExit("training data must contain a label column")
    features = frame.drop(columns=["label"])
    labels = frame["label"]
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.25,
        random_state=args.seed,
        stratify=labels,
    )
    model = RandomForestClassifier(
        n_estimators=240,
        max_depth=12,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=args.seed,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    report = classification_report(y_test, predictions, output_dict=True)
    matrix = confusion_matrix(y_test, predictions, labels=sorted(labels.unique())).tolist()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": list(features.columns)}, output)

    metrics_path = Path(args.metrics)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(
            {
                "classification_report": report,
                "confusion_matrix": matrix,
                "labels": sorted(labels.unique()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"model: {output}")
    print(f"metrics: {metrics_path}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

