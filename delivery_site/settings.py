"""Django settings for the Delivery Prediction service.

The service is stateless: it loads three pre-trained scikit-learn pipelines and answers JSON
requests, so there is no database, authentication or admin site.

Environment variables
---------------------
DJANGO_DEBUG           "1" for local development. Defaults to off (production behaviour).
DJANGO_SECRET_KEY      Required unless DJANGO_DEBUG=1.
DJANGO_ALLOWED_HOSTS   Comma-separated hostnames. Defaults to localhost only.
MODEL_DIR              Folder containing the three .pkl files. Defaults to the project folder.
RENDER_EXTERNAL_HOSTNAME  Set automatically by Render; its host and https origin are allowed.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(int(default))).strip().lower() in {"1", "true", "yes", "on"}


DEBUG = _env_bool("DJANGO_DEBUG")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key"
    else:
        raise ImproperlyConfigured(
            "Set DJANGO_SECRET_KEY, or set DJANGO_DEBUG=1 for local development."
        )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if h.strip()
]
CSRF_TRUSTED_ORIGINS: list[str] = []

_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")
    # Render terminates TLS in front of the app and forwards the original scheme.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "predictor.apps.PredictorConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "delivery_site.urls"
WSGI_APPLICATION = "delivery_site.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# No database: the service only serves predictions from saved models.
DATABASES = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# The CSRF cookie must stay readable by the page's JavaScript (it sends it back as a header),
# so it is not HttpOnly. In production it is only sent over HTTPS.
CSRF_COOKIE_SECURE = not DEBUG

# Where the three trained pipelines live.
MODEL_DIR = Path(os.environ.get("MODEL_DIR", BASE_DIR))
