"""Shared, app-agnostic views."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(_request: HttpRequest) -> JsonResponse:
    """Liveness probe.

    Intentionally dependency-free (no DB/Redis hit) so it answers fast and is
    safe to hammer from a load balancer. Public, no auth, no throttling.
    """
    return JsonResponse({"status": "ok"})


# A tiny, self-contained landing page for the site root. No template/static
# dependencies (inline HTML+CSS) so it renders anywhere with no extra config.
_LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bastiq — multi-tenant SaaS backend</title>
<style>
  :root {
    --bg:#0b1020; --card:#141a2e; --fg:#e8edf7; --muted:#9aa6c0;
    --accent:#6ea8fe; --accent-fg:#08122b; --line:#26304d;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; min-height:100vh; color:var(--fg);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:radial-gradient(1100px 600px at 50% -15%, #1c2747 0%, var(--bg) 60%);
    display:flex; align-items:center; justify-content:center; padding:32px;
  }
  .card {
    width:100%; max-width:620px; background:var(--card); border:1px solid var(--line);
    border-radius:16px; padding:40px 36px; box-shadow:0 20px 60px rgba(0,0,0,.45);
  }
  .brand { font-size:30px; font-weight:700; letter-spacing:-.5px; margin:0 0 6px; }
  .tag { color:var(--muted); margin:0 0 24px; }
  .actions { display:flex; flex-wrap:wrap; gap:12px; margin:0 0 26px; }
  a.btn {
    text-decoration:none; padding:11px 18px; border-radius:10px; font-weight:600;
    border:1px solid var(--line); color:var(--fg); background:#1b2440; transition:.15s;
  }
  a.btn:hover { border-color:var(--accent); }
  a.btn.primary { background:var(--accent); color:var(--accent-fg); border-color:var(--accent); }
  .demo { border-top:1px solid var(--line); padding-top:20px; color:var(--muted); font-size:14.5px; }
  .demo h2 { font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin:0 0 10px; }
  code { background:#0e1426; border:1px solid var(--line); border-radius:6px; padding:2px 6px; color:#cfe0ff; font-size:13px; }
  .note { margin-top:14px; font-size:13px; color:#7e8aa6; }
</style>
</head>
<body>
  <main class="card">
    <h1 class="brand">Bastiq</h1>
    <p class="tag">A production-ready, multi-tenant SaaS backend in Django + DRF —
       authentication, organizations &amp; role-based teams, and Stripe billing,
       with correctly isolated per-tenant data.</p>
    <nav class="actions">
      <a class="btn primary" href="/api/docs">Explore the API &rarr;</a>
      <a class="btn" href="/healthz">Health</a>
      <a class="btn" href="/admin/">Admin</a>
      <a class="btn" href="https://github.com/Omar-Elhorbity/bastiq">Source on GitHub</a>
    </nav>
    <section class="demo">
      <h2>Try the demo</h2>
      <p>Sign in at <a class="link" href="/api/docs" style="color:var(--accent)">/api/docs</a> with
         <code>owner@acme.test</code> / <code>BastiqDemo!23</code>, then send
         <code>X-Organization-ID: 1</code> on tenant-scoped requests.</p>
      <p class="note">Hosted on a free tier — the first request after idle may take
         ~30–60s to wake.</p>
    </section>
  </main>
</body>
</html>
"""


@require_GET
def landing(_request: HttpRequest) -> HttpResponse:
    """Public site root: a small landing page that points to the docs, health,
    admin, and source. Saves the bare domain from being a 404."""
    return HttpResponse(_LANDING_HTML)
