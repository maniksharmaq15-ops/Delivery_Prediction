"""Tests for the Delivery Prediction service.

Run from the project folder (the three .pkl files must be there, or set MODEL_DIR):
    DJANGO_DEBUG=1 python manage.py test
"""
import json

from django.test import Client, SimpleTestCase

VALID_ORDER = {
    "distance_km": 1250.5,
    "promised_days": 5,
    "seller_handling_hours": 12.0,
    "product_weight_kg": 2.4,
    "weather": "Rain",
    "is_festival_season": "Yes",
    "traffic_level": "High",
    "region": "North",
}


class PredictorTests(SimpleTestCase):
    def post(self, payload, client=None, **extra):
        client = client or self.client
        body = payload if isinstance(payload, str) else json.dumps(payload)
        return client.post("/predict", data=body, content_type="application/json", **extra)

    # --- pages and read-only endpoints -------------------------------------------------
    def test_home_serves_page_and_sets_csrf_cookie(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delivery time check")
        self.assertIn("csrftoken", response.cookies)

    def test_health_lists_all_three_models(self):
        data = self.client.get("/health").json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["models_loaded"], ["days", "delay", "late"])

    def test_options_come_from_the_trained_encoder(self):
        data = self.client.get("/options").json()
        self.assertEqual(set(data), {"weather", "is_festival_season", "traffic_level", "region"})
        self.assertIn("Clear", data["weather"])
        self.assertEqual(sorted(data["is_festival_season"]), ["No", "Yes"])
        self.assertEqual(sorted(data["region"]), ["East", "North", "South", "West"])

    # --- predictions ---------------------------------------------------------------------
    def test_predict_returns_all_four_fields_with_sane_values(self):
        response = self.post(VALID_ORDER)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data),
            {"predicted_delivery_days", "predicted_delay_days", "is_late", "late_probability"},
        )
        self.assertIsInstance(data["is_late"], bool)
        self.assertGreater(data["predicted_delivery_days"], 0)
        self.assertTrue(0 <= data["late_probability"] <= 1)

    def test_predict_is_deterministic(self):
        self.assertEqual(self.post(VALID_ORDER).json(), self.post(VALID_ORDER).json())

    def test_numbers_sent_as_strings_are_accepted(self):
        order = {**VALID_ORDER, "distance_km": "1250.5", "promised_days": "5"}
        self.assertEqual(self.post(order).json(), self.post(VALID_ORDER).json())

    def test_extra_fields_are_ignored(self):
        self.assertEqual(self.post({**VALID_ORDER, "note": "x"}).status_code, 200)

    # --- validation ----------------------------------------------------------------------
    def assert_rejected(self, payload, field):
        response = self.post(payload)
        self.assertEqual(response.status_code, 422)
        fields = [error["loc"][-1] for error in response.json()["detail"]]
        self.assertIn(field, fields)

    def test_unknown_category_is_rejected_with_allowed_values(self):
        response = self.post({**VALID_ORDER, "weather": "Rainy"})
        self.assertEqual(response.status_code, 422)
        message = response.json()["detail"][0]["msg"]
        self.assertIn("Rainy", message)
        self.assertIn("Heavy Rain", message)

    def test_non_positive_distance_and_weight_are_rejected(self):
        for value in (0, -5):
            self.assert_rejected({**VALID_ORDER, "distance_km": value}, "distance_km")
            self.assert_rejected({**VALID_ORDER, "product_weight_kg": value}, "product_weight_kg")

    def test_negative_days_and_hours_are_rejected_but_zero_is_allowed(self):
        self.assert_rejected({**VALID_ORDER, "promised_days": -1}, "promised_days")
        self.assert_rejected({**VALID_ORDER, "seller_handling_hours": -1}, "seller_handling_hours")
        self.assertEqual(self.post({**VALID_ORDER, "promised_days": 0}).status_code, 200)

    def test_missing_and_non_numeric_fields_are_rejected(self):
        incomplete = {k: v for k, v in VALID_ORDER.items() if k != "region"}
        self.assert_rejected(incomplete, "region")
        self.assert_rejected({**VALID_ORDER, "distance_km": "far"}, "distance_km")

    def test_infinite_and_nan_numbers_are_rejected(self):
        for bad in ("Infinity", "NaN"):
            body = json.dumps(VALID_ORDER).replace("1250.5", bad)
            self.assertEqual(self.post(body).status_code, 422)

    def test_malformed_json_and_non_object_bodies_are_400(self):
        self.assertEqual(self.post("{not json").status_code, 400)
        self.assertEqual(self.post("[1, 2, 3]").status_code, 400)

    def test_wrong_methods_are_405(self):
        self.assertEqual(self.client.get("/predict").status_code, 405)
        self.assertEqual(self.client.post("/health").status_code, 405)

    # --- CSRF ----------------------------------------------------------------------------
    def test_post_without_csrf_token_is_forbidden_and_with_token_works(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(VALID_ORDER, client=strict).status_code, 403)

        token = strict.get("/").cookies["csrftoken"].value
        response = self.post(VALID_ORDER, client=strict, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
