from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# --- Authentification désactivée en dev (pas d'auth avant la phase 14) ---
# On surcharge REST_FRAMEWORK hérité de base.py pour retirer
# SessionAuthentication, qui impose la vérification CSRF sur les POST/PATCH/DELETE.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # garde filtres + pagination de base.py
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

# Logs SQL en dev — pratique pour vérifier les requêtes générées
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}