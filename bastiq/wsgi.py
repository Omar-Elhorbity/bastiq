"""WSGI entrypoint (gunicorn serves this in production)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bastiq.settings")

application = get_wsgi_application()
