from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# --- Authentification : plus aucune dérogation ici (durcissement, août 2026) ---
# `base.py` ferme l'API par défaut (JWT + IsAuthenticated). Dev et prod sont
# désormais **identiques sur ce point**, volontairement : la surcharge qui vivait
# ici avait été recopiée telle quelle dans `prod.py`, et une API ouverte tournait
# en production. Un réglage de sécurité qui diffère entre environnements finit
# toujours par être testé dans le mauvais.
#
# Pour se connecter en dev : `python manage.py creer_utilisateur --email … `.

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