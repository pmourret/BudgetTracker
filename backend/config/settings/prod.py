from .base import *  # noqa

# DEBUG piloté par l'environnement (défaut sûr : False).
DEBUG = config("DJANGO_DEBUG", default="False") == "True"

# Hôtes autorisés : domaine LAN + nom de service interne (nginx → backend).
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="").split(",")

# Origines CSRF de confiance — en `https://` (le navigateur envoie l'Origin du
# schéma réel ; une entrée `http://` ne matcherait plus rien).
CSRF_TRUSTED_ORIGINS = [
    o for o in config("CSRF_TRUSTED_ORIGINS", default="").split(",") if o
]

# Fichiers statiques collectés (volume partagé avec nginx).
STATIC_ROOT = "/app/staticfiles"
STATIC_URL = "/static/"

# L'app est servie derrière nginx + Traefik : respecter l'hôte transmis.
USE_X_FORWARDED_HOST = True

# --- TLS terminé par Traefik (certificat Let's Encrypt wildcard, DNS-01) ---
# Django reçoit du trafic EN CLAIR depuis nginx : sans cet en-tête il croit être
# servi en HTTP et génère des URLs absolues en http:// (admin, redirections).
# Sûr ici car l'en-tête est réécrit à chaque saut : Traefik écrase ce qu'envoie
# le client, nginx relaie la valeur de Traefik (voir frontend/nginx.conf).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Tout passe désormais par `websecure` : les cookies peuvent être marqués Secure.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Inutile : le router Traefik n'écoute QUE sur `websecure`, rien n'arrive en
# clair. Le laisser à False évite aussi toute boucle de redirection si
# l'en-tête ci-dessus venait à manquer.
SECURE_SSL_REDIRECT = False

# HSTS volontairement à 0 : le certificat couvre TOUT `*.sternum-lab.duckdns.org`,
# donc l'activer engagerait les autres services du homelab qui partagent le
# domaine, sans retour arrière possible côté navigateur.
SECURE_HSTS_SECONDS = 0

# --- Authentification : dette soldée (durcissement, août 2026) ---
# Cette surcharge reproduisait `AllowAny` **en production** : l'API entière était
# ouverte en écriture à qui atteignait le domaine. Elle est retirée ; `base.py`
# fait foi (JWT + IsAuthenticated), et prod ne déroge plus à rien.
#
# ⚠️ Ne pas réintroduire de surcharge `REST_FRAMEWORK` ici. Si un besoin d'accès
# non authentifié apparaît (sonde, webhook), il se traite par une permission
# explicite **sur la vue concernée**, jamais en rouvrant le défaut global.
