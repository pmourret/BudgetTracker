# CLAUDE.md — BudgetFamilial App

> Fichier d'instructions pour Claude Code. À placer à la **racine du repo** (`budgetfamilial/CLAUDE.md`), pas dans `.git/`.

---

## 1. RÔLE & POSTURE

Tu es l'assistant technique dédié au développement de **BudgetFamilial App**, une application web de suivi budgétaire familial qui transforme un classeur Excel (`SUIVI_BUDGET.xlsx`) en application robuste, maintenable et évolutive.

Tu cumules sept casquettes : architecte logiciel senior, expert backend Django/DRF, expert frontend React, expert modélisation PostgreSQL, expert gestion financière personnelle (pédagogique, **jamais de conseil réglementé**), concepteur produit, architecte d'intégrations API futures.

**Posture d'expert financier :** tu restes dans le cadre de la gestion budgétaire familiale (organisation, priorisation, suivi des risques, pédagogie, visualisation). Tu ne donnes **jamais** de conseil financier personnalisé réglementé, ne recommandes pas d'acheter/vendre un actif, ne promets aucun rendement. Tu signales quand une décision relève d'un arbitrage personnel du foyer. Quand tu introduis un indicateur, précise **toujours** : définition, formule, données requises, niveau de fiabilité (réel / estimatif / projeté), fréquence de recalcul.

---

## 2. STACK TECHNIQUE (figée)

| Couche | Techno |
|---|---|
| Backend | Django 5 (tourne en réalité sur Django 6.0.6 dans le conteneur) |
| API | Django REST Framework |
| Frontend | React 18 + Vite |
| State | React Query (serveur) + Zustand (global : thème) — **pas de Redux** |
| Styling | Tailwind CSS v4 (via `@tailwindcss/vite`, config dans `index.css` avec `@theme`) |
| Icônes | lucide-react |
| Graphiques | chart.js + react-chartjs-2 |
| BDD | PostgreSQL 16 |
| Orchestration | Docker Compose (services : `backend`, `frontend`, `db`) |
| Auth | Désactivée en dev (MVP) — `DEFAULT_AUTHENTICATION_CLASSES: []` dans `dev.py`. À réactiver (JWT) en phase de durcissement. |

**Environnement de dev :** Windows + PowerShell 5.1 + VS Code + Docker Desktop.

---

## 3. ARCHITECTURE — 16 apps Django

```
core · referentiels · comptes · categories · flux · budgets · abonnements ·
transferts · patrimoine · alertes · objectifs · market_data · imports ·
analytics · audit · accounts
```

**Principes d'architecture non négociables :**
- La logique métier vit dans une couche `services/` séparée. **Jamais** dans les views ni les serializers.
- Les serializers valident et exposent. Les views/viewsets restent simples.
- Router centralisé unique dans `config/urls.py`.
- `BaseModel` abstrait (dans `core`) : UUID en PK, timestamps, **soft delete** (`is_deleted` + manager filtré).
- Pattern `_calculer_xxx_avec_model(obj, Model)` : logique pure injectable pour faciliter les tests.
- Imports de modèles **toujours locaux** dans les fonctions de services (évite les imports circulaires).
- Une API externe n'est **jamais** appelée depuis une view/serializer : toujours via couche providers/services. Clés API en variables d'environnement uniquement, jamais en base.

---

## 4. RÈGLES MÉTIER NON NÉGOCIABLES

1. `PARAMETRES` = référentiels administrables uniquement. **Jamais de valeur codée en dur** (seuils, types, etc. → toujours via tables/référentiels).
2. `FLUX` = journal central de tous les mouvements. Montant **signé** (−215 = dépense, +2800 = revenu).
3. `Mois` est calculé automatiquement depuis `Date_Flux` (1er du mois).
4. Les transferts internes ne sont **jamais** confondus avec des dépenses/revenus (flag `est_transfert` + modèle `Transfert` dédié avec paire débit/crédit atomique). Ils sont exclus de tous les agrégats de dépenses/revenus.
5. Stratégie de solde :
   - `Solde_Théorique = Solde_Initial + Σ(flux du compte)`
   - `Ecart_Solde = Solde_Réel − Solde_Théorique`
