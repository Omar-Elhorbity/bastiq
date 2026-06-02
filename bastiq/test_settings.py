"""Test bootstrap settings.

This is NOT a deployment settings variant — it is the pytest entrypoint
(``DJANGO_SETTINGS_MODULE=bastiq.test_settings``). It pins a deterministic,
fast, side-effect-free environment *before* importing the real env-driven
settings, so the production module stays fail-closed (it raises on a missing
SECRET_KEY when DEBUG is false) while tests never depend on shell state.

Individual tests still override via ``@override_settings`` / the ``settings``
fixture.
"""

from __future__ import annotations

import os

_TEST_ENV = {
    # DEBUG=true → dev SECRET_KEY fallback allowed, prod security redirects off.
    "DJANGO_DEBUG": "true",
    "DJANGO_SECRET_KEY": "test-secret-key-not-for-production-0123456789",
    # Run Celery tasks inline so email/webhook side-effects are observable.
    "CELERY_TASK_ALWAYS_EAGER": "true",
    # In-memory email backend → assert against django.core.mail.outbox.
    "EMAIL_BACKEND": "locmem",
    # Fast password hashing.
    "USE_FAST_PASSWORD_HASHER": "true",
    # Generous throttle rates so functional tests don't trip limits; tests that
    # assert throttling override these explicitly with @override_settings.
    "THROTTLE_ANON": "100000/min",
    "THROTTLE_USER": "100000/min",
    "THROTTLE_LOGIN": "100000/min",
    "THROTTLE_REGISTER": "100000/min",
    "THROTTLE_PASSWORD_RESET": "100000/min",
    "THROTTLE_EMAIL_VERIFY": "100000/min",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

# Import the real, env-driven settings now that the test environment is in place.
from bastiq.settings import *  # noqa: E402,F401,F403
