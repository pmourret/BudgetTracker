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
| `comptes` | Modèle `Compte` + service de calcul de solde + `CompteViewSet` (ModelViewSet, CRUD complet). `perform_create()` ET `perform_update()` appellent `calculer_solde()` → les trois champs calculés (`solde_theorique`, `solde_reel`, `ecart_solde`) sont corrects dès la création. `solde_reel = solde_initial + Σ(flux dont statut.est_definitif=True)` : se met à jour automatiquement à chaque mutation de flux. |
| `categories` | Modèle `Categorie` hiérarchique 2 niveaux (parent/sous_categories) + soft delete protégé. `CategorieSerializer` : champ `code` rendu optionnel (`required=False`), auto-généré par slug depuis `nom` (unique, suffixe `-1`, `-2`… si collision) dans `create()` et `update()`. |
| `flux` | Modèle `Flux` + signals de recalcul de solde. Champ `est_ajustement` (Boolean, `read_only` dans le serializer) : identifie les flux générés par la réconciliation, exclus de tous les agrégats dépenses/revenus. |
| `transferts` | Modèle `Transfert` (paire débit/crédit atomique) |
| `budgets` | Modèle `Budget` + calcul de consommation + taux. `perform_create` et `perform_update` dans `BudgetViewSet` appellent `calculer_consommation()` → le taux se recalcule à chaque création ou modification du montant prévu. **Phase 11b-2 :** champs `est_budget_majeur` (Boolean, `read_only`, auto-détecté) et `categories_incluses` (M2M → Categorie). Auto-détection backend : majeure = racine avec au moins une sous-catégorie active. Auto-remplissage des mineures actives à la création. Validations : budget majeur sans mineure → 400 ; conflit majeure/mineure même mois → 400. Service `calculer_consommation` : budget majeur agrège les flux des mineures incluses ; filtre `est_ajustement=False` ajouté. Signal étendu aux budgets majeures incluant la catégorie du flux. **Phase 11c :** modèle `BudgetTemplate` (`BaseModel`, FK unique sur `categorie`, `montant_defaut`, `categories_incluses` M2M, `est_budget_majeur`, `actif`, `notes`) + FK `template` (nullable) sur `Budget`. `BudgetTemplateSerializer` : mêmes auto-détections que `BudgetSerializer`, valide unicité par catégorie, refuse `montant_defaut ≤ 0`. Service `reconduire_vers_mois()` idempotent (ignore budgets déjà existants). `BudgetTemplateViewSet` + action `POST /budget-templates/reconduire/`. Migration `0003`. **43 tests** (dont 15 nouveaux : BudgetTemplate CRUD + `ReconduireServiceTest` 7 cas + `ReconduireAPITest` 3 cas). |
| `abonnements` | Modèle `Abonnement` récurrent + détection de divergence |
| `alertes` | Alertes auto (budget, solde bas, retard abonnement, divergence, écart solde, **valorisation à faire**) + acquittement |
| `patrimoine` | `Actif` estimatif + `HistoriqueValorisation` (granularité fine) + service de valorisation + rappels de re-valorisation |
| `analytics` | Service `dashboard.py` (agrégats) + `DashboardView` (APIView) + serializer + 14 tests. Inclut `_calculer_depenses_par_categorie(mois)` : agrégation SQL par catégorie majeure (mineures regroupées sous leur parent, triées par montant décroissant). Champ `depenses_par_categorie` ajouté au `DashboardSerializer`. Filtre `est_ajustement=False` appliqué sur tous les agrégats (revenus, dépenses, catégories). |

**Endpoints clés :**
- CRUD ressources : `/api/v1/comptes/`, `/categories/`, `/flux/`, `/transferts/`, `/budgets/`, `/budget-templates/`, `/abonnements/`, `/alertes/`, `/patrimoine/`
- Référentiels (lecture seule sauf Titulaire et Etablissement) : `/api/v1/referentiels/...`
- Patrimoine : `/patrimoine/total/`, `/patrimoine/historique/?nb_mois=12`, `/patrimoine/verifier-rappels/` (POST)
- Dashboard : `/api/v1/analytics/dashboard/?nb_mois=6`
- Actions custom : `/abonnements/{id}/verifier-divergence/`, `/patrimoine/{id}/valoriser/`, `/alertes/{id}/acquitter/`, `/alertes/acquitter-tout/`, `/budget-templates/reconduire/` (POST, body `{"mois": "YYYY-MM-DD"}`)

