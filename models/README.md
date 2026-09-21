# Models

This directory receives locally trained model artifacts. Binary model files are ignored by Git because dataset provenance, validation results, and deployment approval must accompany each release.

Expected artifact names:

- `mode_classifier.joblib`
- `soh_svm.joblib`

For production, export the approved model to ONNX or TensorFlow Lite and record:

- training data version and consent boundary,
- training and validation split,
- subgroup and worst-case metrics,
- quantization behavior,
- fallback threshold,
- rollback package hash.

