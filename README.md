# Bastiq

A production-ready, multi-tenant SaaS backend (Django + DRF). It gives any SaaS
the three things needed on day one — **authentication**, **organizations &
role-based teams**, and **Stripe subscription billing** — with **correctly
isolated per-tenant data** as the headline guarantee.

> A *bastion* is a walled, defended stronghold; every tenant's data lives sealed
> behind its own walls.

## Status — complete (M0–M6)

| Milestone | Scope | State |
|---|---|---|
| **M0** | Skeleton, custom User model, Postgres, Docker, Celery, drf-spectacular, CI, `/healthz` | ✅ |
| **M1** | Auth: register, email verification, JWT login/refresh, password reset, `/me` | ✅ |
| **M2** | Organizations, memberships & active-org resolution | ✅ |
| **M3** | Multi-tenant isolation + Projects | ✅ |
| **M4** | RBAC (permission matrix) + invitations | ✅ |
| **M5** | Stripe billing: plans, checkout, portal, webhook, plan limits | ✅ |
| **M6** | Hardening: customized admin, seed data, Render deploy, full test suite | ✅ |

**~190 tests, ~95% coverage**, ruff-clean, OpenAPI schema validates with no
warnings. Each milestone was built on its own branch, adversarially reviewed,
and merged via PR.

## Tech stack

Python 3.12 · Django 5.2 · Django REST Framework · PostgreSQL 16 · Celery + Redis
· djangorestframework-simplejwt · drf-spectacular (OpenAPI/Swagger) · Stripe ·
Docker / docker-compose · GitHub Actions CI · pytest + factory_boy · ruff ·
gunicorn + WhiteNoise · Render (deploy).

## Architecture

Five apps; **all multi-tenancy isolation lives in `core/` only**:

```
HTTP (DRF)
  1. JWT auth            → request.user                         (accounts)
  2. active-org resolve  → request.organization                 (core: X-Organization-ID → Membership)
  3. role check          → IsOrganizationMember / RBAC matrix    (core)
  4. tenant queryset     → .filter(organization=request.org)     (core: TenantScopedViewSet)

core/          tenancy base classes, permissions, active-org resolution, RBAC matrix
accounts/      custom email-based User, auth views, /me
organizations/ Organization, Membership, Invitation + views
billing/       Plan, Subscription, WebhookEvent + Stripe + plan-limit enforcement
projects/      sample tenant-scoped resource (isolation + RBAC + limits, end-to-end)
```

The Django project package is `bastiq/` (settings, urls, celery, wsgi/asgi).

## Quickstart (Docker)

```bash
docker compose up                 # boots web + db + redis + worker (dev-safe defaults)
docker compose exec web python manage.py seed_demo   # demo org/users/projects
```

- Swagger UI: <http://localhost:8000/api/docs>
- Health: <http://localhost:8000/healthz> → `{"status": "ok"}`
- Admin: <http://localhost:8000/admin/> (`docker compose exec web python manage.py createsuperuser`)

### Demo credentials (from `seed_demo`)

Organization **Acme Inc** on the **Free** plan. All three users share the
password **`BastiqDemo!23`**. Use the org id printed by `seed_demo` as the
`X-Organization-ID` header for tenant-scoped requests.

| Email | Role |
|---|---|
| `owner@acme.test` | Owner |
| `admin@acme.test` | Admin |
| `member@acme.test` | Member |

## Local development (app outside Docker)

