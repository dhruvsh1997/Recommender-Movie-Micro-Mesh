"""
App configuration for the User Service app.

The ready() method imports signals to ensure they are registered
when Django starts up.
"""

from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"
    verbose_name = "User & Ratings Service"

    def ready(self):
        """Import signals module to register post_save / post_delete hooks."""
        import app.signals  # noqa: F401
