"""Celery application for Bastiq.

Async work (verification/reset/invite emails, Stripe webhook side-effects) runs
through this app. Settings are read from Django under the ``CELERY_`` namespace.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bastiq.settings")

app = Celery("bastiq")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # pragma: no cover - diagnostic only
    print(f"Request: {self.request!r}")
