"""Bastiq project package.

Import the Celery app so that the ``@shared_task`` decorator and the worker
both find it when Django starts.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
