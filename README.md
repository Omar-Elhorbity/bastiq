# Bastiq

A production-ready, multi-tenant SaaS backend (Django + DRF). It gives any SaaS
the three things needed on day one — **authentication**, **organizations &
role-based teams**, and **Stripe subscription billing** — with **correctly
isolated per-tenant data** as the headline guarantee.

> A *bastion* is a walled, defended stronghold; every tenant's data lives sealed
> behind its own walls.

## Status

Built milestone by milestone. **M0–M1 complete.**

| Milestone | Scope | State |
|---|---|---|
| **M0** | Project skeleton, custom User model, Postgres, Docker, Celery, drf-spectacular, CI, `/healthz` | ✅ |
| **M1** | Auth: register, email verification, JWT login/refresh, password reset, `/me` | ✅ |
| M2 | Organizations & active-org resolution | ⏳ |
| M3 | Multi-tenant isolation + Projects | ⏳ |
| M4 | RBAC + invitations | ⏳ |
| M5 | Stripe billing | ⏳ |
| M6 | Hardening, admin, seed, deploy | ⏳ |

## Tech stack

Python 3.12 · Django 5.2 · Django REST Framework · PostgreSQL 16 · Celery + Redis
· djangorestframework-simplejwt · drf-spectacular (OpenAPI/Swagger) · Stripe ·
Docker / docker-compose · GitHub Actions CI · pytest + factory_boy · ruff.

## Architecture

Five apps; all multi-tenancy isolation will live in `core/` only (M3):

```
core/          tenancy base classes, permissions, active-org resolution
accounts/      custom email-based User, auth views, /me
organizations/ Organization, Membership, Invitation + views
billing/       Plan, Subscription, WebhookEvent + Stripe + limit enforcement
projects/      sample tenant-scoped resource (isolation + RBAC + limits)
```

The Django project package is `bastiq/` (settings, urls, celery, wsgi/asgi).

## Quickstart (Docker)

```bash
cp .env.example .env          # optional; compose has dev-safe defaults
docker compose up             # boots web + db + redis + worker
```

Then:

- Health: <http://localhost:8000/healthz> → `{"status": "ok"}`
- Swagger UI: <http://localhost:8000/api/docs>
- Django admin: <http://localhost:8000/admin/> (create a superuser first)

Create an admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

## Local development (without Docker for the app)

Requires a reachable Postgres and Redis (e.g. `docker compose up -d db redis`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

export DATABASE_URL=postgres://postgres:postgres@localhost:5432/bastiq
export DJANGO_DEBUG=true DJANGO_SECRET_KEY=dev-secret

python manage.py migrate
python manage.py runserver
```

## Tests, lint, format

The test suite uses `bastiq.test_settings`, which pins a deterministic, fast
environment (in-memory email, eager Celery, fast hashing). It needs a Postgres
reachable at `DATABASE_URL` (defaults to `localhost:5432`).

```bash
pytest                       # run the suite
pytest --cov                 # with coverage (CI gate: 80%)
ruff check . && ruff format --check .
```

## Configuration

All deployment config is environment-driven — see [`.env.example`](.env.example).
Security defaults (HSTS, secure cookies, SSL redirect, etc.) switch on
automatically when `DJANGO_DEBUG=false`. Secrets are never committed.

## Auth API (M1)

All under `/api/auth/` (JSON):

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /register` | public | Create an unverified user; sends a verification email (async) |
| `POST /verify-email` | public | Confirm email from a signed token |
| `POST /login` | public | Obtain a JWT `access` + `refresh` pair |
| `POST /token/refresh` | public | Rotate a refresh token for a new access token |
| `POST /password-reset` | public | Request a reset email (always `202`; no user enumeration) |
| `POST /password-reset/confirm` | public | Set a new password from a single-use token |
| `GET /me` | JWT | The authenticated user |

**Token strategy.** Email-verification and password-reset tokens are signed,
expiring payloads via `django.core.signing` (no token table). Distinct salts
bind each token to its flow. Reset tokens are single-use — they embed a
fingerprint of the password hash + `last_login`, so resetting (or logging in)
invalidates outstanding reset links.

**Session security.** JWT refresh tokens rotate and the consumed one is
blacklisted. A password reset blacklists the user's outstanding refresh tokens,
so a stolen session can't be refreshed and dies once its short access token
(≤ `JWT_ACCESS_MINUTES`) expires.

**Brute-force protection.** Credential endpoints are scope-throttled (defaults):
login `10/min`, register `10/hour`, password-reset `5/hour`, verify-email
`20/hour` — all tunable via env.

## Security posture (M0)

- Custom `accounts.User` set as `AUTH_USER_MODEL` from the first migration; email
  is the login identifier.
- DRF defaults to `IsAuthenticated` — endpoints opt **out** to be public.
- JWT via simplejwt; access/refresh lifetimes are env-tunable.
- Runs as a non-root user in the container.
- Fail-closed: in production a missing `DJANGO_SECRET_KEY` aborts startup rather
  than booting insecurely.

The full demo script and the isolation-invariant write-up land in M6.
