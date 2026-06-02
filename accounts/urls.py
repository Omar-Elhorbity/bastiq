"""Auth routes, mounted under /api/auth/ by the root urlconf."""

from __future__ import annotations

from django.urls import path

from accounts.views import (
    LoginView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    RegisterView,
    VerifyEmailView,
)

app_name = "accounts"

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("verify-email", VerifyEmailView.as_view(), name="verify-email"),
    path("login", LoginView.as_view(), name="login"),
    path("token/refresh", RefreshView.as_view(), name="token-refresh"),
    path("password-reset", PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "password-reset/confirm",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("me", MeView.as_view(), name="me"),
]
