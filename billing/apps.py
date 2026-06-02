from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Billing (plans, subscriptions, Stripe)"

    def ready(self) -> None:
        # Connect the org → Free-subscription signal.
        from billing import signals  # noqa: F401
