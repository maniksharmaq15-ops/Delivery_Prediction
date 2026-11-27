from django.apps import AppConfig


class PredictorConfig(AppConfig):
    name = "predictor"

    def ready(self):
        # Load every model once at startup, so a missing or incompatible model file fails the
        # server immediately instead of on the first request.
        from . import services

        services.get_models()
