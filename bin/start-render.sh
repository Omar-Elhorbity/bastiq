#!/usr/bin/env sh
# Start command for the Render free-tier web service (referenced by render.yaml).
#
# Free instances have no preDeployCommand and no Shell, so migrations + seeding
# run here before gunicorn starts. This lives in a script (not an inline
# dockerCommand) so there are no YAML-folding or shell-quoting pitfalls.
set -e

python manage.py migrate --noinput
python manage.py seed_demo || echo "seed_demo failed; continuing"
# Best-effort admin: only creates one when DJANGO_SUPERUSER_* are set, and is a
# harmless no-op on later boots once the user already exists.
python manage.py createsuperuser --noinput || true

exec gunicorn bastiq.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 2 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
