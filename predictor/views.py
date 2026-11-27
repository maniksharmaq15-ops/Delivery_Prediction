import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_safe

from . import services
from .forms import OrderForm


@ensure_csrf_cookie  # the page reads this cookie and sends it back as X-CSRFToken on POST
@require_safe
def home(request):
    """The front end: a single HTML page that calls /options and /predict."""
    return render(request, "predictor/index.html")


@require_safe
def health(request):
    return JsonResponse({"status": "ok", "models_loaded": sorted(services.get_models())})


@require_safe
def options(request):
    """Allowed values for the categorical inputs, read from the trained encoder."""
    return JsonResponse(services.get_options())


@require_POST
def predict(request):
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Request body must be valid JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"detail": "Request body must be a JSON object."}, status=400)

    form = OrderForm(payload, services.get_options())
    if not form.is_valid():
        return JsonResponse({"detail": form.error_list()}, status=422)

    return JsonResponse(services.predict(form.cleaned_data))