Needs a reachable Postgres + Redis (`docker compose up -d db redis`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgres://postgres:postgres@localhost:5432/bastiq
export DJANGO_DEBUG=true DJANGO_SECRET_KEY=dev-secret
python manage.py migrate && python manage.py seed_demo && python manage.py runserver
```

## Tests, lint, format

Tests use `bastiq.test_settings` (deterministic: in-memory email, eager Celery,
fast hashing) and need a Postgres at `DATABASE_URL` (defaults to `localhost:5432`).

```bash
pytest                       # the suite
pytest --cov                 # with coverage (CI gate: 90%)
ruff check . && ruff format --check .
```

## The demo script (live walkthrough)

1. Open **Swagger** (`/api/docs`).
2. **Register** → **verify email** (the token is printed to the worker log / email) → **login** for a JWT.
3. **Create org** "Demo Co" (you become Owner) → **invite** a teammate (`POST /api/organizations/{id}/invitations`) → they **accept** (`POST /api/invitations/accept`).
4. **Create projects** up to the Free limit (3) with `X-Organization-ID` set; the 4th is **blocked** with a clear `402 — plan limit reached`.
5. **Upgrade:** `POST /api/billing/checkout {plan_code: "pro"}` → pay in Stripe test Checkout with `4242 4242 4242 4242` → the **webhook** flips the subscription to **Pro** → the 4th project now succeeds.
6. **Isolation:** switch `X-Organization-ID` to a second org → the first org's projects are **invisible** (404).
7. **RBAC:** a Member can't change roles or delete the org; an Owner can.

## The three things to defend on a client call

### (a) Multi-tenant isolation — the invariant
The active organization is resolved in exactly **one** audited place
(`core/permissions.py::IsOrganizationMember`): from the `X-Organization-ID`
header, **validated against the caller's `Membership`**, then attached as
`request.organization`. A single base class (`core/viewsets.py::TenantScopedViewSet`)
filters every tenant queryset by it and stamps it on create. The org is **never**
read from the request body or query params, so a user can't act on an org they
don't belong to and can't smuggle another org's id through a payload. Cross-org
access returns **404** (you can't even learn the row exists). New tenant resources
inherit `TenantScopedModel` + `TenantScopedViewSet` and get this for free.

### (b) RBAC matrix
Roles rank **Owner(3) > Admin(2) > Member(1)** (`core/rbac.py`, asserted cell-by-cell):

| Action | Owner | Admin | Member |
|---|---|---|---|
| Read org/members; read/create project | ✓ | ✓ | ✓ |
| Update org | ✓ | ✓ | ✗ |
| Delete org | ✓ | ✗ | ✗ |
| Invite member | ✓ (any) | ✓ (≤ Admin) | ✗ |
| Change role / remove member | ✓ | ✓ (≤ Admin) | ✗ |
| Update/delete project | ✓ | ✓ | creator only |

Universal guards: **no escalation** (can't grant above your own rank) and **no
ownerless org** (can't demote/remove the last Owner).

### (c) Stripe billing + webhook
The **webhook is the source of truth**, not the success redirect: it verifies
`Stripe-Signature` on the raw body, dedupes on `WebhookEvent.stripe_event_id`
(idempotent), and maps `checkout.session.completed` /
`customer.subscription.updated|deleted` / `invoice.payment_failed` to local
`Subscription` state — record + process in one transaction so a failure
reprocesses on Stripe's retry. **Plan limits** are enforced server-side at
creation time (projects + members), locked against concurrent creates, returning
`402` over the cap.

## API surface

`/api/auth/` register · verify-email · login · token/refresh · password-reset(/confirm) · me
`/api/organizations[/{id}[/members/{mid}|/invitations]]` · `/api/invitations/accept`
`/api/projects[/{id}]` (tenant-scoped; needs `X-Organization-ID`)
`/api/billing/` plans · subscription · checkout · portal · webhook
`/api/docs` (Swagger) · `/api/schema` · `/healthz`

Auth: `Authorization: Bearer <access>`. Tenant resources also send
`X-Organization-ID: <org_id>` (validated against membership).

## Configuration

All deployment config is environment-driven — see [`.env.example`](.env.example).
Production security (HSTS, secure cookies, SSL redirect, proxy SSL header) turns
on automatically when `DJANGO_DEBUG=false`, and a missing `DJANGO_SECRET_KEY`
**aborts startup** (fail-closed). Swagger is public by default for the demo; set
`DOCS_REQUIRE_AUTH=true` to lock it down. Secrets are never committed.

## Deployment (Render)

[`render.yaml`](render.yaml) is a Blueprint: web (gunicorn) + worker (celery) +
Postgres + Redis. `web` and `worker` share one `DJANGO_SECRET_KEY` env group so
signed tokens minted by the worker verify in web. Deploy:

1. Push to GitHub → Render **New → Blueprint** → select this repo.
2. Set `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` (+ `STRIPE_PRICE_*`) on the env group.
3. The pre-deploy command runs `migrate` + `seed_plans`; run `seed_demo` once from the shell for the walkthrough.
4. Point a Stripe **test-mode** webhook at `https://<host>/api/billing/webhook` and set the signing secret.

`RENDER_EXTERNAL_HOSTNAME` is auto-appended to `ALLOWED_HOSTS`. The image runs as
a non-root user and `collectstatic` runs at build (WhiteNoise serves static).

## Acceptance checklist

- [x] `docker compose up` boots web + db + redis + worker; `/healthz` green
- [x] Custom User model from the first migration; email is the login
- [x] Register → verify → login → password reset; emails async (worker)
- [x] Creating an org makes the creator an Owner; roles enforced per the matrix
- [x] **Org B cannot read/write org A's data (tested); org never from the body**
- [x] Invitation invite + accept creates the correct membership
- [x] Stripe Checkout → subscription via webhook; signature verified; **duplicate processed once**; `payment_failed` handled
- [x] Plan limits enforced server-side (projects + members); clear error at the cap
- [x] Customized Django admin, org-scoped and filtered
- [x] Test suite passes (auth, isolation, RBAC, billing idempotency, limits)
- [x] Render Blueprint + Stripe webhook documented
- [x] README documents setup, the demo script, and the isolation invariant
