"""Model loading and prediction.

Serves the three scikit-learn pipelines saved by delivery_days_prediction.ipynb:
  - delivery_days_predictor.pkl : predicted actual delivery days (regression)
  - is_late_prediction.pkl      : will the order be late? (classification)
  - delay_prediction.pkl        : predicted delay in days (regression)
"""
import threading
from pathlib import Path

import joblib
import pandas as pd
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

MODEL_FILES = {
    "days": "delivery_days_predictor.pkl",
    "late": "is_late_prediction.pkl",
    "delay": "delay_prediction.pkl",
}

_lock = threading.Lock()
_models: dict | None = None
_options: dict | None = None


def _load() -> tuple[dict, dict]:
    models = {}
    for key, filename in MODEL_FILES.items():
        path = Path(settings.MODEL_DIR) / filename
        if not path.exists():
            raise ImproperlyConfigured(f"Missing model file: {path}")
        model = joblib.load(path)
        # Free instances have very little CPU; avoid spawning extra worker threads.
        step = model.steps[-1][1]
        if hasattr(step, "n_jobs"):
            step.n_jobs = 1
        models[key] = model

    # Allowed values for the categorical inputs, read from the trained encoder.
    pre = models["days"].named_steps["preprocessor"]
    cat_cols = next(cols for name, _, cols in pre.transformers_ if name == "cat")
    encoder = pre.named_transformers_["cat"]
    options = {col: [str(c) for c in cats] for col, cats in zip(cat_cols, encoder.categories_)}
    return models, options


def get_models() -> dict:
    """Return the loaded pipelines, loading them on first use (thread-safe)."""
    global _models, _options
    if _models is None:
        with _lock:
            if _models is None:
                _models, _options = _load()
    return _models


def get_options() -> dict:
    get_models()
    return _options


def predict(order: dict) -> dict:
    """order: validated input (see forms.OrderForm). Returns the JSON-ready prediction."""
    models = get_models()
    row = pd.DataFrame([order])

    clf = models["late"]
    late_idx = list(clf.classes_).index(1)

    return {
        "predicted_delivery_days": round(float(models["days"].predict(row)[0]), 2),
        "predicted_delay_days": round(float(models["delay"].predict(row)[0]), 2),
        "is_late": bool(clf.predict(row)[0] == 1),
        "late_probability": round(float(clf.predict_proba(row)[0][late_idx]), 3),
    }
