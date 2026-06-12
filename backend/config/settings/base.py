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
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}