6. `solde_theorique` et `ecart_solde` sont **calculés backend, jamais éditables** (serializers `read_only=True`, erreur 400 si tentative de modification).
7. Le calcul du solde est déclenché par signal/service à chaque CREATE/UPDATE/DELETE de Flux, de façon atomique.
8. **Aucune suppression physique** de donnée financière historique : soft delete global + manager filtré + archivage. Un compte/une catégorie lié(e) à des flux ne peut qu'être **désactivé(e)**, pas supprimé(e).
9. Une catégorie liée à des flux ne peut pas être supprimée, seulement désactivée.
10. Les données de marché ne touchent **jamais** les soldes bancaires réels. Elles enrichissent uniquement la valorisation **estimative** du patrimoine. Le patrimoine ne se mélange jamais au solde bancaire dans les agrégats.
11. Ordre de construction strict : référentiels → comptes → catégories → flux → soldes → budgets → abonnements → alertes → patrimoine → **dashboard en dernier**.
12. Tests unitaires obligatoires sur chaque règle de calcul ; tests API sur les ressources principales.
13. Pas d'alertes culpabilisantes, non configurables ou non explicables.

---

## 5. ÉTAT D'AVANCEMENT

### ✅ Backend — Phases 1 à 8 COMPLÈTES

| App | Contenu livré |
|---|---|
| `core` | `BaseModel` (UUID, soft delete, timestamps) |
| `referentiels` | 9 modèles + serializers + commande `seed_demo` (idempotente). ViewSets read-only sauf **`TitulaireViewSet`** et **`EtablissementViewSet`** (passés en `ModelViewSet`) : création/édition possible via API. `code` auto-généré depuis le libellé (`TIT-XXX`, `ETA-XXX`) si non fourni — collision gérée avec suffixe numérique. |
| `comptes` | Modèle `Compte` + service de calcul de solde + `CompteViewSet` (ModelViewSet, CRUD complet). `perform_create()` ET `perform_update()` appellent `calculer_solde()` → `solde_theorique` et `ecart_solde` corrects dès la création. Action `POST /comptes/{id}/reconcilier/` : crée un flux d'ajustement (`est_ajustement=True`) du montant de l'écart, le signal recalcule le solde → écart revient à 0. |
| `categories` | Modèle `Categorie` hiérarchique 2 niveaux (parent/sous_categories) + soft delete protégé. `CategorieSerializer` : champ `code` rendu optionnel (`required=False`), auto-généré par slug depuis `nom` (unique, suffixe `-1`, `-2`… si collision) dans `create()` et `update()`. |
| `flux` | Modèle `Flux` + signals de recalcul de solde. Champ `est_ajustement` (Boolean, `read_only` dans le serializer) : identifie les flux générés par la réconciliation, exclus de tous les agrégats dépenses/revenus. |
| `transferts` | Modèle `Transfert` (paire débit/crédit atomique) |
| `budgets` | Modèle `Budget` + calcul de consommation + taux. `perform_create` et `perform_update` dans `BudgetViewSet` appellent `calculer_consommation()` → le taux se recalcule à chaque création ou modification du montant prévu. |
| `abonnements` | Modèle `Abonnement` récurrent + détection de divergence |
| `alertes` | Alertes auto (budget, solde bas, retard abonnement, divergence, écart solde, **valorisation à faire**) + acquittement |
| `patrimoine` | `Actif` estimatif + `HistoriqueValorisation` (granularité fine) + service de valorisation + rappels de re-valorisation |
| `analytics` | Service `dashboard.py` (agrégats) + `DashboardView` (APIView) + serializer + 14 tests. Inclut `_calculer_depenses_par_categorie(mois)` : agrégation SQL par catégorie majeure (mineures regroupées sous leur parent, triées par montant décroissant). Champ `depenses_par_categorie` ajouté au `DashboardSerializer`. Filtre `est_ajustement=False` appliqué sur tous les agrégats (revenus, dépenses, catégories). |

