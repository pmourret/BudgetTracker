# CLAUDE.md — BudgetTracker

> Fichier d'**instructions**. Les règles de `FamilyToolSuite/CLAUDE.md` s'appliquent
> ici à l'identique.
>
> 📖 **L'état livré, la roadmap et les décisions structurantes vivent dans le site
> de documentation** (`Documentation/docs/budgettracker/`), en ligne sur
> <https://doc.sternum-lab.duckdns.org/budgettracker/>. Ce fichier ne dit que ce
> qu'il faut savoir **avant d'écrire une ligne**. Migration faite le 2026-08-11.

---

## 1. RÔLE & POSTURE

Assistant technique dédié à **BudgetTracker**, application web de suivi budgétaire
familial issue d'un classeur Excel (`SUIVI_BUDGET.xlsx`).

Sept casquettes : architecte logiciel senior, expert backend Django/DRF, expert
frontend React, expert modélisation PostgreSQL, expert gestion financière
personnelle (pédagogique, **jamais de conseil réglementé**), concepteur produit,
architecte d'intégrations API.

**Posture d'expert financier :** rester dans le cadre de la gestion budgétaire
familiale (organisation, priorisation, suivi des risques, pédagogie,
visualisation). **Jamais** de conseil financier personnalisé réglementé, jamais de
recommandation d'achat/vente d'actif, jamais de promesse de rendement. Signaler
quand une décision relève d'un **arbitrage du foyer**.

Quand un indicateur est introduit, préciser **toujours** : définition, formule,
données requises, **fiabilité** (réel / contrôle / estimatif / projeté), fréquence
de recalcul.

---

## 2. STACK TECHNIQUE (figée)

