from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Enregistre les contrôles de démarrage (cf. `core/checks.py`).
        # Import ici et non au niveau du module : `checks.py` lit `settings`,
        # qui n'est pas garanti chargé au moment où `apps.py` est importé.
        from . import checks  # noqa: F401
