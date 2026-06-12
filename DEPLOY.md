# Déploiement — BudgetTracker (Alpha, LAN strict)

Cible : serveur Docker auto-hébergé, **LAN strict** (pas d'exposition Internet),
reverse proxy **Traefik** existant, domaine local `budgets.core.home.arpa`
(non routable, **HTTP only** — pas de TLS).

Infra réutilisée (NE PAS recréer) :
- réseau Traefik externe `proxy` (entrypoint `web`, port 80) ;
- réseau interne externe `backend` ;
- bind-mounts sous `/var/lib/docker/hiatus/budgets/`.

> ⚠️ Auth désactivée = dette assumée pour cette Alpha. Aucune donnée métier de
> démo : l'appli démarre vierge, seuls les **référentiels structurels** sont
> créés (commande `seed_referentiels`, idempotente, lancée par l'entrypoint).

## Séquence de déploiement

```bash
# 1. Créer les dossiers de bind-mount
sudo mkdir -p /var/lib/docker/hiatus/budgets/pgdata
sudo mkdir -p /var/lib/docker/hiatus/budgets/static

# 2. Vérifier que les réseaux externes existent (les réutiliser, ne pas les créer)
docker network ls | grep -E "proxy|backend"

# 3. Créer .env.prod à partir de .env.prod.example (secrets réels)
#    Générer la SECRET_KEY :
#    docker compose -f docker-compose.prod.yml run --rm backend \
#      python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. Build + up
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f backend

# Vérif : http://budgets.core.home.arpa (front) et /admin/ (Django)
# DNS : budgets.core.home.arpa doit résoudre vers l'IP du serveur (DNS local).
```

## Ce que fait l'entrypoint backend au démarrage

1. `migrate --noinput` — applique les migrations.
2. `collectstatic --noinput` — collecte les statiques Django dans le volume
   partagé `/app/staticfiles` (servi par nginx sous `/static/`).
3. `seed_referentiels` — crée les 9 référentiels structurels (idempotent).
4. `gunicorn config.wsgi:application` — sert l'API (jamais `runserver`).

Le frontend est servi en **build statique par Nginx** (jamais le dev server
Vite). Nginx proxifie `^/(api|admin)/` vers `backend:8000` et sert le SPA.

## Variables d'environnement (.env.prod)

Voir `.env.prod.example`. Points clés :
- `DJANGO_SETTINGS_MODULE=config.settings.prod` (obligatoire : `manage.py` et
  `wsgi.py` font `setdefault` sur `config.settings.dev`).
- `DJANGO_SECRET_KEY` — secret réel, jamais committé.
- `DJANGO_ALLOWED_HOSTS=budgets.core.home.arpa,backend` (le second pour les
  appels nginx → backend via le nom de service).
- `CSRF_TRUSTED_ORIGINS=http://budgets.core.home.arpa`.
- `POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD` — lus par l'image postgres
  ET par Django (settings `base.py`).

## Notes sécurité (Alpha)

- **HTTP only** assumé : `SECURE_SSL_REDIRECT`, cookies secure et HSTS sont
  désactivés dans `config/settings/prod.py` (`.home.arpa` non routable → pas de
  Let's Encrypt). À durcir si TLS interne plus tard.
- Auth désactivée (AllowAny). À réactiver (JWT) en phase de durcissement.
- `seed_demo` ne doit **jamais** être lancé en prod (données métier de démo).
