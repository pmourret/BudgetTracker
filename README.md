# BudgetFamilial

Application web de suivi budgétaire familial — transformation d'un classeur Excel en outil robuste, maintenable et évolutif.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Django](https://img.shields.io/badge/Django-6.0-green?logo=django)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?logo=docker)

---

## Sommaire

- [Aperçu](#aperçu)
- [Fonctionnalités](#fonctionnalités)
- [Stack technique](#stack-technique)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation et démarrage](#installation-et-démarrage)
- [Configuration](#configuration)
- [Pages et routes](#pages-et-routes)
- [API REST](#api-rest)
- [Structure du projet](#structure-du-projet)
- [Commandes utiles](#commandes-utiles)
- [Déploiement et Makefile](#déploiement-et-makefile)
- [Règles métier clés](#règles-métier-clés)
- [Roadmap](#roadmap)

---

## Aperçu

BudgetFamilial remplace un classeur Excel de suivi budgétaire par une application web full-stack :

- **Journal de flux** signé (revenus/dépenses/transferts) avec recalcul automatique des soldes
- **Catégories hiérarchiques** (majeures → mineures) avec agrégation budgétaire configurable
- **Suivi du patrimoine** estimatif (actifs financiers et immobiliers) isolé des soldes bancaires
- **Dashboard** avec courbe de solde, dépenses par catégorie, alertes et bloc patrimoine
- **Dark mode** complet avec persistance de la préférence utilisateur

L'application tourne entièrement dans Docker Compose (backend Django, frontend React, base PostgreSQL) et est opérationnelle en une seule commande.

---

## Fonctionnalités

### Gestion financière

| Fonctionnalité | Détail |
|---|---|
| **Comptes bancaires** | CRUD complet, solde théorique calculé automatiquement, réconciliation avec flux d'ajustement, indicateur **compte commun** (badge dédié) |
| **Flux** | Journal central signé (−dépense / +revenu), soft delete, recalcul de solde par signal |
| **Transferts** | Virements entre comptes (ex. alimenter un compte d'épargne) créables depuis l'UI : paire débit/crédit atomique, jamais comptés dans les dépenses/revenus |
| **Budgets** | Par catégorie et par mois, taux de consommation calculé en temps réel |
| **Abonnements** | Récurrents avec détection de divergence de montant |
| **Catégories** | Hiérarchie 2 niveaux (majeure / mineure), soft delete protégé si flux liés |
| **Patrimoine** | Actifs estimatifs avec historique de valorisation, rappels de réévaluation |
| **Alertes** | Budget dépassé, solde bas, retard abonnement, écart de solde, valorisation à faire |

### Dashboard

- Métriques clés du mois (revenus, dépenses, solde, épargne)
- Courbe de solde sur 3 / 6 / 12 mois
- Doughnut « Dépenses par catégorie » avec légende expandable (majeures/mineures)
- Progression des budgets du mois
- Derniers flux et alertes actives
- Bloc patrimoine estimatif séparé (jamais mélangé aux soldes)

### Interface

- Dark mode / Light mode / Système (persisté en `localStorage`)
- Responsive : sidebar desktop + bottom navigation mobile
- Composants UI réutilisables (`Button`, `Card`, `Input`, `Select`, `Modal`, `Badge`, `IconBadge`)
- Sélecteurs de catégories groupés (`<optgroup>` majeures → mineures)
- Création inline de titulaires et établissements depuis les modals

---

## Stack technique

### Backend

| Composant | Version |
|---|---|
| Python | 3.12 |
| Django | 6.0.6 |
| Django REST Framework | 3.15 |
| django-filter | 24.3 |
| psycopg2-binary | 2.9.9 |
| python-decouple | 3.8 |
| python-dateutil | 2.9 |

### Frontend

| Composant | Version |
|---|---|
| React | 18.3 |
| Vite | 5.4 |
| TanStack Query | 5.56 |
| Zustand | 4.5 |
| Tailwind CSS | 4.3 (via `@tailwindcss/vite`) |
| chart.js + react-chartjs-2 | 4.5 / 5.3 |
| lucide-react | 1.17 |
| axios | 1.7 |
| react-router-dom | 6.26 |

### Infrastructure

| Composant | Version |
|---|---|
| PostgreSQL | 16 (Alpine) |
| Docker Compose | v2 |
| Node.js (conteneur) | 20 (Alpine) |

---

## Architecture

### Services Docker

```
┌─────────────────────────────────────────────────────┐
│                   Docker Compose                    │
│                                                     │
│  ┌───────────┐   ┌───────────┐   ┌───────────────┐ │
│  │ frontend  │   │  backend  │   │      db       │ │
│  │ React+Vite│──▶│  Django   │──▶│ PostgreSQL 16 │ │
│  │ :5173     │   │ DRF :8000 │   │    :5432      │ │
│  └───────────┘   └───────────┘   └───────────────┘ │
│                                                     │
│  Volume : postgres_data (données persistées)        │
└─────────────────────────────────────────────────────┘
```

### Apps Django (16)

```
core           → BaseModel abstrait (UUID, soft delete, timestamps)
referentiels   → Tables administrables (types, établissements, titulaires…)
comptes        → Comptes bancaires + calcul de solde
categories     → Hiérarchie 2 niveaux (majeure / mineure)
flux           → Journal central des mouvements
transferts     → Paire débit/crédit atomique
budgets        → Suivi budgétaire par catégorie/mois
abonnements    → Récurrents + détection divergence
alertes        → Alertes automatiques + acquittement
patrimoine     → Actifs estimatifs + historique valorisation
analytics      → Dashboard (agrégats, dépenses par catégorie)
objectifs      → Objectifs d'épargne (prévu phase ultérieure)
market_data    → Données de marché isolées (prévu)
imports        → Import CSV bancaire (prévu)
audit          → Piste d'audit (prévu)
accounts       → Authentification utilisateur (prévu)
```

### Principes d'architecture

- **Couche `services/`** : toute la logique métier vit là, jamais dans les views ni serializers
- **`BaseModel`** : UUID en PK, `created_at`, `updated_at`, soft delete (`is_deleted` + manager filtré)
- **Flux signé** : `−215` = dépense, `+2800` = revenu
- **Solde théorique** = `solde_initial + Σ(flux du compte)` — calculé backend, jamais éditable
- **Transferts exclus** de tous les agrégats (flag `est_transfert` + modèle dédié)
- **Soft delete global** : aucune suppression physique de donnée financière historique
- **Patrimoine isolé** : jamais mélangé aux soldes bancaires dans les agrégats

---

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (avec Docker Compose v2)
- Git

> Aucune installation locale de Python, Node.js ou PostgreSQL n'est nécessaire.

---

## Installation et démarrage

### 1. Cloner le dépôt

```bash
git clone https://github.com/<votre-compte>/BudgetTracker.git
cd BudgetTracker
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
```

Éditer `.env` si nécessaire (voir [Configuration](#configuration)). Les valeurs par défaut fonctionnent pour le développement local.

### 3. Lancer les conteneurs

```bash
docker compose up -d
```

Au premier démarrage, Docker construit les images, installe les dépendances Python et Node, et attend que PostgreSQL soit prêt.

### 4. Appliquer les migrations

```bash
docker compose exec backend python manage.py migrate
```

### 5. (Optionnel) Charger des données de démonstration

```bash
docker compose exec backend python manage.py seed_demo
```

La commande est **idempotente** : elle peut être relancée sans créer de doublons. Elle est réservée au **développement** : elle crée un compte et des catégories de démonstration et **refuse de s'exécuter si `DEBUG=False`** (prod). En production, seuls les référentiels structurels sont chargés (`seed_referentiels`), l'application démarre vierge de données métier.

### 6. Accéder à l'application

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API REST | http://localhost:8000/api/v1/ |
| Admin Django | http://localhost:8000/admin/ |

---

## Configuration

Copier `.env.example` en `.env` et ajuster les valeurs :

```env
# Django
SECRET_KEY=change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,backend
DJANGO_SETTINGS_MODULE=config.settings.dev

# PostgreSQL
DB_NAME=budgetfamilial
DB_USER=budget
DB_PASSWORD=budget
DB_HOST=db
DB_PORT=5432

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

> **Production** : changer `SECRET_KEY`, passer `DEBUG=False`, restreindre `ALLOWED_HOSTS`, et utiliser `config.settings.prod`.

---

## Pages et routes

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` → redirige `/dashboard` | Métriques, courbe solde, dépenses par catégorie, budgets, alertes, patrimoine |
| Comptes | `/comptes` | CRUD comptes bancaires, réconciliation de solde |
| Flux | `/flux` | Journal des mouvements, filtres, badges ajustement |
| Transferts | `/transferts` | Virements entre comptes (ex. courant → épargne), création + annulation |
| Budgets | `/budgets` | Suivi budgétaire par catégorie/mois |
| Abonnements | `/abonnements` | Récurrents, toggle actif, détection divergence |
| Alertes | `/alertes` | Filtres par type, acquittement individuel et global |
| Patrimoine | `/patrimoine` | Actifs estimatifs, historique de valorisation |
| Catégories | `/categories` | Accordéon majeures/mineures, CRUD complet |
| Plus (mobile) | `/plus` | Menu mobile + toggle thème |

---

## API REST

Base URL : `http://localhost:8000/api/v1/`

### Ressources principales (CRUD complet)

```
GET|POST        /comptes/
GET|PUT|PATCH|DELETE  /comptes/{id}/
POST            /comptes/{id}/reconcilier/

GET|POST        /flux/
GET|PUT|PATCH|DELETE  /flux/{id}/

GET|POST        /transferts/
GET|PUT|PATCH|DELETE  /transferts/{id}/

GET|POST        /budgets/
GET|PUT|PATCH|DELETE  /budgets/{id}/

GET|POST        /abonnements/
GET|PUT|PATCH|DELETE  /abonnements/{id}/
GET             /abonnements/{id}/verifier-divergence/

GET|POST        /alertes/
GET|PUT|PATCH   /alertes/{id}/
POST            /alertes/{id}/acquitter/
POST            /alertes/acquitter-tout/

GET|POST        /patrimoine/
GET|PUT|PATCH|DELETE  /patrimoine/{id}/
POST            /patrimoine/{id}/valoriser/
GET             /patrimoine/total/
GET             /patrimoine/historique/?nb_mois=12
POST            /patrimoine/verifier-rappels/

GET|POST        /categories/
GET|PUT|PATCH|DELETE  /categories/{id}/
```

### Référentiels (lecture seule, sauf Titulaires et Établissements)

```
GET             /referentiels/types-compte/
GET             /referentiels/types-flux/
GET             /referentiels/periodicites/
GET|POST        /referentiels/titulaires/
GET|PUT|PATCH   /referentiels/titulaires/{id}/
GET|POST        /referentiels/etablissements/
GET|PUT|PATCH   /referentiels/etablissements/{id}/
```

### Analytics

```
GET             /analytics/dashboard/?nb_mois=6
```

### Pagination

Les listes sont paginées (`PageNumberPagination`, 50 résultats par page par défaut). Le client peut demander une page plus grande via `?page_size=N`, plafonnée à `max_page_size=1000` (classe `core.pagination.StandardPagination`) :

```
GET             /categories/?page_size=1000    # tout le référentiel en une page
```

> Utile pour les référentiels à volume borné consommés en entier par l'UI (catégories : accordéon majeures/mineures, `<optgroup>` des selects). Sans le paramètre, le comportement par défaut (50/page) reste inchangé pour tous les endpoints. Côté frontend, le hook dédié `useCategories()` ajoute automatiquement `?page_size=1000`.

---

## Structure du projet

```
BudgetTracker/
├── backend/
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py        # Paramètres communs
│   │   │   ├── dev.py         # Développement (auth désactivée)
│   │   │   └── prod.py        # Production
│   │   └── urls.py            # Router centralisé
│   ├── core/                  # BaseModel abstrait
│   ├── referentiels/          # Tables administrables
│   ├── comptes/               # Comptes bancaires
│   ├── categories/            # Hiérarchie catégories
│   ├── flux/                  # Journal des mouvements
│   ├── transferts/            # Transferts inter-comptes
│   ├── budgets/               # Suivi budgétaire
│   ├── abonnements/           # Abonnements récurrents
│   ├── alertes/               # Alertes automatiques
│   ├── patrimoine/            # Actifs estimatifs
│   ├── analytics/             # Dashboard et agrégats
│   ├── objectifs/             # (prévu)
│   ├── market_data/           # (prévu)
│   ├── imports/               # (prévu)
│   ├── audit/                 # (prévu)
│   ├── accounts/              # (prévu)
│   ├── manage.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/            # Button, Card, Input, Select, Modal, Badge…
│   │   │   ├── layout/        # Layout, Sidebar, BottomNav, ThemeToggle
│   │   │   ├── charts/        # LineChart, BarChart, DoughnutChart
│   │   │   ├── comptes/       # CompteFormModal, SelectWithCreate
│   │   │   └── categories/    # CategorieFormModal
│   │   ├── hooks/
│   │   │   ├── useResource.js      # CRUD + invalidations croisées
│   │   │   ├── useReferentiels.js  # Référentiels (lecture + création)
│   │   │   └── useMediaQuery.js    # Responsive (breakpoint 640px)
│   │   ├── pages/             # Une page par route
│   │   ├── stores/
│   │   │   └── themeStore.js  # Zustand : dark/light/system
│   │   ├── api/               # Configuration axios
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
│
├── docker-compose.yml         # Stack de développement
├── docker-compose.prod.yml    # Stack de production (Nginx + Traefik)
├── Makefile                   # Cibles dev/prod (up, deploy, migrate, seed…)
├── .env.example
├── .gitignore
├── CLAUDE.md                  # Instructions pour Claude Code
└── README.md
```

---

## Commandes utiles

### Cycle de vie des conteneurs

```bash
# Démarrer en arrière-plan
docker compose up -d

# Arrêter
docker compose down

# Arrêter et supprimer les volumes (reset complet)
docker compose down -v
```

### Backend Django

```bash
# Vérifier la configuration
docker compose exec backend python manage.py check

# Migrations après modification d'un modèle
docker compose exec backend python manage.py makemigrations <app>
docker compose exec backend python manage.py migrate

# Tests
docker compose exec backend python manage.py test            # tous
docker compose exec backend python manage.py test analytics  # une app

# Données de démonstration (dev uniquement — voir aussi `make dev-seed`)
docker compose exec backend python manage.py seed_demo

# Référentiels structurels seuls (sûr en prod, idempotent)
docker compose exec backend python manage.py seed_referentiels

# Shell Django
docker compose exec backend python manage.py shell
```

### Frontend

```bash
# Installer un nouveau paquet
docker compose exec frontend npm install <paquet>

# Vérifier qu'un paquet est bien dans package.json
grep "<paquet>" frontend/package.json
```

### Logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db
```

---

## Déploiement et Makefile

Un `Makefile` (à la racine) encapsule les commandes Docker Compose pour les deux environnements. Il s'appuie sur deux fichiers compose distincts :

| Environnement | Fichier compose | Fichier d'env | Frontend |
|---|---|---|---|
| **Développement** | `docker-compose.yml` | `.env` | Vite en HMR (`npm run dev`, `:5173`) |
| **Production** | `docker-compose.prod.yml` | `.env.prod` | build statique servi par Nginx, exposé via Traefik |

> Les cibles **par défaut** (`up`, `migrate`, `seed`, `deploy`…) visent la **production**. Les cibles de développement sont préfixées par `dev-`.

```bash
make            # ou : make help — affiche toutes les cibles disponibles
```

### Production

| Cible | Action |
|---|---|
| `make up` / `make down` | Démarre / arrête la stack prod (les volumes sont conservés) |
| `make build` / `make rebuild` | Rebuild des images (`rebuild` = sans cache puis `up`) |
| `make migrate` | Applique les migrations |
| `make seed` | Charge les **référentiels structurels** (idempotent, **pas** de données de démo) |
| `make check` | `manage.py check` |
| `make test [app=...]` | Lance les tests (ciblables : `make test app=analytics`) |
| `make logs` / `make logs-backend` / `make logs-db` | Suit les logs |
| `make shell` / `make bash` | Shell Django / bash dans le conteneur backend |
| `make superuser` | Crée un superutilisateur Django |
| `make init` | Première mise en route : `up` + `migrate` + `seed_referentiels` (vierge de données métier) |
| `make backup` | Dump SQL horodaté de la base dans `./backups/` |
| `make restore file=backups/xxx.sql` | Restaure un dump |
| `make reset-db` | ⚠️ **DÉTRUIT** le volume `pgdata` puis réinitialise — demande une confirmation explicite (`CONFIRMER`) |

### Mise à jour de la production

```bash
make deploy        # backup → git pull → build → up → migrate → collectstatic → check
make deploy-front  # rebuild + redéploiement du frontend uniquement
```

`make deploy` effectue un **backup automatique** avant toute migration. Les migrations de schéma sont appliquées automatiquement.

### Développement

| Cible | Action |
|---|---|
| `make dev-up` / `make dev-down` | Démarre / arrête la stack de dev |
| `make dev-logs` | Suit les logs de la stack de dev |
| `make dev-seed` | Charge les **données de démonstration** (compte + catégories) — **dev uniquement** |

> **Garde-fous de sécurité.** `seed_demo` refuse de s'exécuter hors `DEBUG` (donc en prod) — utiliser `make dev-seed` en local. `make reset-db` exige une confirmation avant de détruire les données. En prod, `make init` / `make seed` ne chargent que les référentiels structurels, jamais de données de démo.

---

## Règles métier clés

| Règle | Description |
|---|---|
| **Flux signé** | `−215` = dépense, `+2800` = revenu. Le signe fait foi, pas un type. |
| **Solde théorique** | `solde_initial + Σ(flux du compte)` — calculé backend uniquement, jamais éditable. |
| **Écart de solde** | `solde_réel − solde_théorique` — réconciliation via flux d'ajustement. |
| **Transferts exclus** | Jamais confondus avec des dépenses/revenus dans les agrégats. |
| **Soft delete** | Aucune suppression physique de donnée financière historique. |
| **Patrimoine isolé** | Les données de valorisation n'affectent jamais les soldes bancaires. |
| **Référentiels** | Pas de valeur codée en dur : seuils, types, périodicités → tables administrables. |
| **Mois calculé** | Toujours dérivé de `date_flux` (1er du mois), jamais saisi manuellement. |

---

## Roadmap

### Terminé ✅

- **Phase 1–8** — Backend complet (16 apps, modèles, services, API REST)
- **Phase 9** — Frontend complet (8 pages, CRUD, dark mode, composants UI)
- **Phase 11a** — CRUD Comptes, Flux, Budgets, Patrimoine
- **Phase 11b-1** — Catégories hiérarchiques (UI + API)

### En cours 🟡

- **Phase 11b-2** — Budgets intelligents (budget majeur = agrégat des mineures cochées)
- **Phase 11c** — Budgets répétables (champ `est_recurrent` + génération mensuelle)

### Prévu ⏳

- **Phase 10** — Prévisionnel financier (solde projeté, trajectoire d'épargne, simulations)
- **Phase 12** — Budgets dynamiques (règles de calcul basées sur les revenus ou l'historique)
- **Objectifs** — Suivi d'objectifs d'épargne
- **Import CSV** — Migration Excel + import bancaire
- **Market data** — Valorisation estimative des actifs financiers (cours en temps réel)
- **Durcissement** — Authentification JWT, permissions multi-foyer, audit, tests de charge

---

## Note sur l'authentification

En développement (mode MVP), l'authentification est **désactivée** (`DEFAULT_AUTHENTICATION_CLASSES: []` dans `dev.py`). L'API est accessible sans token.

L'authentification JWT sera réactivée en phase de durcissement. Ne pas exposer l'application en production sans avoir configuré `prod.py` et sécurisé les variables d'environnement.
