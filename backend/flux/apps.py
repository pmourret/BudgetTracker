from django.apps import AppConfig


class FluxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "flux"

    def ready(self):
        import flux.signals  # noqa — enregistre les signals au démarrage