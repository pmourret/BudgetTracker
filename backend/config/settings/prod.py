from .base import *  # noqa

# DEBUG piloté par l'environnement (défaut sûr : False).
DEBUG = config("DJANGO_DEBUG", default="False") == "True"

# Hôtes autorisés : domaine LAN + nom de service interne (nginx → backend).
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="").split(",")

# Origines CSRF de confiance (HTTP, domaine .home.arpa non routable).
CSRF_TRUSTED_ORIGINS = [
    o for o in config("CSRF_TRUSTED_ORIGINS", default="").split(",") if o
]

# Fichiers statiques collectés (volume partagé avec nginx).
STATIC_ROOT = "/app/staticfiles"
STATIC_URL = "/static/"

# L'app est servie derrière nginx + Traefik : respecter l'hôte transmis.
USE_X_FORWARDED_HOST = True

# --- Contexte LAN strict, HTTP only (pas de TLS) ---
# .home.arpa n'est pas routable : pas de Let's Encrypt, donc pas de HTTPS.
# Forcer HTTPS / cookies secure / HSTS casserait l'accès. On les désactive
# EXPLICITEMENT (dette assumée pour cette Alpha auto-hébergée sur LAN).
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# --- Authentification désactivée (dette assumée — Alpha) ---
# On reproduit le comportement de dev : pas d'auth, AllowAny. À réactiver
# (JWT) en phase de durcissement. Sans cette surcharge, SessionAuthentication
# imposerait la vérification CSRF sur les écritures côté API.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # garde filtres + pagination de base.py
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}