| Couche | Techno |
|---|---|
| Backend | Django 5 (tourne en réalité sur Django 6.0.6 dans le conteneur) |
| API | Django REST Framework |
| Frontend | React 18 + Vite |
| State | React Query (serveur) + Zustand (thème) — **pas de Redux** |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`, `@theme` dans `index.css`) |
| Icônes | lucide-react |
| Graphiques | chart.js + react-chartjs-2 |
| BDD | PostgreSQL 16 |
| Orchestration | Docker Compose (`backend`, `frontend`, `db`) |
| Auth | **JWT (`simplejwt`), actif partout.** Défaut fermé dans `base.py` ; **aucune dérogation** dans `dev.py` ni `prod.py`. |

**Environnement de dev :** Windows + PowerShell 5.1 + VS Code + Docker Desktop.

---

## 3. ARCHITECTURE — 16 apps Django

```
core · referentiels · comptes · categories · flux · budgets · abonnements ·
transferts · patrimoine · alertes · objectifs · market_data · imports ·
analytics · audit · accounts
```

**Principes non négociables :**
- Logique métier dans une couche `services/` séparée. **Jamais** dans les views ni les serializers.
- Les serializers valident et exposent. Les views/viewsets restent simples.
- Router centralisé unique dans `config/urls.py`.
- `BaseModel` abstrait (`core`) : UUID en PK, timestamps, **soft delete** (`is_deleted` + manager filtré).
- Pattern `_calculer_xxx_avec_model(obj, Model)` : logique pure injectable.
- Imports de modèles **toujours locaux** dans les fonctions de services (anti-circulaire).
- Une API externe n'est **jamais** appelée depuis une view/serializer : toujours via `providers/`. Clés API en variables d'environnement, jamais en base.

---

## 4. RÈGLES MÉTIER NON NÉGOCIABLES

1. `PARAMETRES` = référentiels administrables. **Jamais de valeur ni de seuil codé en dur.**
2. `FLUX` = journal central. Montant **signé** (−215 = dépense, +2800 = revenu).
3. `Mois` = **mois comptable**, pas calendaire. Paramètre `jour_debut_mois_comptable` (défaut 1, borné à 28). **Point unique de vérité : `core/services/periode.py`.** Changement du paramètre → remap auto de tout l'historique. *(Détail et convention de libellé : site → Domaine.)*
4. Les transferts internes ne sont **jamais** confondus avec des dépenses/revenus (`est_transfert` + modèle `Transfert`). Exclus de tous les agrégats.
5. Soldes : `Théorique = Initial + Σ(tous les flux)` · `Réel = Initial + Σ(flux définitifs)` · `Ecart = Réel − Théorique` (= mouvements en attente, **pas une erreur**).
6. `solde_theorique`, `solde_reel`, `ecart_solde` **calculés backend, jamais éditables** (`read_only`, 400 si tentative).
7. Recalcul de solde par signal à chaque CREATE/UPDATE/DELETE de flux, **atomique**.
8. **Aucune suppression physique** d'une donnée financière : soft delete. Un compte/une catégorie lié à des flux ne peut qu'être **désactivé**.
9. Une catégorie liée à des flux ne se supprime pas, elle se désactive.
10. Les données de marché ne touchent **jamais** les soldes bancaires. Valorisation **estimative** du patrimoine uniquement, jamais mélangée au solde.
11. Ordre de construction : référentiels → comptes → catégories → flux → soldes → budgets → abonnements → alertes → patrimoine → **dashboard en dernier**.
12. Tests unitaires **obligatoires** sur chaque règle de calcul ; tests API sur les ressources principales.
13. **Pas d'alertes culpabilisantes**, non configurables ou non explicables.

---

## 5. ÉTAT — EN BREF

**493 tests.** Backend phases 1-8 complètes, frontend phase 9 complète, plus
10-A, 11a/b/c, 12-B, 13, 14-A/B, durcissement de l'auth et vérification des
jetons de l'annuaire.

**En production**, derrière Traefik, sur `budgets.sternum-lab.duckdns.org`.
L'annuaire `Identite` fait autorité sur les comptes depuis le 2026-08-11.

📖 **Détail complet sur le site** — [État livré], [Authentification], [Domaine].

**Porte de secours si l'annuaire est éteint :** admin Django, session et mot de
passe locaux. **Ne pas supprimer les comptes `pierre` / `pmourret_adm`.**

---

## 6. PROCHAINE ÉTAPE

> **Scénario A (pragmatique)** : stabiliser avant le prévisionnel, le prévisionnel
> avant les budgets dynamiques. 📖 Roadmap complète sur le site.

🚧 **L'étape 3 de l'interop courses** (`RegleIngestion` +
`POST /api/v1/integrations/depenses/`) est **bloquée par une décision de suite** :
depuis que l'annuaire fait autorité, FoyerOS n'a plus aucun moyen de
s'authentifier ici — un compte local n'obtient plus de jeton, et
`accounts/annuaire.py` refuse tout jeton portant `service: true`.

Les trois issues sont détaillées dans le contrat : <https://doc.sternum-lab.duckdns.org/suite/interop-courses-budget/#le-point-bloquant>
**Trancher avant de coder.**

Ensuite : **10-B** (scénarios + fourchettes), puis le prévisionnel à taux
d'épargne. **Phase 12 mécaniques A et C : gelées, ne pas coder sans spec.**

---

## 7. PIÈGES CONNUS & BONNES PRATIQUES

> La section la plus utile de ce fichier. Chaque ligne a coûté du temps.

### Environnement & conteneurs

- **Encodage PowerShell** : des fichiers édités via PowerShell ont corrompu des accents (`Ã©`). Écrire en UTF-8 propre. *(`requirements.txt` était en UTF-16LE, corrigé.)*
- **`AppRegistryNotReady`** : `python -c "from app.models import X"` hors contexte Django échoue. Utiliser `manage.py shell` ou `manage.py check`.
- **Tailwind v4** : après un rebuild du conteneur, vérifier que `tailwindcss` + `@tailwindcss/vite` sont dans `package.json` (souci de persistance rencontré).
- **Dépendances front absentes après rebuild** : un paquet déclaré mais absent du `node_modules` du conteneur fait échouer `npm run build` (`Rollup failed to resolve import`). **Remède systématique : `docker compose exec frontend npm install` après tout rebuild `frontend`.**
- **`cryptography` pour RS256** : PyJWT ne fait pas de RS256 sans elle et **ne le dit qu'à l'exécution**. Reconstruire l'image — un `pip install` ne survit pas à `up -d`.
- **`dateutil`** : utilisé dans patrimoine/analytics (`relativedelta`). Si absent après rebuild, l'ajouter à `requirements.txt`.
- **Migrations** : après tout changement de modèle → `makemigrations <app>` puis `migrate`. **Vérifier qu'une migration est générée, ne pas supposer.**
- **Volumes vidés (`down -v`)** : séquence obligatoire `migrate` → `seed_demo`. Sans migrations, toutes les requêtes échouent en 500.
- **HMR Vite en conteneur ne voit pas les nouveaux fichiers** : après création d'un fichier React ou ajout de route depuis Windows, symptôme « No routes matched location », page blanche sans erreur console. Remède : `docker compose restart frontend`. **Toujours valider une nouvelle page par un rendu réel, pas seulement le build.**
- **`ALLOWED_HOSTS` doit contenir `host.docker.internal`** côté annuaire *et* FoyerOS : sinon **400 DisallowedHost**, qui ressemble à un mauvais mot de passe. Rencontré deux fois.
- **Upload multipart : curl sur Windows n'aime pas `-F "fichier=@x.csv;type=text/csv"`** (renvoie `HTTP 000`) → omettre le `;type=`.

### Backend — modèle et signaux

- **`perform_create()` manquant** : si seul `perform_update()` est surchargé, les objets créés par POST n'ont pas leurs champs calculés. **Surcharger les deux.**
- **`solde_reel` auto-calculé** (`comptes/services/solde.py`), `read_only`. Ne jamais le saisir. Après un import de données, relancer `calculer_solde()` sur tous les comptes.
- **Changement de compte/catégorie/date d'un flux** : `pre_save` mémorise l'état précédent, `post_save` recalcule AUSSI l'ancien compte et les anciens budgets (`recalculer_budgets_pour`). **Ne pas court-circuiter avec des `update()` de queryset** — ils ne déclenchent pas les signaux.
- **Soft delete vs contraintes d'unicité** : toute `UniqueConstraint` sur un `BaseModel` doit porter `condition=Q(is_deleted=False)`. Pour les `code` `unique=True`, la contrainte compte AUSSI les lignes soft-deletées : les `_auto_code` cherchent dans `all_with_deleted()` et `validate_code` renvoie un 400 propre au lieu d'un 500.
- **Le soft delete ne cascade pas** : `ImportBancaire.delete()` est surchargé pour soft-deleter ses lignes. Sinon leurs hash restent comptés par l'anti-doublon → **ré-import du même relevé bloqué à tort**. Toute nouvelle relation enfant persistée doit prévoir ce cas.
- **Flux transfert/ajustement protégés** : création directe `est_transfert=True` → 400 ; PATCH/DELETE d'un transfert ou ajustement → 400.
- **Flux d'ajustement et agrégats** : filtre `est_ajustement=False` explicite nécessaire sur les totaux revenus/dépenses (leur `categorie=None` ne suffit qu'aux ventilations par catégorie).
- **`est_budget_majeur` auto-détecté backend** : la valeur envoyée par le client est **ignorée**. Ne jamais tenter de la forcer.
- **`categories_incluses`** : chaque mineure doit être fille directe de la catégorie du budget (400 sinon) ; forcée à vide sur un budget non majeur.
- **Budgets thématiques** : `categorie=None` + `nom` obligatoire. Unicité et exclusivité gérées **manuellement dans `validate()`**. Ne jamais afficher `categorie_nom` (peut être null) — utiliser `libelle`.
- ⚠️ **DRF `UniqueConstraint` multi-champs → `UniqueTogetherValidator` qui rend les champs OBLIGATOIRES.** Il exige tous ces champs dans chaque payload (erreur `required`), **même si le champ est `required=False`**, et **en ignorant la condition partielle**. Une contrainte **mono-champ** devient un simple `UniqueValidator` — d'où une asymétrie déroutante entre deux serializers voisins. Remède : `class Meta: validators = []` puis valider dans `validate()`. Symptôme piégeux : `serializer.fields['x'].required` renvoie `False` alors qu'`is_valid()` lève quand même `required`.
- **Mois comptable ≠ calendaire** : **toute** logique « mois courant » ou « bornes de mois » DOIT passer par `core/services/periode.py`. Jamais `date.replace(day=1)` en dur. Filtrer par `flux.mois` est auto-correct ; filtrer par **plage de dates** exige `bornes_mois_comptable`.
- **Solde projeté : ne pas repartir du `solde_theorique` brut** — il inclut DÉJÀ les flux futurs datés. La projection part de `solde_actuel = Σ solde_theorique − Σ flux futurs`, puis réintroduit chaque brique séparément. Réintroduire sans avoir retiré compte deux fois.
- **Système de points** : `points_alloues` est **read-only** — passer par `POST /budgets/{id}/allouer/`, jamais un PATCH direct. Le taux se calcule contre le **prévu effectif**. La réserve est recalculée à la volée, il n'y a pas de table.
- **`seed_demo` est dev-only** : lève `CommandError` si `DEBUG=False`, sauf `--force`. En prod seul `seed_referentiels` tourne. **Ne jamais router `seed_demo` vers la prod.**

### Rapprochement bancaire

- **La SEULE écriture de flux est `creer_flux_depuis_ligne`.** Tout le reste du moteur n'écrit que l'état de rapprochement de la `LigneBancaire`.
- **Pointage détecté par le LIEN, pas par `reference_externe`** — celle-ci n'est qu'une trace lisible, jamais une clé de détection, jamais écrasée sur un flux existant.
- **`accountbalance` BoursoBank = instantané journalier** : les lignes d'un même jour partagent le même solde. Donc (1) **pas d'unicité dure** sur `hash_dedup`, l'anti-doublon se fait par comptage ; (2) le contrôle compare le solde **actuel** de l'app au dernier solde du relevé, **au centime**.
- ⚠️ **Ne PAS ré-ancrer le contrôle « à la date du relevé »** (`Σ flux ≤ date_ref`) : faux écarts par décalage de dates de saisie, **constaté en prod**.
- **Matching STRICT puis tolérance, ambigus non devinés** : un flux exact l'emporte sur un flux proche. Plusieurs candidats → `ambigu`, l'utilisateur tranche. Les virements se rapprochent **sans parser le libellé VIR**.
- **Remboursement = contre-flux recette, JAMAIS un drapeau** (le foyer fait du rapprochement : la banque montre les deux lignes). Ne jamais rembourser un flux qui n'est pas une dépense, un transfert, un ajustement, ni au-delà du reste à rembourser.

### Frontend

- **Emojis comme icônes** : abandonnés au profit de `lucide-react`. Utiliser `IconBadge`.
- **Couleurs en dark** : ne pas bricoler `dark:` au cas par cas → variables CSS sémantiques centralisées.
- ⚠️ **Couleurs de données ≠ couleurs d'état.** Le turquoise dit « entrant »,
  le rouge « sortant », l'ambre « alerte », le violet la marque : aucune ne
  désigne jamais une catégorie ou une série. Passer par
  `charts/paletteDonnees.js` (`usePaletteDonnees`), dont la rampe est
  **disjointe** et validée (chroma, séparation en vision déficiente,
  contraste), avec ses propres crans en sombre. La couleur suit
  l'**identifiant** de l'entité, jamais son rang dans la liste — sinon une
  catégorie change de couleur dès qu'une autre est ajoutée. Revalider après
  tout changement de rampe : les contrôles portent sur les paires
  **adjacentes**, donc l'ordre compte.
- ⚠️ **En thème sombre, une frontière se trace par la BORDURE, pas par le fond.**
  Une carte ne se sépare du fond que par **1,22:1** — c'est `border-border-app`
  qui la délimite. Remonter un fond pour « détacher » un bloc ne marche pas :
  la barre latérale câblée sur `bg-ink` était à 1,12:1 du fond de page et
  disparaissait. Corrigé par fond **et** `border-r`. Vérifier un contraste par
  le calcul, jamais à l'œil sur un écran calibré autrement.
- **Dashboard non rafraîchi après mutation** : toute ressource affectant les agrégats doit être ajoutée à `RESOURCE_DEPENDENCIES` dans `useResource.js`, sinon le cache reste périmé.
- **Early return sur `isError`** : pattern à éviter, il remplace toute la page (header compris) et supprime les boutons d'action. Préférer `{isLoading && …}` / `{isError && …}` / `{!isLoading && !isError && (…)}`.
- **Label des comptes dans les selects** : toujours `nom — établissement`, jamais `établissement || nom` (deux comptes de la même banque deviendraient indiscernables).
- **`type_flux` dans `FluxFormModal`** : dérivé du sens (Dépense → `DEBIT`). Si de nouveaux codes sont ajoutés, vérifier la correspondance.
- **Select groupé** : `BudgetFormModal`/`BudgetTemplateFormModal` insèrent la majeure comme option (`Nom — budget global`) ; dans `FluxFormModal`/`AbonnementFormModal` elle est **absente** si elle a des mineures (voulu : on flux sur une mineure).
- **Liste de flux : toujours `FluxSearchPanel` + `useInfiniteResource`**, jamais `useResourceList('flux')` seul — ce dernier ne charge que 50 flux et rend les mois anciens inaccessibles. Recherche et filtrage **côté serveur**, jamais en filtrant un tableau déjà chargé. `baseParams` ne doit pas être contournable.
- **`titulaire_compte` ≠ `titulaire`** : le propriétaire d'un compte est `compte__titulaire` ; le `titulaire` du flux est souvent nul.
- **Heatmap : échelle plafonnée au 90e centile**, jamais sur le max brut (un loyer écrasait toute l'échelle). Cellules en hauteur fixe (`h-12 sm:h-14`), **jamais `aspect-square`**.
- **Infos-bulles : textes centralisés** dans `src/constants/definitions.js`, jamais au point d'usage. Le `Tooltip` s'ouvre au **survol ET au clic** (le `:hover` seul est inutilisable en tactile). **Toute nouvelle métrique ajoute son entrée.**
- ⚠️ **Upload `FormData` via `apiClient` → 415** : `api/client.js` fixe `Content-Type: application/json`, et axios v1 **sérialise alors le FormData en JSON**. Forcer `multipart/form-data` ne suffit pas (le **boundary manque**). **Solution : axios NU** (`axios.post('/api/v1/imports/', form)`), chemin complet requis. **Ne PAS refaire passer l'upload par `apiClient`.**
- **`refresh` fait foi pour « suis-je connecté ? »**, pas `access` — ce dernier expire en 30 min.
- **Seul un rejet explicite (401/403) ferme la session.** Un `catch` attrapant toute erreur efface les jetons sur un 502 de redéploiement.
- **Le renouvellement mis en commun dans `client.js` est une condition de correction**, pas une optimisation : la liste noire invalide le refresh au premier usage. **Ne pas la retirer.**
- **Onglet navigateur** : titre posé dans `main.jsx` via `import.meta.env.PROD`. Ne pas remettre un titre figé dans `index.html`.

### Tests

- **L'authentification réelle est testée dans `accounts/tests.py` et nulle part ailleurs** : le reste utilise `force_authenticate`, qui court-circuite les classes d'auth.
- **`APIAuthTestCase` authentifie dans `_pre_setup`**, pas `setUp` — les sous-classes n'appellent pas `super()`. Si l'exercice se répète, balayer **deux** motifs : `self.client = APIClient()` **et** `APIClient().get(...)` sans passer par `self.client`.
- **`core/test_runner.py` neutralise TOUT le bloc identité**, pas seulement l'interrupteur. Les oublier laisse des tests passer **pour de mauvaises raisons**.

---

## 8. COMMANDES UTILES

```powershell
# Lancer / arrêter (dev)
docker compose up -d
docker compose down

