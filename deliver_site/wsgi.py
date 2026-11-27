"""WSGI entry point. Run in production with:  gunicorn delivery_site.wsgi"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "delivery_site.settings")

application = get_wsgi_application()