### ✅ Frontend — Phase 9 COMPLÈTE

Toutes les pages sont en Tailwind v4 + dark mode complet :

| Page | Route | État |
|---|---|---|
| Dashboard | `/dashboard` (+ `/` redirige ici) | ✅ métriques, courbe solde (sélecteur 3/6/12M), **dépenses par catégorie** (DoughnutChart + légende expandable majeures/mineures), budgets, derniers flux, alertes, bloc patrimoine estimé séparé |
| Comptes | `/comptes` | ✅ CRUD complet : `CompteFormModal` (création + édition — `solde_reel` non saisi, calculé automatiquement), boutons Éditer/Supprimer sur chaque carte, gestion du 400 « compte lié à des flux » avec lien « Désactiver à la place », création inline de Titulaire et Établissement. Affichage carte : « Solde confirmé » (= `solde_reel`) + « En attente » (= `ecart_solde`, négatif si dépenses prévisionnelles). |
| Flux | `/flux` | ✅ CRUD complet : `FluxFormModal` étendu (création + édition), colonne Actions sur table desktop (hover), boutons Éditer/Supprimer sur cards mobile, bloc transfert protégé (message + redirection). `type_flux` auto-dérivé du sens (Dépense → DEBIT, Recette → CREDIT), champ retiré du formulaire. Badge « Ajustement » (amber) sur les flux `est_ajustement=True` (anciens flux de réconciliation) ; bouton Supprimer masqué sur ces flux ; `FluxFormModal` bloque leur édition. |
| Budgets | `/budgets` | ✅ CRUD complet + budgets intelligents (11b-2) + budgets répétables (11c) : `BudgetFormModal` (cases à cocher mineures, majeure accessible via `Nom — budget global`). `BudgetCard` affiche les mineures incluses + icône RecycleArrow si issu d'un template. Onglets **"Ce mois"** / **"Modèles"** : `BudgetTemplateFormModal` (création + édition, catégorie désactivée en édition, toggle actif), `TemplateCard` (CRUD), bouton **"Reconduire sur Mois"** → `POST /budget-templates/reconduire/` → message de confirmation + bascule sur l'onglet Ce mois. Bouton Reconduire aussi dans l'EmptyState du mois si des templates existent. |
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
  flux:               ['comptes', 'budgets', 'alertes', 'analytics'],
  transferts:         ['comptes', 'flux', 'analytics'],
  budgets:            ['analytics'],
  'budget-templates': ['budgets', 'analytics'],
  comptes:            ['flux', 'analytics'],
  patrimoine:         ['analytics'],
  alertes:            ['analytics'],
  categories:         ['flux', 'budgets', 'abonnements', 'budget-templates'],
}
```
La clé `'analytics'` couvre toutes les variantes du dashboard (`['analytics', 'dashboard', nbMois]`) via le prefix-matching de React Query.

**Sélecteur de catégories groupé :** dans `FluxFormModal`, `AbonnementFormModal`, les catégories sont affichées hiérarchiquement via la prop `groups` de `Select` : majeures sans enfants en options directes, majeures avec enfants en `<optgroup>` contenant leurs mineures. **Dans `BudgetFormModal` et `BudgetTemplateFormModal`**, la majeure elle-même est ajoutée comme **première option sélectionnable dans son propre `<optgroup>`** (label `Nom — budget global`), car on veut pouvoir la sélectionner pour créer un budget d'ensemble.

**Composants Budgets** (`src/components/budgets/`) : `BudgetFormModal` (création + édition via prop `budget`), `BudgetTemplateFormModal` (création + édition via prop `template` — même logique majeure/mineures, catégorie `disabled` en édition pour respecter l'unicité).

---

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

### ⏳ Phase 10 — Prévisionnel financier (APRÈS la 11) — SPEC CADRÉE

> Pièce maîtresse. **Spec détaillée ci-dessous, cadrée en session de réflexion dédiée (mode Projet).** Découpée en deux sous-phases : **10-A** (socle lecture seule, mono-mois) puis **10-B** (projection longue + scénarios). Exécution en Claude Code.

**Principe directeur (à ne jamais perdre de vue) :** le prévisionnel est **purement consultatif** (lecture seule). Il lit budgets + flux + abonnements, ne modifie **rien**, ne génère **aucune** alerte. Une projection n'est **jamais** une vérité comptable (toujours étiquetée « projeté »). Le solde réel reste la seule vérité.

**Distinction fondamentale — trois natures de flux futurs**, par certitude décroissante, jamais mélangées dans un chiffre opaque :

| Nature | Définition | Source | Certitude |
|---|---|---|---|
| **Engagé** | Flux futur déjà daté et saisi | Flux `statut=PREVISIONNEL`, date future | Quasi-certaine |
| **Récurrent** | Échéance connue, pas encore matérialisée | Abonnements à échoir | Forte |
| **Estimé** | Extrapolation d'un budget | Reste-à-dépenser budgété | Faible/moyenne |

#### Phase 10-A — Socle lecture seule (mono-mois) — À FAIRE EN PREMIER

> Donne 80 % de la valeur pour 40 % de l'effort : savoir si on finit le mois dans le vert, et combien il reste à dépenser.

**DÉCISIONS MÉTIER ACTÉES (ne pas re-débattre, implémenter directement) :**

| Sujet | Décision actée |
|---|---|
| Source des dépenses variables futures | **Les budgets** (prolongement phase 11b). Pas l'historique en 10-A. |
| Flux futurs « certains » | **Statut PREVISIONNEL + `date_flux` future** (les deux conditions). On s'appuie sur le sens métier du statut. |
| Abonnements vs budgets | Abonnements **inclus** dans les budgets → **déduits** pour éviter le double comptage. |
| Abonnement non budgété | Si sa catégorie n'a **pas** de budget actif (ni majeure ni mineure) → ajouté séparément comme dépense future autonome. |
| Tension budgétaire | Si un abonnement à échoir **couvert** par un budget pèse ≥ seuil du reste-à-dépenser de sa catégorie → **drapeau** (consultatif, pas d'alerte générée). |
| Seuil de tension | Référentiel `ParametrePrevision.seuil_tension_abonnement_pct`, **défaut 70 %**. |
| Couverture budgétaire | Indicateur qui qualifie la fiabilité : % des dépenses historiques réelles tombant dans des catégories budgétées. |
| Fenêtre de couverture | `ParametrePrevision.fenetre_couverture_mois`, **défaut 3 mois**. |
| Niveau d'éval. couverture | **Majeure**. Une majeure est « couverte » s'il existe un budget sur elle **OU** sur une de ses mineures. |
| Nombre d'endpoints | **Trois endpoints séparés** (granularité, états de chargement indépendants). |

**Formule de référence du solde projeté (DÉCOMPOSITION TRAÇABLE obligatoire) :**

> ⚠️ Cohérence avec la stratégie de solde actuelle (règles 5/6) : le `solde_theorique` inclut DÉJÀ tous les flux (y compris prévisionnels). **Ne pas ré-additionner les flux prévisionnels au `solde_theorique`** ou on les compte deux fois. Partir du `solde_reel` (= flux définitifs uniquement) pour une projection propre :

```
Solde projeté fin de mois =
    solde_reel_actuel                            (RÉEL — flux définitifs : solde_initial + Σ flux statut.est_definitif=True)
  + Σ flux PREVISIONNELS du mois (date ≤ fin mois) (ENGAGÉ — hors transferts, hors est_ajustement)
  − reste_à_dépenser_budgété                       (ESTIMÉ — Σ max(0, montant_prevu − montant_consomme), inclut abos budgétés)
  − Σ abonnements à échoir SANS budget             (RÉCURRENT non couvert)
