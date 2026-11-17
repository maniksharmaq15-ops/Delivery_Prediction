"""FastAPI service for the Delivery_Prediction models.

Serves the three scikit-learn pipelines saved by delivery_days_prediction.ipynb:
  - delivery_days_predictor.pkl : predicted actual delivery days (regression)
  - is_late_prediction.pkl      : will the order be late? (classification)
  - delay_prediction.pkl        : predicted delay in days (regression)

Run locally:  uvicorn app:app --reload
Front end:        http://127.0.0.1:8000/
API test form:    http://127.0.0.1:8000/docs
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

MODEL_DIR = Path(os.environ.get("MODEL_DIR", Path(__file__).parent))
MODEL_FILES = {
    "days": "delivery_days_predictor.pkl",
    "late": "is_late_prediction.pkl",
    "delay": "delay_prediction.pkl",
}

models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load every model once at startup (the notebook reloaded from disk on each call).
    for key, filename in MODEL_FILES.items():
        path = MODEL_DIR / filename
        if not path.exists():
            raise RuntimeError(f"Missing model file: {path}")
        model = joblib.load(path)
        # Free instances have very little CPU; avoid spawning extra worker threads.
        step = model.steps[-1][1]
        if hasattr(step, "n_jobs"):
            step.n_jobs = 1
        models[key] = model
    yield
    models.clear()


app = FastAPI(title="Delivery Prediction API", lifespan=lifespan)


class Order(BaseModel):
    distance_km: float = Field(gt=0, examples=[1250.5])
    promised_days: float = Field(ge=0, examples=[5])
    seller_handling_hours: float = Field(ge=0, examples=[12.0])
    product_weight_kg: float = Field(gt=0, examples=[2.4])
    weather: str = Field(examples=["Rainy"])
    is_festival_season: Literal["Yes", "No"] = Field(examples=["Yes"])
    traffic_level: str = Field(examples=["High"])
    region: str = Field(examples=["North"])


INDEX_FILE = Path(__file__).parent / "index.html"


@app.get("/", include_in_schema=False)
def home():
    # The front end: a single HTML page that calls /options and /predict.
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return {"service": "Delivery Prediction API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": sorted(models)}


@app.get("/options")
def options():
    """Allowed values for the categorical inputs, read from the trained encoder."""
    pre = models["days"].named_steps["preprocessor"]
    cat_cols = next(cols for name, _, cols in pre.transformers_ if name == "cat")
    encoder = pre.named_transformers_["cat"]
    return {col: [str(c) for c in cats] for col, cats in zip(cat_cols, encoder.categories_)}


@app.post("/predict")
def predict(order: Order):
    row = pd.DataFrame([order.model_dump()])

    # Unknown category values would be silently ignored by the encoder
    # (handle_unknown='ignore'), so reject them with a clear message instead.
    allowed = options()
    for col, values in allowed.items():
        if str(row.at[0, col]) not in values:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {col!r}: {row.at[0, col]!r}. Allowed values: {values}",
            )

    clf = models["late"]
    late_idx = list(clf.classes_).index(1)

    return {
        "predicted_delivery_days": round(float(models["days"].predict(row)[0]), 2),
        "predicted_delay_days": round(float(models["delay"].predict(row)[0]), 2),
        "is_late": bool(clf.predict(row)[0] == 1),
        "late_probability": round(float(clf.predict_proba(row)[0][late_idx]), 3),
    }
