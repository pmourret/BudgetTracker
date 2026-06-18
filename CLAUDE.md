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
   - `Solde_Théorique = Solde_Initial + Σ(tous les flux du compte)`
   - `Solde_Réel = Solde_Initial + Σ(flux dont statut.est_definitif=True)`
   - `Ecart_Solde = Solde_Réel − Solde_Théorique` (= −Σ flux prévisionnels ; représente les mouvements en attente, **pas une erreur**)
6. `solde_theorique`, `solde_reel` et `ecart_solde` sont **calculés backend, jamais éditables** (serializers `read_only=True`, erreur 400 si tentative de modification).
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
| `comptes` | Modèle `Compte` + service de calcul de solde + `CompteViewSet` (ModelViewSet, CRUD complet). `perform_create()` ET `perform_update()` appellent `calculer_solde()` → les trois champs calculés (`solde_theorique`, `solde_reel`, `ecart_solde`) sont corrects dès la création. `solde_reel = solde_initial + Σ(flux dont statut.est_definitif=True)` : se met à jour automatiquement à chaque mutation de flux. **Champ `est_commun`** (Boolean, défaut `False`, éditable via l'API) : marque un compte partagé du foyer (joint), purement informatif — n'affecte aucun calcul. Migration `0002`. Migration `0003` aligne `solde_reel` (`editable=False`, drift de schéma préexistant corrigé). |
| `categories` | Modèle `Categorie` hiérarchique 2 niveaux (parent/sous_categories) + soft delete protégé. `CategorieSerializer` : champ `code` rendu optionnel (`required=False`), auto-généré par slug depuis `nom` (unique, suffixe `-1`, `-2`… si collision) dans `create()` et `update()`. |
| `flux` | Modèle `Flux` + signals de recalcul de solde. Champ `est_ajustement` (Boolean, `read_only` dans le serializer) : identifie les flux générés par la réconciliation, exclus de tous les agrégats dépenses/revenus. |
| `transferts` | Modèle `Transfert` (paire débit/crédit atomique) |
| `budgets` | Modèle `Budget` + calcul de consommation + taux. `perform_create` et `perform_update` dans `BudgetViewSet` appellent `calculer_consommation()` → le taux se recalcule à chaque création ou modification du montant prévu. **Phase 11b-2 :** champs `est_budget_majeur` (Boolean, `read_only`, auto-détecté) et `categories_incluses` (M2M → Categorie). Auto-détection backend : majeure = racine avec au moins une sous-catégorie active. Auto-remplissage des mineures actives à la création. Validations : budget majeur sans mineure → 400 ; conflit majeure/mineure même mois → 400. Service `calculer_consommation` : budget majeur agrège les flux des mineures incluses ; filtre `est_ajustement=False` ajouté. Signal étendu aux budgets majeures incluant la catégorie du flux. **Phase 11c :** modèle `BudgetTemplate` (`BaseModel`, FK unique sur `categorie`, `montant_defaut`, `categories_incluses` M2M, `est_budget_majeur`, `actif`, `notes`) + FK `template` (nullable) sur `Budget`. `BudgetTemplateSerializer` : mêmes auto-détections que `BudgetSerializer`, valide unicité par catégorie, refuse `montant_defaut ≤ 0`. Service `reconduire_vers_mois()` idempotent (ignore budgets déjà existants). `BudgetTemplateViewSet` + action `POST /budget-templates/reconduire/`. Migration `0003`. **43 tests** (dont 15 nouveaux : BudgetTemplate CRUD + `ReconduireServiceTest` 7 cas + `ReconduireAPITest` 3 cas). |
| `abonnements` | Modèle `Abonnement` récurrent + détection de divergence |
| `alertes` | Alertes auto (budget, solde bas, retard abonnement, divergence, écart solde, **valorisation à faire**) + acquittement |
| `patrimoine` | `Actif` estimatif + `HistoriqueValorisation` (granularité fine) + service de valorisation + rappels de re-valorisation |
| `analytics` | Service `dashboard.py` (agrégats) + `DashboardView` (APIView) + serializer + 14 tests. Inclut `_calculer_depenses_par_categorie(mois)` : agrégation SQL par catégorie majeure (mineures regroupées sous leur parent, triées par montant décroissant). Champ `depenses_par_categorie` ajouté au `DashboardSerializer`. Filtre `est_ajustement=False` appliqué sur tous les agrégats (revenus, dépenses, catégories). **Phase 10-A (prévisionnel)** : services `projection.py` (`calculer_solde_projete`, `calculer_capacite_restante`, `calculer_previsionnel` + helpers échéances abonnements / couverture budgétaire) et `trajectoire.py` (`calculer_trajectoire`), `PrevisionnelView` (APIView) + `PrevisionnelSerializer`, **21 tests** (suite globale à **253 OK**). Lecture seule stricte, aucun modèle persisté, aucune migration. |

**Endpoints clés :**
- CRUD ressources : `/api/v1/comptes/`, `/categories/`, `/flux/`, `/transferts/`, `/budgets/`, `/budget-templates/`, `/abonnements/`, `/alertes/`, `/patrimoine/`
- Référentiels (lecture seule sauf Titulaire et Etablissement) : `/api/v1/referentiels/...`
- Patrimoine : `/patrimoine/total/`, `/patrimoine/historique/?nb_mois=12`, `/patrimoine/verifier-rappels/` (POST)
- Dashboard : `/api/v1/analytics/dashboard/?nb_mois=6`
- Prévisionnel (10-A) : `/api/v1/analytics/previsionnel/?nb_mois=6` (3 blocs `solde_projete`, `capacite_restante`, `trajectoire`, chacun avec `fiabilite` + `definition`)
- Actions custom : `/abonnements/{id}/verifier-divergence/`, `/patrimoine/{id}/valoriser/`, `/alertes/{id}/acquitter/`, `/alertes/acquitter-tout/`, `/budget-templates/reconduire/` (POST, body `{"mois": "YYYY-MM-DD"}`)

### ✅ Frontend — Phase 9 COMPLÈTE

Toutes les pages sont en Tailwind v4 + dark mode complet :

| Page | Route | État |
|---|---|---|
| Dashboard | `/dashboard` (+ `/` redirige ici) | ✅ métriques, courbe solde (sélecteur 3/6/12M), **dépenses par catégorie** (DoughnutChart + légende expandable majeures/mineures), budgets, derniers flux, alertes, bloc patrimoine estimé séparé |
| Comptes | `/comptes` | ✅ CRUD complet : `CompteFormModal` (création + édition — `solde_reel` non saisi, calculé automatiquement), boutons Éditer/Supprimer sur chaque carte, gestion du 400 « compte lié à des flux » avec lien « Désactiver à la place », création inline de Titulaire et Établissement. Affichage carte : « Solde confirmé » (= `solde_reel`) + « En attente » (= `ecart_solde`, négatif si dépenses prévisionnelles). Case à cocher **« Compte commun (partagé du foyer) »** (création + édition) → badge violet **« 👥 Commun »** sur la `CompteCard` et suffixe ` · Commun` dans les libellés de comptes des selects (`FluxFormModal`, `AbonnementFormModal`). |
| Flux | `/flux` | ✅ CRUD complet : `FluxFormModal` étendu (création + édition), colonne Actions sur table desktop (hover), boutons Éditer/Supprimer sur cards mobile, bloc transfert protégé (message + redirection). `type_flux` auto-dérivé du sens (Dépense → DEBIT, Recette → CREDIT), champ retiré du formulaire. Badge « Ajustement » (amber) sur les flux `est_ajustement=True` (anciens flux de réconciliation) ; bouton Supprimer masqué sur ces flux ; `FluxFormModal` bloque leur édition. |
| Transferts | `/transferts` | ✅ Création + annulation : `TransfertFormModal` (compte source/destination, montant, date, statut — défaut « Validé »/`est_definitif`, notes) → `POST /transferts/` (la paire débit/crédit atomique est gérée backend ; le front envoie `type_flux_debit`=DEBIT, `type_flux_credit`=CREDIT, `devise` par défaut). `TransfertCard` affiche `source → destination`, montant, date ; bouton Annuler → `DELETE /transferts/{id}/` (soft delete des deux flux, recalcul des soldes). **Pas d'édition** (un transfert se supprime/recrée, miroir du viewset back). Accessible Sidebar (icône `Repeat`) + menu Plus. C'est le **seul** moyen UI d'alimenter un compte d'épargne (un Flux normal ne touche qu'un compte et serait compté en dépense/recette). |
| Budgets | `/budgets` | ✅ CRUD complet + budgets intelligents (11b-2) + budgets répétables (11c) : `BudgetFormModal` (cases à cocher mineures, majeure accessible via `Nom — budget global`). `BudgetCard` affiche les mineures incluses + icône RecycleArrow si issu d'un template. Onglets **"Ce mois"** / **"Modèles"** : `BudgetTemplateFormModal` (création + édition, catégorie désactivée en édition, toggle actif), `TemplateCard` (CRUD), bouton **"Reconduire sur Mois"** → `POST /budget-templates/reconduire/` → message de confirmation + bascule sur l'onglet Ce mois. Bouton Reconduire aussi dans l'EmptyState du mois si des templates existent. |
| Abonnements | `/abonnements` | ✅ CRUD complet : `AbonnementFormModal` étendu (création + édition + toggle actif), boutons Éditer/Supprimer sur chaque carte. Classes Tailwind brutes remplacées par variables sémantiques. |
| Alertes | `/alertes` | ✅ filtres chips + acquittement |
| Patrimoine | `/patrimoine` | ✅ CRUD complet : `ActifFormModal` étendu (création + édition), boutons Éditer/Supprimer sur chaque `ActifCard`, toggle « actif » en édition |
| Catégories | `/categories` | ✅ CRUD complet : `CategorieFormModal` (majeure ou mineure selon `parentId`), accordéon (majeures → clic → mineures). Boutons Éditer/Supprimer ; si 409 (flux liés) → propose de désactiver. Accessible depuis Sidebar + menu Plus. |
| Prévisionnel | `/previsionnel` | ✅ **Phase 10-A front** : 3 cartes (solde projeté fin de mois avec décomposition en briques réel/engagé/estimé/récurrent ; capacité à dépenser restante + jauge ; trajectoire d'épargne `LineChart`, sélecteur 3/6/12M). `FiabiliteBadge` (elevee=vert, moyenne=ambre, faible=gris) mappé sur la valeur API. Fiabilité dégressive de la trajectoire rendue par coupure plein/pointillés gris dérivée du champ `fiabilite` de chaque point (aucun seuil front). États skeleton/ErrorState (pas d'early return)/EmptyState. Accessible Sidebar (icône `TrendingUp`) + menu Plus. Wording « projeté », jamais vérité comptable. |
| Plus | `/plus` | ✅ menu mobile (accès Prévisionnel/Comptes/Abonnements/Patrimoine/Catégories) + toggle thème |

**Composants UI** (`src/components/ui/`) : `Button`, `Card`, `Input`, `Select` (prop `groups` pour `<optgroup>` natifs), `Modal`, `States` (Loading/Error/Empty), `Badge`, `IconBadge`, `PeriodSelector` (sélecteur 3/6/12M partagé, extrait du Dashboard et réutilisé par Dashboard + Prévisionnel), `Tooltip` (info-bulle d'aide : petite icône « i » révélée au **survol ET au clic/tap** — utilisable en tactile ; ferme au clic extérieur / Échap ; prop `align` `left`/`center`/`right` contre les débordements de bord ; dark mode via variables sémantiques ; props `titre`/`texte`/`formule`, alimenté par `DEFINITIONS`).

**Infos-bulles d'aide (passe transversale, juin 2026)** : tous les indicateurs calculés portent une bulle expliquant **ce que le chiffre représente** ET **comment il est calculé** (formule). Les textes sont **centralisés** dans `src/constants/definitions.js` (objet `DEFINITIONS`, une entrée = `{ titre, texte, formule }`), jamais codés au point d'usage. Usage : `<Tooltip {...DEFINITIONS.solde_total} align="left" />`. Couverture : Dashboard (Solde total, Dépenses/Revenus du mois, Épargne nette, titres « Dépenses par catégorie » + « Patrimoine estimé »), Comptes (Solde théorique/confirmé/En attente — métriques **et** cartes), Budgets (Total prévu/consommé, Reste, taux, badge « Global »), Patrimoine (Total estimé, Plus-value latente), Abonnements (Total mensuel estimé, En retard, Seuil de divergence), Prévisionnel (4 briques du solde projeté + titres des cards, en complément du `definition` déjà renvoyé par l'API). **Toute nouvelle métrique doit ajouter son entrée dans `definitions.js`** et préciser la fiabilité (réel / estimatif / projeté) quand c'est pertinent — pas de texte d'aide en dur.
**Charts** (`src/components/charts/`) : `chartSetup.js` (palette `CAT_PALETTE` 12 couleurs dans DashboardPage), `LineChart`, `BarChart`, `DoughnutChart`.
**Layout** (`src/components/layout/`) : `Layout`, `Sidebar` (desktop, inclut Catégories + Prévisionnel), `BottomNav` (mobile <640px), `ThemeToggle` (variants `dark`/`light`).
**Composants Catégories** (`src/components/categories/`) : `CategorieFormModal` (prop `parentId` = création mineure ; prop `categorie` = édition).
**Composants Prévisionnel** (`src/components/previsionnel/`) : `FiabiliteBadge` (mappe `elevee`/`moyenne`/`faible` → variantes Badge `success`/`avertissement`/`neutre`). Hook dédié `usePrevisionnel.js` (query key `['analytics', 'previsionnel', nbMois]`, couverte par l'invalidation préfixe `'analytics'`).

**Dark mode :** variables CSS sémantiques dans `index.css` (`@theme` clair + bloc `.dark`) : `--color-surface`, `--color-surface-2/3`, `--color-border-app`, `--color-content`, `--color-content-2/3`, `--icon-badge-bg/fg`. Store Zustand `themeStore.js` (modes `system`/`light`/`dark`, persistance `localStorage`, écoute `prefers-color-scheme`). Les couleurs métier (rouge/vert/ambre/violet) restent identiques dans les deux thèmes ; seules surfaces et textes changent.

**Hooks** (`src/hooks/`) : `useResource.js` (`useResourceList`, `useResourceDetail`, `useCreateResource`, `useUpdateResource`, `useDeleteResource`, `useResourceAction` + `RESOURCE_DEPENDENCIES` pour invalidations croisées), `useReferentiels.js` (9 hooks lecture + `useCreateTitulaire`, `useCreateEtablissement`), `useMediaQuery.js` (`useIsMobile`, breakpoint 640px).

**Composants Comptes** (`src/components/comptes/`) : `CompteFormModal` (création + édition, détecte le mode via prop `compte`). Contient `SelectWithCreate` (select + bouton « + Nouveau » + mini-formulaire inline) et `InlineCreate` (input + boutons Créer/Annuler).
**Composants Transferts** (`src/components/transferts/`) : `TransfertFormModal` (création seule — un transfert ne s'édite pas). Construit le payload `POST /transferts/` à partir de compte source/destination + montant + date + statut (défaut le statut `est_definitif`) ; injecte `type_flux_debit`=DEBIT, `type_flux_credit`=CREDIT et la `devise` par défaut. La paire débit/crédit atomique reste gérée par le service backend `creer_transfert`.

**`RESOURCE_DEPENDENCIES`** (invalidations de cache croisées) :
```js
{
  flux:               ['comptes', 'budgets', 'alertes', 'analytics'],
  transferts:         ['comptes', 'flux', 'analytics'],
  budgets:            ['analytics'],
  'budget-templates': ['budgets', 'analytics'],
  abonnements:        ['analytics'],
  comptes:            ['flux', 'analytics'],
  patrimoine:         ['analytics'],
  alertes:            ['analytics'],
  categories:         ['flux', 'budgets', 'abonnements', 'budget-templates'],
}
```
La clé `'analytics'` couvre toutes les variantes du dashboard (`['analytics', 'dashboard', nbMois]`) **et du prévisionnel** (`['analytics', 'previsionnel', nbMois]`) via le prefix-matching de React Query. `abonnements` a été ajouté en phase 10-A (les échéances d'abonnement nourrissent le prévisionnel).

**Sélecteur de catégories groupé :** dans `FluxFormModal`, `AbonnementFormModal`, les catégories sont affichées hiérarchiquement via la prop `groups` de `Select` : majeures sans enfants en options directes, majeures avec enfants en `<optgroup>` contenant leurs mineures. **Dans `BudgetFormModal` et `BudgetTemplateFormModal`**, la majeure elle-même est ajoutée comme **première option sélectionnable dans son propre `<optgroup>`** (label `Nom — budget global`), car on veut pouvoir la sélectionner pour créer un budget d'ensemble.

**Composants Budgets** (`src/components/budgets/`) : `BudgetFormModal` (création + édition via prop `budget`), `BudgetTemplateFormModal` (création + édition via prop `template` — même logique majeure/mineures, catégorie `disabled` en édition pour respecter l'unicité).

---

### ✅ Audit de sécurisation (juin 2026) — TERMINÉ

Exploration complète backend + frontend, corrections de cohérence, **19 tests de régression ajoutés** (suite complète : **232 tests OK**). Migration budgets `0004` (contraintes d'unicité conditionnées au soft delete).

**Corrigé (backend) :**
- **Signal flux** : `pre_save` mémorise l'état précédent (compte/catégorie/mois) ; en cas de changement, `post_save` recalcule AUSSI l'ancien compte (solde) et les anciens budgets via `recalculer_budgets_pour(categorie_id, mois)` (`budgets/services/consommation.py`). Avant : solde/consommation périmés sur l'ancien compte/budget.
- **Contraintes d'unicité vs soft delete** : `Budget(categorie, mois)` et `BudgetTemplate(categorie)` conditionnées à `is_deleted=False` → supprimer puis recréer/reconduire sur la même clé fonctionne (avant : IntegrityError 500).
- **Codes uniques vs soft delete** : les `_auto_code` (catégories, référentiels) vérifient `all_with_deleted()` ; `validate_code` sur `CompteSerializer` et `CategorieSerializer` → 400 propre en cas de collision avec une ligne supprimée (avant : 500).
- **Flux transfert/ajustement protégés** : création directe `est_transfert=True` → 400 (passer par `/transferts/`) ; PATCH/DELETE d'un flux transfert ou ajustement → 400. Le PATCH partiel d'un flux normal (montant seul) ne réclame plus la catégorie à tort.
- **Alertes budgets majeurs** : le signal flux détecte les alertes pour le budget direct ET les budgets majeurs incluant la catégorie du flux (avant : jamais d'alerte sur les majeurs).
- **`categories_incluses` validées** : chaque mineure incluse doit être une fille directe de la catégorie du budget/template ; liste forcée à vide sur un budget non majeur.

**Corrigé (frontend) :**
- `BudgetsPage` : `BudgetCard` teste `budget.template_id` (et non `budget.template`) — l'icône « issu d'un modèle » ne s'affichait jamais.
- `FluxPage` : bouton Supprimer masqué sur les flux de transfert (comme les ajustements).
- `BudgetFormModal` : en édition, changer de catégorie resynchronise les mineures cochées (revenir à la catégorie d'origine restaure la sélection sauvegardée).
- `FluxFormModal` : catégorie exigée aussi pour les recettes (le backend l'a toujours refusée).

**Relevé, NON corrigé (à arbitrer) :**
- ~~**Pagination DRF (`PAGE_SIZE: 50`)**~~ : ✅ **CORRIGÉ (juin 2026)** pour les catégories. Classe `core/pagination.py::StandardPagination` (`page_size=50`, `page_size_query_param="page_size"`, `max_page_size=1000`) référencée dans `REST_FRAMEWORK['DEFAULT_PAGINATION_CLASS']` — comportement par défaut des autres endpoints inchangé. Hook front dédié `useCategories()` (dans `useResource.js`) qui demande `?page_size=1000` et déballe `results` défensivement ; **tous** les consommateurs de `/categories/` passent par lui (CategoriesPage, FluxFormModal, BudgetFormModal, AbonnementFormModal, BudgetTemplateFormModal). 3 tests de régression (`CategoriePaginationTest`). **Reste à étendre aux comptes** si un foyer dépasse 50 comptes (peu probable) : réutiliser `?page_size` via un hook analogue.
- **Catégorie sans flux mais liée à des budgets/abonnements/templates** : encore supprimable (soft delete), ce qui laisse des références vers une catégorie supprimée. Piste : étendre la protection 409 de `Categorie.delete()`.
- **Dashboard `solde_total`** : basé sur `solde_theorique` mais étiqueté fiabilité « reel » — arbitrage sémantique du foyer à confirmer (théorique = inclut le prévisionnel).

## 6. RESTE À FAIRE — ROADMAP

> **Scénario retenu : A (pragmatique).** Stabiliser l'app (CRUD + hiérarchie catégories + budgets répétables) AVANT le prévisionnel. Les budgets dynamiques sont repoussés en phase 12 (nécessitent un cadrage métier dédié).
>
> **État au dernier point :** phases 11a, 11b, 11c **terminées**. Prochaine étape = **Phase 10-A** (prévisionnel, socle lecture seule), dont la **spec détaillée est désormais cadrée** ci-dessous (session de réflexion du projet). Les budgets dynamiques (phase 12) restent **gelés** jusqu'à ce que l'usage réel du prévisionnel 10-A en nourrisse la spec — on n'automatise bien que ce qu'on a d'abord fait à la main et compris.

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

**11b-2 — Budgets intelligents** ✅ TERMINÉE

- Backend : `est_budget_majeur` (Boolean, `read_only`, auto-détecté) + `categories_incluses` (M2M). Majeure = racine avec sous-catégories actives. Auto-remplissage à la création. Validations croisées majeure/mineure même mois. Service mis à jour. Signal étendu aux budgets majeures. Migration `0002`. 28 tests.
- Frontend : `BudgetFormModal` — majeure dans son optgroup comme option `Nom — budget global`, cases à cocher mineures, validation bloquante si aucune cochée. `BudgetCard` affiche les mineures incluses.

### ✅ Phase 11c — Budgets répétables — TERMINÉE

**Architecture retenue : Option B (BudgetTemplate séparé)** — validée par l'utilisateur. Miroir du pattern `Abonnement → Flux`. Base propre pour la Phase 10 (prévisionnel) et Phase 12 (dynamiques).

**Backend :**
- Modèle `BudgetTemplate` (`BaseModel` : UUID, soft delete, timestamps) : `categorie` (FK unique), `montant_defaut`, `categories_incluses` (M2M), `est_budget_majeur`, `actif`, `notes`. Contrainte d'unicité sur `categorie`.
- Champ `template` (FK `BudgetTemplate`, nullable) ajouté sur `Budget` → trace l'origine de chaque budget mensuel.
- `BudgetTemplateSerializer` : auto-détecte `est_budget_majeur`, auto-remplit `categories_incluses` à la création, valide unicité, refuse `montant_defaut ≤ 0`.
- Service `reconduire_vers_mois(mois_cible)` (dans `budgets/services/reconduire.py`) : **idempotent** (ignore si budget existe déjà), copie `montant_defaut → montant_prevu`, `categories_incluses`, `est_budget_majeur`, `notes`, appelle `calculer_consommation`. Normalise le mois au 1er.
- `BudgetTemplateViewSet` (ModelViewSet) + action `POST /budget-templates/reconduire/` (body : `{"mois": "YYYY-MM-DD"}`). Endpoint : `/api/v1/budget-templates/`.
- Migration `0003_budgettemplate_budget_template_and_more.py`.
- 43 tests : CRUD Budget (existants) + BudgetTemplate CRUD + `ReconduireServiceTest` (7 cas) + `ReconduireAPITest` (3 cas).

**Frontend :**
- `BudgetTemplateFormModal.jsx` (`src/components/budgets/`) : création + édition (prop `template`). Pas de champ `mois` (templates permanents). Même logique majeure/mineures que `BudgetFormModal`. Catégorie désactivée en mode édition (unicité). Toggle `actif` en édition.
- `BudgetsPage.jsx` : onglets **"Ce mois"** / **"Modèles"** (TabBtn). Onglet Modèles : liste des templates (`TemplateCard` avec CRUD), bouton **"Reconduire sur Mois"** → `POST /budget-templates/reconduire/` → affiche un message de confirmation + bascule sur l'onglet Ce mois. Bouton Reconduire aussi dans l'EmptyState du mois si des templates existent.
- `useResource.js` : `'budget-templates': ['budgets', 'analytics']` ajouté dans `RESOURCE_DEPENDENCIES`. `categories` invalide aussi `'budget-templates'` (changement de mineures impacte l'auto-détection).

### 🟢 Phase 10 — Prévisionnel financier — 10-A LIVRÉE (back + front)

> Pièce maîtresse. **Spec détaillée ci-dessous, cadrée en session de réflexion dédiée (mode Projet).** Découpée en deux sous-phases : **10-A** (socle lecture seule) **✅ TERMINÉE** puis **10-B** (scénarios de simulation + fourchettes) **⏳ à venir**.
>
> ⚠️ **L'implémentation 10-A livrée s'écarte volontairement de la spec ci-dessous** (validé par l'utilisateur en session). Lire l'encadré « CE QUI A ÉTÉ RÉELLEMENT LIVRÉ » juste sous le titre 10-A avant de toucher au code : la spec d'origine reste affichée comme contexte historique, mais c'est l'encadré qui fait foi.

**Principe directeur (à ne jamais perdre de vue) :** le prévisionnel est **purement consultatif** (lecture seule). Il lit budgets + flux + abonnements, ne modifie **rien**, ne génère **aucune** alerte. Une projection n'est **jamais** une vérité comptable (toujours étiquetée « projeté »). Le solde réel reste la seule vérité.

**Distinction fondamentale — trois natures de flux futurs**, par certitude décroissante, jamais mélangées dans un chiffre opaque :

| Nature | Définition | Source | Certitude |
|---|---|---|---|
| **Engagé** | Flux futur déjà daté et saisi | Flux `statut=PREVISIONNEL`, date future | Quasi-certaine |
| **Récurrent** | Échéance connue, pas encore matérialisée | Abonnements à échoir | Forte |
| **Estimé** | Extrapolation d'un budget | Reste-à-dépenser budgété | Faible/moyenne |

#### Phase 10-A — Socle lecture seule — ✅ TERMINÉE (back + front, 12/06/2026)

> **CE QUI A ÉTÉ RÉELLEMENT LIVRÉ — référence canonique de la phase 10-A.** (La spec détaillée d'origine, qui décrivait une app `previsions`, 3 endpoints, `ParametrePrevision` et des drapeaux de tension, a été retirée car caduque. Le tableau ci-dessous fait foi.)
>
> | Sujet | Spec d'origine | Livré (validé en session) |
> |---|---|---|
> | App | App `previsions` dédiée | **Étendu `analytics`** (scénario A pragmatique) — services `analytics/services/projection.py` + `trajectoire.py` |
> | Endpoints | 3 endpoints séparés | **1 seul** : `GET /api/v1/analytics/previsionnel/?nb_mois=6`, réponse en 3 blocs (`solde_projete`, `capacite_restante`, `trajectoire`), chacun avec `fiabilite` + `definition` |
> | Trajectoire | Repoussée en 10-B | **Incluse en 10-A** (3 indicateurs livrés). Seuls les **scénarios de simulation** restent en 10-B |
> | `ParametrePrevision` | Référentiel singleton (seuils) | **Non créé** — aucun seuil de tension en 10-A, donc aucun paramètre à administrer pour l'instant |
> | Drapeaux de tension + couverture budgétaire | Indicateur 3 avec drapeaux | **Non livrés** (dépendaient de `ParametrePrevision`). Helpers de couverture existent dans `projection.py` mais ne sont pas exposés en drapeaux |
> | Base de la formule | Partir du `solde_reel` | **Partir de `solde_actuel = Σ solde_theorique − Σ flux futurs`** : le `solde_theorique` inclut déjà les flux futurs datés, on les retire puis on réintroduit chaque brique séparément (même objectif anti-double-comptage) |
> | Source dépenses variables (mois futurs trajectoire) | — | **Abonnements + `BudgetTemplate` actifs** (`montant_defaut` comme estimation), complément `max(0, montant_defaut − part déjà couverte)` anti-double-comptage |
> | Modèle persisté / migration | Aucun (10-A) | **Aucun** ✅ — calcul à la volée, lecture seule stricte |
>
> **Détails d'implémentation livrés** (à respecter en 10-B) : échéances d'abonnement dérivées exclusivement de `Frequence.nb_jours` (≥ 28 j → pas calendaires mensuels en `base + pas × n`, `jour_echeance` cale le jour) ; déduplication des abonnements déjà matérialisés en flux futur sur la clé `(categorie_id, montant, mois)` (un flux neutralise une échéance) ; abonnements budgétés exclus (déjà dans le reste-à-dépenser), abonnements non budgétés ajoutés ; transferts et `est_ajustement` exclus partout ; fiabilité dégressive par point (`elevee` M0, `moyenne` M+1→M+3, `faible` au-delà) ; tous les services acceptent `aujourd_hui` injectable pour des tests déterministes ; **21 tests** (suite à **253 OK**). Front : `PrevisionnelPage`, `usePrevisionnel`, `FiabiliteBadge`, `PeriodSelector` partagé, `abonnements: ['analytics']` ajouté à `RESOURCE_DEPENDENCIES`, vérifié Playwright de bout en bout.
>
> **Reste ouvert pour 10-B / plus tard** : `ParametrePrevision` + drapeaux de tension + indicateur de couverture budgétaire (gelés faute de besoin éprouvé), puis scénarios de simulation et fourchettes pessimiste/optimiste.

#### Phase 10-B — Scénarios + fourchettes — APRÈS 10-A

> À ne PAS commencer tant que 10-A n'est pas vécu en usage réel (l'usage nourrit la spec). La trajectoire d'épargne multi-mois est **déjà livrée en 10-A** ; 10-B n'ajoute que ce qui suit.

| Indicateur | Formule | Fiabilité |
|---|---|---|
| Scénarios de simulation | ajustement d'un paramètre (revenu / catégorie) → impact recalculé à la volée | projeté (hypothétique) |
| Fourchette pessimiste/optimiste | solde projeté ± montant non capturé (issu de l'indicateur de couverture, lui aussi à construire) | projeté |
| Drapeaux de tension + couverture budgétaire | abonnement couvert pesant ≥ seuil du reste-à-dépenser ; % des dépenses historiques tombant dans des catégories budgétées | consultatif / réel |

**Architecture 10-B :** service additionnel `scenario.py` (simulation à la volée) dans `analytics/services/`. Si les drapeaux de tension / la couverture budgétaire sont retenus, introduire alors le référentiel `ParametrePrevision` (seuils administrables — ex. `seuil_tension_abonnement_pct`, `fenetre_couverture_mois`) : **aucun seuil codé en dur** (règle 1). Modèle `HypotheseProjection` **seulement si** l'utilisateur veut sauvegarder des scénarios (par défaut : jetables, calcul à la volée).

**Règles à respecter (rappel) :** projection toujours étiquetée « projeté » ; transferts et flux `est_ajustement` exclus ; aucune donnée de marché dans le solde projeté ; le solde réel reste la seule vérité ; tout seuil éventuel via référentiel, jamais en dur.

### ⏳ Phase 12 — Budgets dynamiques (expertise financière requise) — GELÉE

**Besoin exprimé :** règles de calcul de budget en fonction des revenus, et/ou recalcul automatique selon les mois précédents (ex : moins dépensé en essence → capacité accrue ailleurs ; rééquilibrage inter-budgets).

**Trois mécaniques identifiées (non encore spécifiées en détail) :**

| Mécanique | Description | Exemple |
|---|---|---|
| A — Budget indexé sur les revenus | Enveloppe en % du revenu plutôt qu'en montant fixe | « Alimentation = 15 % des revenus du mois » |
| B — Rééquilibrage inter-budgets | Le sous-consommé d'une catégorie augmente la capacité d'une autre | −50 € en carburant → +50 € disponibles ailleurs |
| C — Lissage de tendance | Budget par défaut ajusté sur la moyenne des mois précédents | Carburant moyen 3 mois = 180 € → budget proposé 180 € |

⚠️ **GELÉE jusqu'à usage réel du prévisionnel 10-A.** Raison : les budgets dynamiques sont une **automatisation** ; on n'automatise bien que ce qu'on a d'abord fait à la main et compris. Le prévisionnel (notamment l'indicateur de couverture et l'écart budget/tendance historique) va révéler empiriquement quels budgets sont irréalistes et quels rééquilibrages l'utilisateur fait spontanément — ces observations deviendront la **spec naturelle** de la phase 12.

⚠️ **Nécessite un cadrage métier dédié** (règles précises à définir avec l'utilisateur). À traiter en session de réflexion (mode Projet). Ne PAS coder sans spec claire. Arbitrage de fond déjà identifié : un rééquilibrage automatique est-il souhaitable, ou risque-t-il de masquer un dépassement ? Faire appel à l'expertise financière (méthodes type budget base zéro, enveloppes, % de revenu, lissage de tendance) — toujours en restant pédagogique, sans conseil réglementé. Le lissage de tendance (mécanique C) pourra réutiliser la fenêtre historique paramétrable (`ParametrePrevision`, à introduire en 10-B/12 si retenu — pas encore créé).

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
- **Flux d'ajustement et agrégats** : les flux `est_ajustement=True` (anciens flux de réconciliation, plus créés depuis la suppression de l'action `reconcilier`) doivent rester exclus de tous les filtres dépenses/revenus dans `analytics/services/dashboard.py` (filtre `est_ajustement=False`). Leur `categorie=None` les exclut automatiquement de `_calculer_depenses_par_categorie`, mais le filtre explicite reste nécessaire pour les totaux revenus/dépenses.
- **`solde_reel` auto-calculé** : depuis la phase 11a-correctif, `solde_reel` est calculé dans `comptes/services/solde.py` (`solde_initial + Σ(flux.statut.est_definitif=True)`) et est `read_only` dans le serializer. Ne jamais le saisir manuellement ni l'inclure dans un payload. Après un changement de modèle ou un import de données, relancer `calculer_solde(compte)` sur tous les comptes via `manage.py shell`.
- **`type_flux` dans FluxFormModal** : le champ n'est plus affiché — il est dérivé automatiquement du sens choisi (Dépense → code `DEBIT`, Recette → code `CREDIT`) via `typesFluxData.find(t => t.code === ...)`. Si de nouveaux codes `TypeFlux` sont ajoutés, vérifier que la correspondance `sens → code` dans `FluxFormModal.jsx` reste correcte.
- **`est_budget_majeur` auto-détecté côté backend** : la valeur envoyée par le client est ignorée — le serializer recalcule toujours `est_budget_majeur = (parent_id IS NULL AND sous_catégories actives existent)`. Ne jamais tenter de le forcer via l'API. Une catégorie racine sans mineures actives reste budgétée comme une simple catégorie (`est_budget_majeur=False`).
- **Select groupé `BudgetFormModal` vs autres formulaires** : `BudgetFormModal` et `BudgetTemplateFormModal` insèrent la majeure comme première option sélectionnable dans son `<optgroup>` (`Nom — budget global`). Dans `FluxFormModal` et `AbonnementFormModal`, la majeure n'apparaît dans le groupe que si elle n'a pas de mineures — sinon elle est absente (comportement voulu : on flux sur une mineure, jamais sur une majeure).
- **`test_ecart_solde_recalcule` (flux/tests.py)** : ce test avait un bug — le `setUp` partage un statut `est_definitif=True` entre tous les tests de la classe, mais ce test supposait un statut non-définitif pour obtenir un écart de 100. Corrigé en créant un `StatutFlux` `est_definitif=False` localement dans le test. La logique de production (`solde.py`) était correcte.
- **Volumes Docker vidés (`docker compose down -v`)** : après un `docker compose up -d`, la BDD est vide (pas de tables). Séquence obligatoire : `manage.py migrate` → `manage.py seed_demo`. Sans les migrations, toutes les requêtes API échouent en 500, ce qui peut masquer les pages (si early return sur `isError`).
- **Early return sur `isError` dans les pages** : pattern à éviter — il remplace toute la page (header compris) par le composant d'erreur, supprimant les boutons d'action. Préférer le pattern `{isLoading && <Loading />}` / `{isError && <ErrorState />}` / `{!isLoading && !isError && (...)}` pour conserver le header. `ComptesPage` a été corrigé en ce sens.
- **Soft delete vs contraintes d'unicité** (audit de sécurisation) : les `UniqueConstraint` de `Budget(categorie, mois)` et `BudgetTemplate(categorie)` portent désormais une condition `is_deleted=False` (migration budgets `0004`) — supprimer puis recréer/reconduire sur la même clé fonctionne. Pour les champs `code` `unique=True` (Compte, Categorie, référentiels), la contrainte en base compte AUSSI les lignes soft-deletées : les `_auto_code` cherchent dans `all_with_deleted()` et `validate_code` (Compte, Categorie) renvoie un 400 propre au lieu d'un IntegrityError 500. Toute nouvelle contrainte d'unicité sur un `BaseModel` doit prévoir ce cas.
- **Flux de transfert et d'ajustement protégés côté backend** : `FluxSerializer` refuse `est_transfert=True` en création directe (passer par `/transferts/`) et refuse toute modification d'un flux `est_transfert` ou `est_ajustement` ; `FluxViewSet.destroy()` renvoie 400 sur ces deux types (un transfert s'annule via DELETE `/transferts/{id}/` qui soft-delete la paire). Côté front, `FluxPage` masque le bouton Supprimer pour les deux.
- **Changement de compte/catégorie/date d'un flux** : le signal `pre_save` mémorise l'état précédent (`flux/signals.py`) et `post_save` recalcule AUSSI l'ancien compte (solde) et les anciens budgets (`recalculer_budgets_pour(categorie_id, mois)` dans `budgets/services/consommation.py`). Ne pas court-circuiter ce mécanisme avec des `update()` de queryset (ils ne déclenchent pas les signaux).
- **Alertes budget majeur** : le signal flux détecte les alertes pour le budget direct ET les budgets majeurs incluant la catégorie du flux.
- **`categories_incluses` validées** : chaque mineure incluse doit être une sous-catégorie directe de la catégorie du budget/template (400 sinon) ; sur un budget non majeur, la liste est forcée à vide.
- **`template_id` côté API budgets** : le serializer expose `template_id` (pas `template`) — `BudgetCard` doit tester `budget.template_id`.
- **HMR Vite en conteneur Docker ne voit pas les nouveaux fichiers/routes (phase 10-A front)** : après création d'un fichier React (nouvelle page, nouveau composant) ou ajout d'une route depuis Windows, le watcher Vite dans le conteneur ne recharge pas → symptôme « No routes matched location », page blanche sans erreur console. Remède : `docker compose restart frontend` (puis vérifier que la route répond). Piste de fond si ça récidive : `server.watch.usePolling: true` dans `vite.config`. Toujours valider une nouvelle page par un rendu réel (pas seulement le build).
- **Solde projeté — ne pas repartir du `solde_theorique` brut (phase 10-A)** : `solde_theorique` inclut DÉJÀ les flux datés dans le futur. La projection part de `solde_actuel = Σ solde_theorique − Σ flux futurs (tous, transferts inclus)`, puis réintroduit chaque brique séparément (flux futurs du mois hors transferts/ajustements, abonnements à échoir non budgétés, reste-à-dépenser budgété). Réintroduire un flux futur sans l'avoir d'abord retiré du `solde_theorique` le compte deux fois. Les transferts futurs ne sont pas réintroduits (effet net nul sur le solde global). Voir `analytics/services/projection.py::calculer_solde_projete`.
- **Anti-double-comptage abonnement dans le prévisionnel (phase 10-A)** : un abonnement-dépense est compté UNE seule fois. S'il est déjà matérialisé en flux futur daté → dédupliqué sur `(categorie_id, montant, mois)`. S'il est couvert par un budget (direct ou via une mineure d'un budget majeur) → laissé dans le reste-à-dépenser budgété, jamais ajouté en plus. Seuls les abonnements-dépenses NON budgétés et non encore datés sont ajoutés comme dépense future autonome. Les abonnements-recettes (salaire) sont toujours comptés. Toute évolution de `projection.py`/`trajectoire.py` doit préserver ces trois cas (tests dédiés dans `analytics/tests.py`).
- **Infos-bulles d'aide : textes centralisés, jamais en dur** : les explications des indicateurs vivent dans `src/constants/definitions.js` (objet `DEFINITIONS`, `{ titre, texte, formule }`) et sont rendues via `<Tooltip {...DEFINITIONS.xxx} />`. Ne jamais écrire un texte d'aide directement au point d'usage. Le composant `Tooltip` s'ouvre au **survol ET au clic/tap** (le `:hover` seul est inutilisable en tactile) : ne pas le réduire à un `title=` HTML natif. Positionnement : pas de moteur de placement type floating-ui ; gérer manuellement le risque de débordement de bord via la prop `align` (`right` pour les éléments en bord droit — dernière métrique d'une grille, valeurs alignées à droite ; `left` par défaut pour un libellé suivi de l'icône). Wording aligné sur les règles métier §4-5 et la fiabilité (réel/estimatif/projeté) précisée quand pertinent. **Toute nouvelle métrique calculée ajoute son entrée dans `definitions.js`.**
- **`seed_demo` est dev-only, garde-fou backend** : la commande crée un compte + des catégories de DÉMO et **lève une `CommandError` si `settings.DEBUG=False`** (prod), sauf `--force` explicite. En prod, l'app démarre vierge de données métier : seul `seed_referentiels` (idempotent, aucune donnée métier) est lancé — par l'`entrypoint.prod.sh` à chaque démarrage, et par `make init`/`make seed`. Ne jamais router `seed_demo` vers la prod. En dev : `make dev-seed` (stack dev) ou `python manage.py seed_demo`.
- **Makefile : cibles prod par défaut, dev préfixées `dev-`** : `up`/`down`/`migrate`/`seed`/`deploy`/`backup`… visent la **prod** (`docker-compose.prod.yml` + `.env.prod`). Le dev passe par `dev-up`/`dev-down`/`dev-logs`/`dev-seed` (`docker-compose.yml` + `.env`). `make deploy` = `backup → git pull → build → up → migrate → collectstatic → check` (rebuild back + front, migrations auto). `make reset-db` **détruit le volume `pgdata`** → confirmation `CONFIRMER` exigée. Attention : pour le dev local on utilise habituellement `docker compose ...` directement (cf. §8), pas le Makefile.
- **Onglet navigateur prod/dev** : le titre est posé dynamiquement dans `frontend/src/main.jsx` via `import.meta.env.PROD` — `BudgetTracker` en prod (`vite build`, Dockerfile.prod), `🛠️ BudgetTracker · DEV` en dev (`npm run dev`). `index.html` ne porte qu'un titre neutre par défaut. Ne pas remettre un titre figé dans `index.html`.

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