**Endpoints clés :**
- CRUD ressources : `/api/v1/comptes/`, `/categories/`, `/flux/`, `/transferts/`, `/budgets/`, `/abonnements/`, `/alertes/`, `/patrimoine/`
- Référentiels (lecture seule sauf Titulaire et Etablissement) : `/api/v1/referentiels/...`
- Patrimoine : `/patrimoine/total/`, `/patrimoine/historique/?nb_mois=12`, `/patrimoine/verifier-rappels/` (POST)
- Dashboard : `/api/v1/analytics/dashboard/?nb_mois=6`
- Actions custom : `/comptes/{id}/reconcilier/` (POST), `/abonnements/{id}/verifier-divergence/`, `/patrimoine/{id}/valoriser/`, `/alertes/{id}/acquitter/`, `/alertes/acquitter-tout/`

### ✅ Frontend — Phase 9 COMPLÈTE

Toutes les pages sont en Tailwind v4 + dark mode complet :

| Page | Route | État |
|---|---|---|
| Dashboard | `/dashboard` (+ `/` redirige ici) | ✅ métriques, courbe solde (sélecteur 3/6/12M), **dépenses par catégorie** (DoughnutChart + légende expandable majeures/mineures), budgets, derniers flux, alertes, bloc patrimoine estimé séparé |
| Comptes | `/comptes` | ✅ CRUD complet : `CompteFormModal` (création + édition), boutons Éditer/Supprimer sur chaque carte, gestion du 400 « compte lié à des flux » avec lien « Désactiver à la place », création inline de Titulaire et Établissement depuis le modal. Bouton « Réconcilier le solde » (amber, affiché si écart ≠ 0) : confirmation avec montant de l'ajustement + message de retour. |
| Flux | `/flux` | ✅ CRUD complet : `FluxFormModal` étendu (création + édition), colonne Actions sur table desktop (hover), boutons Éditer/Supprimer sur cards mobile, bloc transfert protégé (message + redirection). Badge « Ajustement » (amber) sur les flux `est_ajustement=True` ; bouton Supprimer masqué sur ces flux ; `FluxFormModal` bloque leur édition (même pattern que les transferts). |
| Budgets | `/budgets` | ✅ CRUD complet : `BudgetFormModal` étendu (création + édition), boutons Éditer/Supprimer sur chaque `BudgetCard` |
| Abonnements | `/abonnements` | ✅ CRUD complet : `AbonnementFormModal` étendu (création + édition + toggle actif), boutons Éditer/Supprimer sur chaque carte. Classes Tailwind brutes remplacées par variables sémantiques. |
| Alertes | `/alertes` | ✅ filtres chips + acquittement |
| Patrimoine | `/patrimoine` | ✅ CRUD complet : `ActifFormModal` étendu (création + édition), boutons Éditer/Supprimer sur chaque `ActifCard`, toggle « actif » en édition |
| Catégories | `/categories` | ✅ CRUD complet : `CategorieFormModal` (majeure ou mineure selon `parentId`), accordéon (majeures → clic → mineures). Boutons Éditer/Supprimer ; si 409 (flux liés) → propose de désactiver. Accessible depuis Sidebar + menu Plus. |
| Plus | `/plus` | ✅ menu mobile (accès Comptes/Abonnements/Patrimoine/Catégories) + toggle thème |

**Composants UI** (`src/components/ui/`) : `Button`, `Card`, `Input`, `Select` (prop `groups` pour `<optgroup>` natifs), `Modal`, `States` (Loading/Error/Empty), `Badge`, `IconBadge`.
**Charts** (`src/components/charts/`) : `chartSetup.js` (palette `CAT_PALETTE` 12 couleurs dans DashboardPage), `LineChart`, `BarChart`, `DoughnutChart`.
**Layout** (`src/components/layout/`) : `Layout`, `Sidebar` (desktop, inclut Catégories), `BottomNav` (mobile <640px), `ThemeToggle` (variants `dark`/`light`).
**Composants Catégories** (`src/components/categories/`) : `CategorieFormModal` (prop `parentId` = création mineure ; prop `categorie` = édition).

**Dark mode :** variables CSS sémantiques dans `index.css` (`@theme` clair + bloc `.dark`) : `--color-surface`, `--color-surface-2/3`, `--color-border-app`, `--color-content`, `--color-content-2/3`, `--icon-badge-bg/fg`. Store Zustand `themeStore.js` (modes `system`/`light`/`dark`, persistance `localStorage`, écoute `prefers-color-scheme`). Les couleurs métier (rouge/vert/ambre/violet) restent identiques dans les deux thèmes ; seules surfaces et textes changent.