```

Chaque brique est **exposée séparément** dans la réponse API (le front affiche le total ET son détail).

**Les trois indicateurs du 10-A :**

| # | Indicateur | Formule | Fiabilité |
|---|---|---|---|
| 1 | Solde projeté fin de mois | voir décomposition ci-dessus | projeté |
| 2 | Capacité à dépenser restante | `Σ budgets − Σ consommé − Σ abonnements restants non couverts` | projeté |
| 3 | Couverture budgétaire (+ drapeaux tension) | `dépenses hist. dans catégories budgétées / dépenses hist. totales` | réel (qualifie la projection) |

**Règle de tension (indicateur 3, drapeaux) :**
```
part = abonnement_à_échoir / reste_à_dépenser_catégorie
reste ≤ 0           → drapeau ROUGE (budget épuisé)
part ≥ seuil (70%)  → drapeau AMBRE (l'abonnement mange l'essentiel du reste)
sinon               → pas de drapeau
```
Message factuel, non culpabilisant (règle 13). Ex : « L'abonnement Spotify (25 €) représente 83 % de ton reste-à-dépenser Loisirs (30 €). »

**ARCHITECTURE TECHNIQUE 10-A :**

```
backend/previsions/
├── models.py          # ParametrePrevision (référentiel singleton) — AUCUN modèle de projection
├── serializers.py     # sérialiseurs de sortie (lecture seule)
├── views.py           # 3 APIView : SoldeProjeteView, CapaciteView, CouvertureView
├── urls.py            # 3 routes (hors router, comme analytics)
├── services/
│   ├── __init__.py
│   ├── parametres.py     # get_parametres() → singleton get_or_create avec défauts
│   ├── solde_projete.py  # calculer_solde_projete(nb_mois_horizon=1) → dict décomposé + drapeaux_tension
│   ├── capacite.py       # calculer_capacite_depenser()
│   └── couverture.py     # calculer_couverture_budgetaire()
└── tests.py
```

**Modèle `ParametrePrevision`** (singleton, app `previsions`) :
- `seuil_tension_abonnement_pct` : Decimal, défaut `70.00`.
- `fenetre_couverture_mois` : PositiveSmallInteger, défaut `3`.
- Hérite de `BaseModel`. Accès via `services/parametres.py::get_parametres()` (get_or_create avec défauts — soigner l'implémentation singleton, ex. `pk` fixe ou manager dédié).
- ⚠️ Jamais de seuil codé en dur ailleurs (règle 1).

**Endpoints (3 séparés) :**
```
GET /api/v1/previsions/solde-projete/?horizon=1
GET /api/v1/previsions/capacite/
GET /api/v1/previsions/couverture/
```
Chacune une `APIView` (pas un ViewSet — ce ne sont pas des ressources de modèle), déclarées dans `config/urls.py` AVANT le router (comme `analytics/dashboard/`).

**Structure de retour `solde-projete` :**
```json
{
  "solde_reel_actuel": "...", "flux_previsionnels": "...",
  "reste_a_depenser_budgete": "...", "abonnements_non_budgetes": "...",
  "solde_projete": "...", "fiabilite": "projete",
  "drapeaux_tension": [ { "abonnement": "...", "categorie": "...", "part_pct": "...", "niveau": "ROUGE|AMBRE", "message": "..." } ]
}
```

**Branchements :**
- `seed_demo` : créer la ligne `ParametrePrevision` par défaut (idempotent).
- Front `RESOURCE_DEPENDENCIES` : ajouter `'previsions'` comme dépendance de `flux`, `budgets`, `abonnements`, `comptes`. Les 3 query keys (`['previsions','solde-projete']`, etc.) partagent le préfixe `'previsions'` → une invalidation les rafraîchit toutes (prefix-matching React Query).
- Front : 3 `useQuery` distincts, une page `PrevisionsPage` avec 3 blocs (chacun son état de chargement). Bloc solde projeté = afficher le total + sa décomposition en briques étiquetées (réel/engagé/estimé/récurrent). Bandeau de couverture honnête (« la projection couvre X % de tes dépenses habituelles »).

**Tests obligatoires (10-A) :** une brique du solde projeté par test + cas double-comptage abonnement (budgété → déduit, non budgété → ajouté) + couverture (majeure couverte via mineure) + drapeau tension (rouge si reste ≤ 0, ambre si part ≥ seuil) + exclusion transferts et `est_ajustement`.

#### Phase 10-B — Projection longue + scénarios — APRÈS 10-A

> À ne PAS commencer tant que 10-A n'est pas vécu en usage réel (l'usage nourrit la spec).

| Indicateur | Formule | Fiabilité |
|---|---|---|
| Trajectoire d'épargne | par mois futur : `revenus_attendus − dépenses_attendues`, cumulé | projeté (dégressive avec l'horizon) |
| Scénarios de simulation | ajustement d'un paramètre (revenu / catégorie) → impact recalculé à la volée | projeté (hypothétique) |
| Fourchette pessimiste/optimiste | solde projeté ± montant non capturé (issu de la couverture) | projeté |

**Principe de fiabilité dégressive (affichage) :**

| Horizon | Composantes dominantes | Fiabilité affichée |
|---|---|---|
| Fin du mois courant | Flux réels + abonnements + budgets restants | Élevée |
| 1–3 mois | Abonnements + budgets reconduits (templates phase 11c) | Moyenne |
| 3–12 mois | Tendance historique extrapolée | Faible (indicative) |

**Architecture 10-B :** services additionnels `trajectoire.py` (épargne multi-mois) et `scenario.py` (simulation à la volée). Modèle `HypotheseProjection` **seulement si** l'utilisateur veut sauvegarder des scénarios (arbitrage à trancher : simulations jetables vs mémorisées — par défaut jetables, calcul à la volée). La reconduction des budgets via `BudgetTemplate` (phase 11c) alimente naturellement la projection multi-mois.

**Règles à respecter (10-A et 10-B) :** projection toujours étiquetée « projeté » ; transferts et flux `est_ajustement` exclus ; aucune donnée de marché dans le solde projeté ; le solde réel reste la seule vérité ; aucun seuil codé en dur (tout via `ParametrePrevision`).

### ⏳ Phase 12 — Budgets dynamiques (expertise financière requise) — GELÉE

**Besoin exprimé :** règles de calcul de budget en fonction des revenus, et/ou recalcul automatique selon les mois précédents (ex : moins dépensé en essence → capacité accrue ailleurs ; rééquilibrage inter-budgets).

**Trois mécaniques identifiées (non encore spécifiées en détail) :**

| Mécanique | Description | Exemple |
|---|---|---|
| A — Budget indexé sur les revenus | Enveloppe en % du revenu plutôt qu'en montant fixe | « Alimentation = 15 % des revenus du mois » |
| B — Rééquilibrage inter-budgets | Le sous-consommé d'une catégorie augmente la capacité d'une autre | −50 € en carburant → +50 € disponibles ailleurs |
| C — Lissage de tendance | Budget par défaut ajusté sur la moyenne des mois précédents | Carburant moyen 3 mois = 180 € → budget proposé 180 € |

⚠️ **GELÉE jusqu'à usage réel du prévisionnel 10-A.** Raison : les budgets dynamiques sont une **automatisation** ; on n'automatise bien que ce qu'on a d'abord fait à la main et compris. Le prévisionnel (notamment l'indicateur de couverture et l'écart budget/tendance historique) va révéler empiriquement quels budgets sont irréalistes et quels rééquilibrages l'utilisateur fait spontanément — ces observations deviendront la **spec naturelle** de la phase 12.

⚠️ **Nécessite un cadrage métier dédié** (règles précises à définir avec l'utilisateur). À traiter en session de réflexion (mode Projet). Ne PAS coder sans spec claire. Arbitrage de fond déjà identifié : un rééquilibrage automatique est-il souhaitable, ou risque-t-il de masquer un dépassement ? Faire appel à l'expertise financière (méthodes type budget base zéro, enveloppes, % de revenu, lissage de tendance) — toujours en restant pédagogique, sans conseil réglementé. Le lissage de tendance (mécanique C) pourra réutiliser la fenêtre historique de `ParametrePrevision`.

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