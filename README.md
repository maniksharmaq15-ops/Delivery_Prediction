# Delivery Prediction

A Django web service that estimates how many days an order will take to arrive, how long it may be delayed, and how likely it is to be late. It serves three scikit-learn pipelines trained on about 495,000 cleaned delivery orders, behind a small web page and a JSON API.

## Models

Trained in `delivery_days_prediction.ipynb` on an 80/20 split of 495,000 cleaned orders (99,000 held out for testing). The data was cleaned and explored in `eda_cleaning.ipynb`.

| Model | Task | Test result |
|---|---|---|
| `delivery_days_predictor.pkl` | Random Forest regressor: actual delivery days | R-squared 0.919, MAE 0.57 days |
| `is_late_prediction.pkl` | Random Forest classifier: will the order be late? | Accuracy 89.8% (late class: precision 0.81, recall 0.67, F1 0.73) |
| `delay_prediction.pkl` | Random Forest regressor: days of delay | R-squared 0.644, MAE 0.33 days |

Inputs: `distance_km`, `promised_days`, `seller_handling_hours`, `product_weight_kg`, `weather`, `is_festival_season`, `traffic_level`, `region`.

## Project layout

```
manage.py
delivery_site/        Django settings, URLs, WSGI entry point
predictor/
  services.py         loads the three models once at startup and runs predictions
  forms.py            input validation (ranges, allowed categories)
  views.py            page, /health, /options, /predict
  templates/predictor/index.html   the front end
  tests.py            15 tests
*.pkl                 the trained pipelines
```

The service has no database, login or admin site: it only loads the saved models and answers requests.

## Run locally

```bash
pip install -r requirements.txt
DJANGO_DEBUG=1 python manage.py runserver
```

On Windows PowerShell: `$env:DJANGO_DEBUG="1"; python manage.py runserver`. Then open http://127.0.0.1:8000/.

Run the tests (the three `.pkl` files must be in the project folder, or set `MODEL_DIR`):

```bash
DJANGO_DEBUG=1 python manage.py test
```

## API

| Endpoint | Description |
|---|---|
| `GET /` | The web page |
| `GET /health` | `{"status": "ok", "models_loaded": ["days", "delay", "late"]}` |
| `GET /options` | Allowed values for `weather`, `is_festival_season`, `traffic_level`, `region` |
| `POST /predict` | JSON order in, prediction out |

Example request body:

```json
{
  "distance_km": 1250.5,
  "promised_days": 5,
  "seller_handling_hours": 12,
  "product_weight_kg": 2.4,
  "weather": "Rain",
  "is_festival_season": "Yes",
  "traffic_level": "High",
  "region": "North"
}
```

Response:

```json
{
  "predicted_delivery_days": 4.98,
  "predicted_delay_days": 0.36,
  "is_late": false,
  "late_probability": 0.257
}
```

Errors: `400` for a body that is not a JSON object, `422` for invalid or unknown values (the response lists each problem), `405` for the wrong HTTP method.

`POST /predict` is protected by Django's CSRF check. The web page handles this automatically. From a script, fetch the page first to get the cookie, then send it back as a header:

```bash
curl -c jar.txt -s -o /dev/null http://127.0.0.1:8000/
curl -b jar.txt -H "X-CSRFToken: $(awk '/csrftoken/{print $7}' jar.txt)" \
     -H "Content-Type: application/json" -d @order.json http://127.0.0.1:8000/predict
```

## Deploy

Suggested settings for a Python web service host such as Render:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn delivery_site.wsgi --workers 1 --timeout 120`
- Environment variables: `DJANGO_SECRET_KEY` (any long random string). On Render, `RENDER_EXTERNAL_HOSTNAME` is set automatically and is allowed for you. On other hosts set `DJANGO_ALLOWED_HOSTS`.
- Use Python 3.12 or newer (developed on 3.13).
- Each worker uses about 240 MB of memory with all three models loaded, so use one worker on a 512 MB instance.

## Notes

- `scikit-learn` is pinned to 1.9.1, the version the `.pkl` files were trained with. If you retrain with a different version, update `requirements.txt` to match.
- The raw dataset (`delivery_data.csv`) is not included in the repository.