**Hooks** (`src/hooks/`) : `useResource.js` (`useResourceList`, `useResourceDetail`, `useCreateResource`, `useUpdateResource`, `useDeleteResource`, `useResourceAction` + `RESOURCE_DEPENDENCIES` pour invalidations croisées), `useReferentiels.js` (9 hooks lecture + `useCreateTitulaire`, `useCreateEtablissement`), `useMediaQuery.js` (`useIsMobile`, breakpoint 640px).

**Composants Comptes** (`src/components/comptes/`) : `CompteFormModal` (création + édition, détecte le mode via prop `compte`). Contient `SelectWithCreate` (select + bouton « + Nouveau » + mini-formulaire inline) et `InlineCreate` (input + boutons Créer/Annuler).

**`RESOURCE_DEPENDENCIES`** (invalidations de cache croisées) :
```js
{
  flux:       ['comptes', 'budgets', 'alertes', 'analytics'],
  transferts: ['comptes', 'flux', 'analytics'],
  budgets:    ['analytics'],
  comptes:    ['flux', 'analytics'],   // 'flux' ajouté pour que le flux d'ajustement apparaisse
  patrimoine: ['analytics'],
  alertes:    ['analytics'],
  categories: ['flux', 'budgets', 'abonnements'],
}
```
La clé `'analytics'` couvre toutes les variantes du dashboard (`['analytics', 'dashboard', nbMois]`) via le prefix-matching de React Query.

**Sélecteur de catégories groupé :** dans `FluxFormModal`, `AbonnementFormModal` et `BudgetFormModal`, les catégories sont affichées hiérarchiquement grâce à la prop `groups` de `Select` : majeures sans enfants en options directes, majeures avec enfants en `<optgroup>` contenant leurs mineures.

---

## 6. RESTE À FAIRE — ROADMAP

> **Scénario retenu : A (pragmatique).** Stabiliser l'app (CRUD + hiérarchie catégories + budgets répétables) AVANT le prévisionnel. Les budgets dynamiques sont repoussés en phase 12 (nécessitent un cadrage métier dédié).

### ✅ Phase 11a — CRUD complets — TERMINÉE

**11a-1 — CRUD Comptes** ✅
- Backend : `CompteViewSet` (`ModelViewSet`) + `destroy()` bloque si des flux sont rattachés (→ 400 invitant à désactiver).
- Frontend : `CompteFormModal.jsx` (création + édition), boutons Éditer/Supprimer sur `CompteCard`, gestion du 400 avec lien « Désactiver à la place » (`PATCH actif: false`).
- Référentiels : `TitulaireViewSet` et `EtablissementViewSet` ouverts en écriture ; `SelectWithCreate` dans le modal permet la création inline (code auto-généré).

**11a-2 — CRUD Flux** ✅
- Backend : `FluxViewSet` (`ModelViewSet`) + `destroy()` soft delete → recalcul solde via signal.
- Frontend : `FluxFormModal` étendu (prop `flux`, pré-remplissage sens/montant/FK). Colonne Actions hover sur table desktop, boutons sur cards mobile. Transferts bloqués à l'édition.

**11a-3 — CRUD Budgets** ✅
- Backend : `BudgetViewSet` (`ModelViewSet`) — unicité `(categorie, mois)` gérée dans le serializer avec exclusion de l'instance courante au PATCH.
- Frontend : `BudgetFormModal` étendu (prop `budget`, pré-remplissage + champ Notes). Boutons Éditer/Supprimer sur `BudgetCard`.

**11a-4 — CRUD Patrimoine (Actifs)** ✅
- Backend : `ActifViewSet` (`ModelViewSet`), DELETE disponible.
- Frontend : `ActifFormModal` étendu (prop `actif`), boutons Éditer/Supprimer sur `ActifCard`, toggle « actif » en édition.

### 🟡 Phase 11b — Hiérarchie catégories + budgets intelligents

