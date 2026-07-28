# Déploiement — BudgetTracker (Alpha, LAN strict)

Cible : serveur Docker auto-hébergé, **LAN strict** (pas d'exposition Internet),
reverse proxy **Traefik** existant, domaine `budgets.sternum-lab.duckdns.org`
en **HTTPS** (certificat Let's Encrypt valide).

Infra réutilisée (NE PAS recréer) :
- réseau Traefik externe `proxy` (entrypoint **`websecure`**, port 443) ;
- résolveur de certificat Traefik **`duckdns`** (challenge DNS-01) ;
- réseau interne externe `backend` ;
- bind-mounts sous `/var/lib/docker/hiatus/budgets/`.

## DNS et TLS — pourquoi ce domaine

`*.core.home.arpa` a été abandonné : `home.arpa` est **réservé par la RFC 8375**
et les résolveurs conformes ont l'**obligation de ne jamais le transmettre en
amont**. Certains appareils du réseau (constaté sur un téléphone Samsung) ne le
résolvaient donc pas, malgré un DNS réseau correct.

`sternum-lab.duckdns.org` est un domaine public ordinaire : aucun résolveur ne
le filtre. Il n'est pourtant **jamais exposé** — aucun port n'est ouvert sur
internet, l'IP publique enregistrée chez DuckDNS n'a aucune importance :

- **AdGuard Home** réécrit `*.sternum-lab.duckdns.org` → `192.168.1.139` (IP du
  serveur Traefik). Une seule règle wildcard couvre tous les services.
- **Traefik** obtient un certificat **wildcard** par challenge **DNS-01** (pas
  HTTP-01) : Let's Encrypt vérifie un enregistrement TXT chez DuckDNS, il n'a
  jamais besoin d'atteindre le serveur.

> ⚠️ **Un seul niveau de sous-domaine.** Le wildcard ne couvre pas
> `import.budgets.sternum-lab.duckdns.org`. Si un jour BudgetTracker expose une
> seconde entrée, l'aplatir : `budgets-import.sternum-lab.duckdns.org`.

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
#    ⚠️ `--force-recreate` : Traefik lit les labels sur le CONTENEUR EN COURS,
#    pas dans le fichier compose. Modifier le compose puis faire un simple
#    `restart` laisse l'ancien routage actif (piège vécu lors de la migration).
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d --force-recreate
docker compose -f docker-compose.prod.yml logs -f backend

# Vérif : https://budgets.sternum-lab.duckdns.org (front) et /admin/ (Django)
# DNS : la réécriture AdGuard `*.sternum-lab.duckdns.org` → IP du serveur suffit.
```

## Vérifier le routage et le certificat

```bash
# Tester sans dépendre du DNS (remplacer l'IP si le serveur Traefik change)
curl -vk --resolve budgets.sternum-lab.duckdns.org:443:192.168.1.139 \
  https://budgets.sternum-lab.duckdns.org/
```

Lecture du résultat :

| Symptôme | Cause |
|---|---|
| 404 en **texte brut** Traefik | Aucun router ne matche → vérifier `Host()`, `entrypoints`, et que le conteneur a bien été **recréé** |
| 404 **stylé par l'app** (SPA) | Le routage est bon, le problème est applicatif |
| Certificat auto-signé `TRAEFIK DEFAULT CERT` | `tls.certresolver` absent ou posé sur un **autre nom de router** que la règle |

Le dashboard Traefik (`HTTP → Routers`) doit afficher la règle attendue : c'est
la source de vérité, pas le fichier compose.

## Ce que fait l'entrypoint backend au démarrage

1. `migrate --noinput` — applique les migrations.
2. `collectstatic --noinput` — collecte les statiques Django dans le volume
   partagé `/app/staticfiles` (servi par nginx sous `/static/`).
3. `seed_referentiels` — crée les 9 référentiels structurels + le singleton `ParametresBudget` (mois comptable, défaut 1 = calendaire), idempotent.
4. `gunicorn config.wsgi:application` — sert l'API (jamais `runserver`).

Le frontend est servi en **build statique par Nginx** (jamais le dev server
Vite). Nginx proxifie `^/(api|admin)/` vers `backend:8000` et sert le SPA.

## Variables d'environnement (.env.prod)

Voir `.env.prod.example`. Points clés :
- `DJANGO_SETTINGS_MODULE=config.settings.prod` (obligatoire : `manage.py` et
  `wsgi.py` font `setdefault` sur `config.settings.dev`).
- `DJANGO_SECRET_KEY` — secret réel, jamais committé.
- `DJANGO_ALLOWED_HOSTS=budgets.sternum-lab.duckdns.org,backend` (le second pour
  les appels nginx → backend via le nom de service).
- `CSRF_TRUSTED_ORIGINS=https://budgets.sternum-lab.duckdns.org` — **schéma
  `https://` obligatoire** : Django compare l'`Origin` réel du navigateur, une
  entrée `http://` ne matcherait plus rien (403 CSRF sur l'admin).
- `POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD` — lus par l'image postgres
  ET par Django (settings `base.py`).

## Notes sécurité

- **TLS terminé par Traefik**, Django reçoit du clair depuis nginx. D'où
  `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` dans
  `config/settings/prod.py` — sans lui, Django se croit en HTTP et génère des
  URLs absolues en `http://`. nginx relaie l'en-tête posé par Traefik au lieu de
  l'écraser avec `$scheme` (`map $http_x_forwarded_proto` dans `nginx.conf`).
- **Cookies `Secure` activés** (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`).
- `SECURE_SSL_REDIRECT` reste **False** : le router n'écoute que `websecure`,
  rien n'arrive en clair, et cela évite toute boucle de redirection si l'en-tête
  ci-dessus venait à manquer.
- **HSTS à 0**, volontairement : le certificat couvre tout
  `*.sternum-lab.duckdns.org`, l'activer engagerait les autres services du
  homelab sans retour arrière possible côté navigateur.
- Auth désactivée (AllowAny). À réactiver (JWT) en phase de durcissement.
- `seed_demo` ne doit **jamais** être lancé en prod (données métier de démo).