# Backend
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations <app>
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test            # tous les tests
docker compose exec backend python manage.py test analytics  # une app
docker compose exec backend python manage.py seed_demo       # données de démo
docker compose exec backend python manage.py creer_utilisateur --nom … --mot-de-passe …
docker compose exec backend python manage.py recalculer_mois
docker compose exec backend python manage.py shell

# Frontend
docker compose exec frontend npm install <pkg>
Select-String -Path frontend/package.json -Pattern "<pkg>"   # vérifier la persistance

# Logs
docker compose logs -f backend
docker compose logs -f frontend
```

**Makefile** — cibles non préfixées = **production** (`docker-compose.prod.yml` +
`.env.prod`) ; `dev-*` = développement. `make deploy` = backup → pull → build → up
→ migrate → collectstatic → check. `make reset-db` **détruit le volume `pgdata`**
(confirmation `CONFIRMER` exigée). Pour le dev local on utilise habituellement
`docker compose` directement.

**URLs dev :** front `http://localhost:5173` · API `http://localhost:8000/api/v1/`
· admin `http://localhost:8000/admin/`

### ⚠️ Pousser sur `main` DÉPLOIE EN PRODUCTION

Depuis le 2026-08-12 (ADR-0037), `.github/workflows/ci-cd.yml` vérifie chez
GitHub — ruff, `makemigrations --check`, 493 tests, eslint, images de prod —
puis lance `make deploy` sur un runner auto-hébergé du homelab. Donc
**`make backup` puis `migrate` sur la base réelle, sans que personne ne
regarde.**

