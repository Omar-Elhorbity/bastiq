# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Bastiq image. Single stage on slim base; psycopg[binary] needs no libpq at
# build time. Runs as a non-root user. Default CMD serves via gunicorn (prod);
# docker-compose overrides the command for the dev/worker containers.
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime deps only.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Non-root runtime user.
RUN useradd --create-home --uid 1000 appuser

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/staticfiles && chown -R appuser:appuser /app/staticfiles

USER appuser

EXPOSE 8000

# Production default. Gunicorn serving WSGI; WhiteNoise serves static assets.
CMD ["gunicorn", "bastiq.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
