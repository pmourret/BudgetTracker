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

> ⚠️ **L'API est fermée depuis le durcissement d'août 2026** (JWT, `CLAUDE.md`
> §5). Ce document a longtemps dit l'inverse — « auth désactivée, dette assumée
> pour cette Alpha » — et c'était faux depuis le durcissement. Conséquence
> concrète : un déploiement mené d'après l'ancienne version montait une pile
> dans laquelle **personne ne pouvait entrer**, faute d'avoir créé un compte
> (étape 5 ci-dessous). Corrigé le 2026-08-10.
>
> Aucune donnée métier de démo : l'appli démarre vierge, seuls les
> **référentiels structurels** sont créés (commande `seed_referentiels`,
> idempotente, lancée par l'entrypoint).

## Séquence de déploiement

```bash
# 1. Créer les dossiers de bind-mount
sudo mkdir -p /var/lib/docker/hiatus/budgets/pgdata
sudo mkdir -p /var/lib/docker/hiatus/budgets/static

# 2. Vérifier que les réseaux externes existent (les réutiliser, ne pas les créer)
docker network ls | grep -E "proxy|backend"

# 3. Créer .env.prod à partir de .env.prod.example (secrets réels)
#    ⚠️ SECRET_KEY : depuis le durcissement, elle SIGNE TOUS LES JETONS. Le
#    contrôle `core.E001/E002` (backend/core/checks.py) refuse de démarrer hors
#    DEBUG si elle est la clé de repli du dépôt ou fait moins de 32 octets.
#    Elle se génère SUR LE SERVEUR et ne transite par aucun canal :
#    docker compose -f docker-compose.prod.yml run --rm backend \
#      python -c "import secrets; print(secrets.token_urlsafe(48))"
#
#    ⚠️ Poser aussi IDENTITE_FOYER (UUID du foyer de CETTE instance). Vide,
#    aucun jeton de l'annuaire n'est accepté ; faux, la connexion réussit puis
#    TOUT retombe en 401 (piège vécu, cf. .env.prod.example).
#    La clé PUBLIQUE de l'annuaire arrive par FICHIER monté, jamais en variable.

# 4. Build + up
#    ⚠️ `--force-recreate` : Traefik lit les labels sur le CONTENEUR EN COURS,
#    pas dans le fichier compose. Modifier le compose puis faire un simple
#    `restart` laisse l'ancien routage actif (piège vécu lors de la migration).
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d --force-recreate
docker compose -f docker-compose.prod.yml logs -f backend

# 5. Créer un compte — SANS LUI, PERSONNE NE PEUT ENTRER.
#    L'API est fermée (JWT) : il n'y a aucune inscription dans l'interface, et
#    l'écran de connexion est la seule surface accessible sans jeton.
#    Idempotente : relancée, elle repose le mot de passe. C'est la porte de
#    secours si l'annuaire est éteint ou si un mot de passe est perdu.
docker compose -f docker-compose.prod.yml exec backend \
  python manage.py creer_utilisateur --nom pierre --email … --mot-de-passe … --admin

#    ⚠️ Sous IDENTITE_AUTORITE=True, ce compte local n'obtient PLUS de jeton par
#    /auth/token/ (la connexion est relayée à l'annuaire). Il reste la porte de
#    secours par /admin/ (session Django locale) : ne pas le supprimer.

# 6. Vérifier que la pile est bien fermée (doit répondre 401, jamais 200)
curl -s -o /dev/null -w "%{http_code}\n" \
  https://budgets.sternum-lab.duckdns.org/api/v1/comptes/

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
- `DJANGO_SECRET_KEY` — secret réel, jamais committé, **≥ 32 octets** : le
  contrôle au démarrage refuse de servir en dessous (voir Notes sécurité).
- `IDENTITE_AUTORITE` / `IDENTITE_URL` / `IDENTITE_CLE_PUBLIQUE_FICHIER` /
  `IDENTITE_FOYER` — service d'identité partagé. `IDENTITE_FOYER` désigne le
  foyer de **cette** instance (une instance par foyer) : c'est la seule chose
  qui refuse un membre du foyer voisin.
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
- **API fermée par défaut** (JWT, août 2026). La dérogation `AllowAny` vivait
  dans `dev.py` **et avait été recopiée dans `prod.py`** : le défaut est
  désormais fermé dans `base.py`, et aucun fichier d'environnement n'y déroge.
  ⚠️ **Ne jamais reposer une exception d'authentification dans un fichier
  d'environnement** — c'est le mécanisme qui a produit le trou, pas l'étourderie.
- **`SECRET_KEY` signe les jetons.** `core/checks.py` la contrôle au démarrage
  et **bloque hors DEBUG** (`core.E001` clé de repli du dépôt, `core.E002`
  moins de 32 octets). La renouveler déconnecte toutes les sessions en cours —
  c'est le comportement voulu.
- **La vérification des jetons de l'annuaire est locale** (RS256, clé publique
  lue au démarrage) : BudgetTracker continue de fonctionner annuaire éteint.
  Seule l'**émission** est relayée.
- `seed_demo` ne doit **jamais** être lancé en prod (données métier de démo).