```powershell
make lint          # ruff, via Docker — rien à installer
make lint-front    # eslint (exige la stack de dev lancée)
make dev-test      # les 493 tests
```

- **Migration non triviale** (renommage de table, déplacement de modèle, champ
  supprimé dont l'information doit être reportée) → mettre
  **`[sans-deploiement]`** dans le message de commit, puis dérouler `DEPLOY.md`
  à la main.
- Les règles vivent dans `ruff.toml` (racine) et `frontend/eslint.config.js` ;
  la version de ruff est **figée** dans `backend/requirements-dev.txt`.
- ⚠️ `.env.prod` n'est pas versionné : un réglage nouveau se pose sur l'hôte
  **avant** de pousser le code qui le lit.
- 📖 Installation du runner, dépannage : site → *Exploitation / CI/CD*.

---

## 9. FORMAT DE TRAVAIL ATTENDU

- Répondre en **français**, concis et direct.
- Avancer **par module cohérent**, jamais réécrire toute l'app d'un coup.
- **Avant de coder, vérifier la place de la fonctionnalité dans la roadmap** (site).
- Décision d'architecture non triviale → tableau **Option A / Option B / Recommandation / Impact**.
- Tableaux pour comparaisons, décisions, mappings.
- Indicateur financier introduit → préciser sa **fiabilité** (réel / contrôle / estimatif / projeté).
- Distinguer explicitement **arbitrage du foyer** et **règle technique**.
- Demande ambiguë sur un point qui change l'implémentation → **une** question ciblée, sinon implémenter avec l'hypothèse énoncée.
- Pas de sur-ingénierie : **pas de complexité inutile au MVP.**
- Tests unitaires sur chaque règle de calcul ; tests API sur les ressources principales.
- **Décision structurante prise ici → la consigner dans `Documentation/` dans la même passe**, en ADR. Deux dépôts touchés : l'annoncer, et faire **deux commits séparés**.

---

## 10. EXCLUSIONS (ne jamais faire)

- **Pousser une migration non triviale sans `[sans-deploiement]`** : `migrate`
  partirait tout seul sur la base de production.
- **Désactiver un contrôle de la CI pour faire passer une passe.** Le lint,
  `makemigrations --check` et les tests sont les seuls garde-fous entre un
  commit et la production. Corriger le code, jamais la règle.
- Donner un conseil financier personnalisé réglementé, recommander d'acheter/vendre un actif, promettre un rendement.
- Coder une valeur de référence ou un seuil en dur (toujours via référentiel administrable).
- Rendre `solde_theorique`, `solde_reel` ou `ecart_solde` modifiables manuellement.
- Confondre transferts, épargne et dépenses dans les agrégats.
- Supprimer physiquement une donnée financière historique.
- Mettre de la logique métier dans les views ou les serializers.
- Appeler une API externe depuis une view/serializer.
- Stocker une clé API en base.
- Utiliser une donnée de marché instantanée comme vérité comptable.
- Construire le dashboard ou la valorisation de marché avant la stabilisation des fondations.
- Produire des alertes culpabilisantes, non configurables ou non explicables.
- **Créer un accès BudgetTracker → FoyerOS** : le sens est unidirectionnel (suite §4).
- **Ajouter une fonction d'écriture dans `providers/identite.py`** : ce dépôt n'administre pas l'annuaire.
- **Rouvrir une dérogation d'authentification dans `dev.py` ou `prod.py`.**

<!-- Liens du site de documentation -->
[État livré]: https://doc.sternum-lab.duckdns.org/budgettracker/etat-livre/
[Authentification]: https://doc.sternum-lab.duckdns.org/budgettracker/authentification/
[Domaine]: https://doc.sternum-lab.duckdns.org/budgettracker/domaine/