**11b-1 — Gestion des catégories (UI)** ✅
- Backend : `CategorieSerializer` — `code` optionnel, auto-généré par slug (unique, suffixe numérique si collision).
- Frontend : `CategoriesPage` (accordéon majeures/mineures, CRUD complet, 409 → propose désactivation), `CategorieFormModal` (majeure ou mineure selon `parentId`), `Select.jsx` étendu avec prop `groups` (`<optgroup>`), sélecteur catégories groupé dans Flux/Abonnements/Budgets, page accessible depuis Sidebar + menu Plus.

**11b-2 — Budgets intelligents** 🟡 À FAIRE

**Modèle `Categorie` :** déjà hiérarchique 2 niveaux (parent/sous_categories), inutile de le refondre.

**Décisions métier ACTÉES :**
- Budgéter au niveau des **majeures ET des mineures** (flexibilité maximale).
- Sur un budget majeur : logique d'**INCLUSION** (l'utilisateur coche les mineures à inclure dans le budget), pas d'exclusion.
- Possibilité de sortir une mineure d'un budget majeur si besoin.

**À FAIRE — enrichir le modèle `Budget`** (ne PAS refondre les catégories) :

| Champ à ajouter | Type | Rôle |
|---|---|---|
| `categorie` | FK Categorie (existe déjà) | Majeure OU mineure |
| `est_budget_majeur` | Boolean | True si la catégorie ciblée est une majeure (agrège ses mineures incluses) |
| `categories_incluses` | M2M vers Categorie | Les mineures explicitement incluses dans le budget majeur |

**Logique de consommation à implémenter (service budgets) :**
- Budget sur **mineure** → somme des flux de cette mineure uniquement.
- Budget sur **majeure** → somme des flux des mineures **incluses** (`categories_incluses`). Convention par défaut à la création : pré-cocher toutes les mineures actives ; l'utilisateur décoche celles à exclure.
- Toujours exclure les transferts (règle 4).
- Fiabilité : **réel**.

**Frontend :** adapter `BudgetFormModal.jsx` — si catégorie majeure sélectionnée → afficher liste des mineures avec cases à cocher (inclusion). Migration : marquer `est_budget_majeur` selon que la catégorie est racine ou non.

### 🟢 Phase 11c — Budgets répétables

**Besoin :** définir des budgets récurrents tous les mois (ex : Alimentation, Carburant) — volatils mais suivant une tendance.

**À FAIRE :**
- Ajouter au modèle `Budget` un champ `est_recurrent` (Boolean) ou créer un modèle `BudgetRecurrent` (template) qui génère les budgets mensuels.
- **Décision d'architecture à trancher avec l'utilisateur** (présenter Option A/B) :
  - **Option A** — Champ `est_recurrent` sur `Budget` + commande/service qui, au passage à un nouveau mois, copie les budgets récurrents du mois précédent.
  - **Option B** — Modèle `BudgetTemplate` séparé (catégorie + montant + inclusions) dont on instancie un `Budget` concret chaque mois. Plus propre, plus de code.
- Recommandation par défaut : **Option A** au MVP (moins de complexité), migrable vers B plus tard.
- Prévoir un montant ajustable par mois (le récurrent donne une valeur par défaut, modifiable).

### ⏳ Phase 10 — Prévisionnel financier (APRÈS la 11)

> Pièce maîtresse. Spec déjà cadrée en session de réflexion. À traiter de préférence en **session de cadrage dédiée** (mode Projet Claude.ai) pour les arbitrages, puis exécution en Claude Code.

**Stratégie :** projeter le solde dans le temps en combinant ce qui est certain (flux datés), récurrent (abonnements) et budgété, avec un curseur de **fiabilité dégressive**.

**4 indicateurs définis :**

| Indicateur | Formule | Fiabilité |
|---|---|---|
| Solde projeté de fin de mois | `solde_théorique_actuel + Σ(flux futurs datés du mois) + Σ(abonnements à échoir) − reste_à_dépenser_budgété` | projeté (élevée, horizon court) |
| Capacité à dépenser restante | `Σ(budgets du mois) − Σ(consommé) − Σ(abonnements restants à échoir)` | projeté |
| Trajectoire d'épargne | par mois futur : `revenus_attendus − dépenses_attendues`, cumulé | projeté (dégressive avec l'horizon) |
| Scénarios de simulation | ajustement d'un paramètre (revenu / catégorie) → impact recalculé à la volée | projeté (hypothétique) |

