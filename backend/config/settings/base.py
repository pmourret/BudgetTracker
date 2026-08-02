from datetime import timedelta
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECRET_KEY : prod via DJANGO_SECRET_KEY (env_file .env.prod).
# Fallback sur SECRET_KEY (convention dev existante), puis clé de dev non
# sécurisée en tout dernier recours pour ne pas bloquer un poste de dev.
SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default=config(
        "SECRET_KEY",
        default="django-insecure-dev-only-change-me-in-prod",
    ),
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Librairies
    "rest_framework",
    "django_filters",
    # Apps métier — seront ajoutées à l'étape 1C
        # Apps métier
    "core",
    "referentiels",
    "comptes",
    "categories",
    "flux",
    "budgets",
    "abonnements",
    "transferts",
    "patrimoine",
    "alertes",
    "objectifs",
    "market_data",
    "imports",
    "analytics",
    "audit",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Connexion DB lue depuis l'environnement.
# Prod : POSTGRES_* (alignés sur l'image postgres et le compose).
# Dev  : fallback sur les conventions DB_* existantes (.env).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default=config("DB_NAME", default="budgetfamilial")),
        "USER": config("POSTGRES_USER", default=config("DB_USER", default="budget")),
        "PASSWORD": config("POSTGRES_PASSWORD", default=config("DB_PASSWORD", default="")),
        "HOST": config("DB_HOST", default="db"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    # --- Authentification (durcissement, août 2026) ---------------------- #
    # L'API était `AllowAny` **en dev comme en prod** : n'importe quel appelant
    # du réseau pouvait écrire un flux. Le défaut est désormais fermé, et il
    # l'est **ici**, dans `base.py` : un réglage de sécurité posé dans un seul
    # environnement est un réglage qu'on oublie dans l'autre — c'est exactement
    # ce qui s'était passé, `prod.py` recopiant la dérogation de `dev.py`.
    #
    # **JWT seul, pas de `SessionAuthentication`.** Elle imposerait la
    # vérification CSRF sur toutes les écritures d'un client de navigateur, ce
    # que la dérogation d'origine cherchait précisément à éviter. L'admin Django
    # garde sa propre session, il n'est pas concerné.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # L'annuaire d'abord : il ne reconnaît que RS256 et renvoie `None` pour
        # tout le reste, laissant la classe suivante examiner les jetons locaux.
        "accounts.annuaire.JetonAnnuaire",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# Aligné sur FoyerOS (`config/settings/base.py`) : même durée, même rotation.
# La cohérence n'est pas cosmétique — les deux applications convergeront vers un
# service d'identité commun, et deux politiques de session divergentes seraient
# une dette à payer au moment de la fusion.
# --------------------------------------------------------------------------- #
# Service d'identité partagé (étape 4) — vérification, jamais émission
# --------------------------------------------------------------------------- #
# Clé **publique** de l'annuaire. Fournie par **fichier** de préférence : un PEM
# tient sur huit lignes, un `.env` ne porte pas de multiligne, et l'aplatir en
# `\n` échappés rate silencieusement (vécu côté FoyerOS).
_CHEMIN_CLE = config("IDENTITE_CLE_PUBLIQUE_FICHIER", default="")
if _CHEMIN_CLE and Path(_CHEMIN_CLE).exists():
    IDENTITE_CLE_PUBLIQUE = Path(_CHEMIN_CLE).read_text(encoding="utf-8")
else:
    IDENTITE_CLE_PUBLIQUE = config("IDENTITE_CLE_PUBLIQUE", default="").replace(
        "\\n", "\n"
    )

# ⚠️ **De quel foyer cette instance est-elle celle ?** Une instance BudgetTracker
# par foyer (décision de suite du 2026-08-01) : sans cet identifiant, impossible
# de juger si le porteur d'un jeton a affaire ici. **Sans lui, aucun jeton de
# l'annuaire n'est accepté** — fermé par défaut, plutôt que d'ouvrir « au cas où »
# la seule frontière que ce contrôle protège.
IDENTITE_FOYER = config("IDENTITE_FOYER", default="")

# Interrupteur de bascule : à `False`, BudgetTracker émet encore ses propres
# jetons ; à `True`, il relaie vers l'annuaire. Se rattrape par un réglage.
IDENTITE_AUTORITE = config("IDENTITE_AUTORITE", default="False") == "True"
IDENTITE_URL = config("IDENTITE_URL", default="http://host.docker.internal:8003")
IDENTITE_TIMEOUT = config("IDENTITE_TIMEOUT", default=5, cast=int)

# Les tests ne dépendent d'aucun réglage de déploiement (cf. `core/test_runner`).
TEST_RUNNER = "core.test_runner.LanceurBudgetTracker"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}