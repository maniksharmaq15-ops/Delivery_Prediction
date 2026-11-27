"""Input validation for /predict, using a Django form."""
from django import forms
from django.core.exceptions import ValidationError

CATEGORICAL_FIELDS = ("weather", "is_festival_season", "traffic_level", "region")


def _positive(value: float) -> None:
    if value <= 0:
        raise ValidationError("Must be greater than 0.")


def _non_negative(value: float) -> None:
    if value < 0:
        raise ValidationError("Must be 0 or more.")


class OrderForm(forms.Form):
    distance_km = forms.FloatField(validators=[_positive])
    promised_days = forms.FloatField(validators=[_non_negative])
    seller_handling_hours = forms.FloatField(validators=[_non_negative])
    product_weight_kg = forms.FloatField(validators=[_positive])
    weather = forms.ChoiceField(choices=())
    is_festival_season = forms.ChoiceField(choices=())
    traffic_level = forms.ChoiceField(choices=())
    region = forms.ChoiceField(choices=())

    def __init__(self, data, options: dict, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        # Unknown category values would be silently ignored by the encoder
        # (handle_unknown='ignore'), so reject them with a clear message instead.
        for name in CATEGORICAL_FIELDS:
            allowed = options[name]
            field = self.fields[name]
            field.choices = [(value, value) for value in allowed]
            field.error_messages["invalid_choice"] = (
                "Invalid value %(value)s. Allowed values: " + ", ".join(allowed) + "."
            )

    def error_list(self) -> list[dict]:
        """Errors as [{"loc": [field], "msg": text}, ...], the shape the page's JS already reads."""
        return [
            {"loc": [field], "msg": error["message"]}
            for field, errors in self.errors.get_json_data().items()
            for error in errors
        ]