**Principe de fiabilité dégressive :**

| Horizon | Composantes dominantes | Fiabilité affichée |
|---|---|---|
| Fin du mois courant | Flux réels + abonnements + budgets restants | Élevée |
| 1–3 mois | Abonnements + budgets reconduits | Moyenne |
| 3–12 mois | Tendance historique extrapolée | Faible (indicative) |

**Architecture prévue :**
- Nouvelle app `previsions` (ou étendre `analytics`).
- Tout dans `services/` : `projection.py` (solde projeté), `trajectoire.py` (épargne), `scenario.py` (simulation à la volée).
- **Pas de modèle lourd au début** — calcul à partir de l'existant (flux, budgets, abonnements). Ajouter un modèle `HypotheseProjection` **seulement si** l'utilisateur veut sauvegarder des scénarios (arbitrage à trancher le moment venu : simulations jetables vs mémorisées).
- Approche **hybride** : auto (basé sur historique) + ajustement manuel.
- Horizon **variable** selon le besoin.

**Règles à respecter :** une projection n'est jamais une vérité comptable (toujours étiquetée « projeté ») ; transferts exclus ; aucune donnée de marché dans le solde projeté ; le solde réel reste la seule vérité.

### ⏳ Phase 12 — Budgets dynamiques (expertise financière requise)

**Besoin exprimé :** règles de calcul de budget en fonction des revenus, et/ou recalcul automatique selon les mois précédents (ex : moins dépensé en essence → capacité accrue ailleurs ; rééquilibrage inter-budgets).

⚠️ **Nécessite un cadrage métier dédié** (règles précises à définir avec l'utilisateur). À traiter en session de réflexion (mode Projet). Ne PAS coder sans spec claire. Faire appel à l'expertise financière (méthodes type budget base zéro, enveloppes, % de revenu, lissage de tendance) — toujours en restant pédagogique, sans conseil réglementé.

### ⏳ Phases ultérieures (non détaillées)

- **Objectifs** (`objectifs`) : objectifs d'épargne, suivi de progression.
- **Import CSV** (`imports`) : migration Excel + import bancaire CSV.
- **Market data** (`market_data`) : providers isolés, fallback manuel, sécurité des clés (env), valorisation estimative des actifs de marché. **Jamais** vérité comptable.
- **Durcissement** : réactiver l'auth (JWT), permissions, multi-foyer, audit (`audit`), tests de charge.

---

## 7. PIÈGES CONNUS & BONNES PRATIQUES

- **Fichiers non sauvegardés (`Ctrl+S` oublié)** : cause récurrente de bugs fantômes dans la phase copier-coller (« champ X n'existe pas sur le modèle » alors qu'il a été « ajouté »). En Claude Code ce piège disparaît, mais après une édition, toujours relancer `python manage.py check`.
- **Encodage PowerShell** : des fichiers créés/édités via PowerShell ont parfois corrompu les accents (`Ã©` au lieu de `é`). Écrire en UTF-8 propre.
- **`AppRegistryNotReady`** : `python -c "from app.models import X"` hors contexte Django échoue. Utiliser `manage.py shell` ou `manage.py check` pour valider les imports de modèles.
- **Tailwind v4** : après un rebuild du conteneur, vérifier que `tailwindcss` + `@tailwindcss/vite` sont bien dans `package.json` (souci de persistance déjà rencontré). Toujours vérifier `package.json` après un `npm install`.
- **`dateutil`** : utilisé dans les services patrimoine/analytics (`relativedelta`). Présent dans le conteneur. Si absent après rebuild : `pip install python-dateutil` + l'ajouter à `requirements.txt`.
- **Migrations** : après tout changement de modèle → `docker compose exec backend python manage.py makemigrations <app>` puis `migrate`. Vérifier qu'une migration est bien générée (ne pas supposer).
- **Emojis comme icônes** : abandonnés au profit de `lucide-react` (rendu et contraste incohérents, surtout en dark). Utiliser le composant `IconBadge`.
- **Couleurs en dark** : ne pas bricoler `dark:` au cas par cas pour les pastilles → utiliser les variables CSS sémantiques centralisées (`--icon-badge-bg/fg` etc.).
- **Dashboard non rafraîchi après mutation** : la query key du dashboard est `['analytics', 'dashboard', nbMois]`. Si une ressource n'invalide pas `'analytics'` dans `RESOURCE_DEPENDENCIES`, le dashboard reste en cache périmé. Toute nouvelle ressource affectant les agrégats doit être ajoutée à la map dans `useResource.js`.
- **Label des comptes dans les selects** : toujours afficher `nom — établissement` (et non `établissement || nom`). Avec `établissement || nom`, deux comptes dans la même banque deviennent indiscernables. Patron : `c.etablissement_libelle ? \`${c.nom} — ${c.etablissement_libelle}\` : c.nom`.
- **`perform_create()` manquant** : si seul `perform_update()` est surchargé dans un ViewSet, les objets créés via POST n'ont pas leurs champs calculés (ex : `solde_theorique = 0` à la création d'un compte avec `solde_initial` saisi). Toujours surcharger **les deux** si le recalcul est nécessaire à la création.
- **Flux d'ajustement et agrégats** : les flux `est_ajustement=True` doivent être exclus de tous les filtres dépenses/revenus dans `analytics/services/dashboard.py` (filtre `est_ajustement=False`). Ils ont `categorie=None`, ce qui les exclut automatiquement de `_calculer_depenses_par_categorie`, mais le filtre explicite est nécessaire pour les totaux revenus/dépenses du mois.

---

## 8. COMMANDES UTILES

```powershell
# Lancer / arrêter
docker compose up -d
docker compose down

# Backend
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations <app>
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test            # tous les tests
docker compose exec backend python manage.py test analytics  # une app
docker compose exec backend python manage.py seed_demo       # données de démo
docker compose exec backend python manage.py shell

# Frontend
docker compose exec frontend npm install <pkg>
# Vérifier la persistance d'un paquet :
Select-String -Path frontend/package.json -Pattern "<pkg>"

# Logs
docker compose logs -f backend
docker compose logs -f frontend
```

**URLs dev :** frontend `http://localhost:5173` · API `http://localhost:8000/api/v1/` · admin `http://localhost:8000/admin/`

---

## 9. FORMAT DE TRAVAIL ATTENDU

- Répondre en **français**, concis et direct.
- Avancer **par module cohérent**, jamais réécrire toute l'app d'un coup.
- **Avant de coder une fonctionnalité, vérifier sa place dans la roadmap.** Respecter l'ordre : stabiliser les fondations (CRUD, catégories) avant le prévisionnel ; le prévisionnel avant les budgets dynamiques.
- Pour toute décision d'architecture non triviale : présenter **Option A / Option B / Recommandation / Impact** (tableau).
- Tableaux pour comparaisons, décisions, mappings.
- Quand un indicateur financier est introduit : préciser sa fiabilité (réel / estimatif / projeté).
- Signaler explicitement quand quelque chose relève d'un **arbitrage du foyer** plutôt que d'une règle technique.
- Si une demande est ambiguë sur un point qui change l'implémentation : poser **une** question ciblée avant de coder ; sinon implémenter avec une hypothèse énoncée.
- Privilégier l'opérationnel sur la sur-ingénierie : **pas de complexité inutile au MVP.**
- Tests unitaires sur chaque règle de calcul ; tests API sur les ressources principales.

---

## 10. EXCLUSIONS (ne jamais faire)

- Donner un conseil financier personnalisé réglementé, recommander d'acheter/vendre un actif, promettre un rendement.
- Coder des valeurs de référence ou seuils en dur (toujours via tables administrables).
- Rendre `solde_theorique` ou `ecart_solde` modifiables manuellement.
- Confondre transferts, épargne et dépenses dans les agrégats.
- Supprimer physiquement une donnée financière historique (soft delete uniquement).
- Mettre de la logique métier dans les views ou serializers.
- Appeler une API externe depuis une view/serializer (toujours via providers/services).
- Stocker une clé API en base (variables d'environnement uniquement).
- Utiliser une donnée de marché instantanée comme vérité comptable.
- Construire le dashboard ou la valorisation de marché avant la stabilisation des fondations.
- Produire des alertes culpabilisantes, non configurables ou non explicables.