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
| Auth | **JWT (`djangorestframework-simplejwt`), actif partout depuis août 2026.** Défaut fermé dans `base.py` (`IsAuthenticated`) ; **plus aucune dérogation dans `dev.py` ni `prod.py`**. Voir §5 « Durcissement ». |

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
3. `Mois` (libellé = 1er du mois) est calculé automatiquement depuis `Date_Flux` selon le **mois comptable** du foyer : paramètre administrable `jour_debut_mois_comptable` (référentiel `ParametresBudget`, défaut **1** = mois calendaire). Point unique de vérité : `core/services/periode.py::mois_comptable(date, jour_bascule)`. Convention validée foyer : une période démarrant en fin de mois calendaire porte le libellé du mois qu'elle **finance** (ex. jour de bascule 25 → période 25 juin→24 juillet = mois comptable « juillet », `2026-07-01`). Le jour de bascule est **borné à 28** (valide tous les mois). Tout changement du paramètre → relancer `manage.py recalculer_mois` (remappe les flux + recalc soldes/budgets via signaux).
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

### 🔒 Durcissement — étape 1 : authentification JWT (backend) — LIVRÉE (août 2026)

Première étape du chantier d'interop (cf. §6). **Elle vaut pour elle-même** : elle
solde une dette de sécurité qui n'attendait pas FoyerOS.

**Ce qui n'allait pas :** `DEFAULT_AUTHENTICATION_CLASSES: []` + `AllowAny`
étaient posés dans `dev.py` **et recopiés tels quels dans `prod.py`**. L'API
entière était donc ouverte en écriture à qui atteignait le domaine — n'importe
qui pouvait créer un flux. C'est le mécanisme qui compte, pas l'oubli : **une
dérogation de sécurité vivant dans les fichiers d'environnement finit toujours
par être recopiée dans le mauvais.** Le défaut est désormais fermé dans
`base.py`, et ni `dev.py` ni `prod.py` ne dérogent plus à quoi que ce soit.

- **`simplejwt`** ajouté ; `SIMPLE_JWT` **aligné sur FoyerOS** (access 30 min,
  refresh 7 j, rotation) — les deux applications convergeront vers un service
  d'identité commun, deux politiques de session divergentes seraient une dette
  à payer au moment de la fusion.
- **JWT seul, pas de `SessionAuthentication`** : elle imposerait la vérification
  CSRF sur toutes les écritures d'un client de navigateur, ce que la dérogation
  d'origine cherchait justement à éviter. L'admin Django garde sa session à lui.
- **Routes** — `POST /api/v1/auth/token/`, `POST /api/v1/auth/token/refresh/`,
  `GET /api/v1/auth/me/`. Mêmes chemins que FoyerOS, volontairement.
- **`accounts`** cesse d'être une coquille vide (aucun modèle, aucune vue, aucun
  test depuis l'origine) : `MoiView` + `UtilisateurSerializer`, qui **n'expose ni
  `is_staff` ni `is_superuser`** — un écran qui lit un droit dans l'API finit par
  le croire garanti ; la garantie est au serveur. Test de régression dédié.
- ⚠️ **`AUTH_USER_MODEL` n'a pas bougé** — `User` de Django, identifié par
  `username`. Le basculer sur un modèle sur mesure alors que l'app tourne sur des
  données réelles est l'opération la plus risquée de Django, pour un gain nul :
  rien ici ne rattache d'objet métier à un compte de connexion
  (`Compte.titulaire` pointe un *référentiel*). Divergence avec FoyerOS (email)
  **assumée**, à charge du futur service d'identité.
- **`manage.py creer_utilisateur --nom … --mot-de-passe … [--email] [--admin]`** —
  non interactive, donc utilisable en déploiement, et **idempotente** (relancée,
  elle repose le mot de passe : c'est la porte de secours). Sans elle,
  l'application se verrouillait elle-même dehors au moment où l'API se ferme.
  Elle passe par `AUTH_PASSWORD_VALIDATORS`, jusqu'ici réglés mais **jamais
  appelés** puisque rien ne créait de compte.
  - ⚠️ **`validate_password(user=…)`, jamais sans.** Corrigé après coup :
    `UserAttributeSimilarityValidator` compare le mot de passe aux attributs du
    compte, donc **sans instance il ne compare rien et s'abstient en silence** —
    « pmourret_adm » passait comme mot de passe du compte « pmourret_adm ». La
    moitié du réglage était inopérante sans que rien ne le signale. On passe une
    instance non enregistrée, comme `FoyerOS/accounts/services/comptes.py`.
  - **`--nom` et `--email` permettent tous deux de se connecter** (voir
    « Connexion par email » ci-dessous). L'email reste facultatif ; un compte
    sans adresse ne se connecte que par son identifiant. Relancer la commande
    avec `--email` **ajoute** l'adresse à un compte créé sans.
- **Connexion par email *ou* identifiant** (`accounts/serializers.py::
  ConnexionSerializer`, ajouté à la première mise en service — le premier compte
  créé s'est fait refuser parce que son propriétaire tapait son email). Personne
  ne retient un identifiant technique quand FoyerOS, l'autre application de la
  suite, se connecte par email.
  - **`AUTH_USER_MODEL` n'a toujours pas bougé** : on traduit l'email en
    identifiant *avant* de laisser SimpleJWT authentifier. Rien d'autre ne change.
  - ⚠️ **On ne devine pas à la présence d'un `@`** : un identifiant peut en
    contenir (c'était le cas du compte en question). Règle : si un compte porte
    cette adresse, on prend son identifiant ; sinon la saisie est essayée telle
    quelle. Les deux voies restent ouvertes. Test de régression dédié.
  - **Aucune fuite** : une adresse inconnue tombe en 401 comme un mot de passe
    faux. On ne dit jamais qu'un compte n'existe pas.
  - **L'unicité de l'email est garantie en base** — `accounts/0001_email_unique`,
    index **partiel** et **insensible à la casse**
    (`LOWER(email) WHERE email <> ''`). Sans elle, « se connecter avec son
    email » n'aurait pas de sens : le serveur devrait choisir un compte. Posée en
    base et pas seulement à la création, sinon l'admin Django ou un shell la
    contournent. Partielle parce que l'email est facultatif : un index total
    interdirait un **second** compte sans adresse. `RunSQL` plutôt
    qu'`AddConstraint`, le modèle appartenant à `django.contrib.auth`.
    ⚠️ La migration **échoue s'il existe déjà des doublons** — volontaire :
    lesquels fusionner n'est pas une question qu'une migration peut trancher.
- ⚠️ **`SECRET_KEY` change de nature.** Tant que l'API était ouverte et sans
  session, elle ne protégeait rien ; elle signe désormais **tous les jetons**.
  D'où **`core/checks.py`**, qui la contrôle au démarrage.
  - **Durci en août 2026 : bloquant hors `DEBUG`** (`core.E001`/`E002`),
    simple avertissement en développement (`W001`/`W002`). ⚠️ Le niveau devait
    changer avec l'environnement : un *warning* passe
    `check --deploy --fail-level ERROR`, donc les **20 octets** de cette
    application seraient partis en production sans que rien ne les arrête.
    Bloquer en développement, à l'inverse, n'aurait fait qu'empêcher de
    travailler. Quatre tests fixent la propriété (`core/tests_checks.py`).
  - La clé de dev a été renouvelée (64 caractères). **`.env.prod` reste à
    faire** — le contrôle refusera désormais de démarrer sans.
  - ⚠️ **`core/checks.py` est volontairement dupliqué** dans les trois dépôts :
    la règle de suite interdit de partager du code par copie ou symlink. Un
    paquet versionné sera la bonne réponse quand il y aura plus à mutualiser.
- **`requirements.txt` reconverti en UTF-8** — il était en **UTF-16LE**, soit
  exactement le piège d'encodage listé au §7.

**Tests : 444 (430 + 14).** Le passage a demandé de traiter **33 classes** qui
appelaient l'API :

- **`core/tests_base.py::APIAuthTestCase`** authentifie le client dans
  **`_pre_setup`**, pas dans `setUp`. Délibéré : ces classes définissent déjà
  leur `setUp` et **n'appellent pas `super()`** — une authentification posée dans
  un `setUp` de base aurait été silencieusement inopérante partout. `_pre_setup`
  est appelé par Django avant `setUp` quoi que fasse la sous-classe.
- **Sa limite, rencontrée pour de vrai** : trois `setUp` faisaient
  `self.client = APIClient()`, écrasant le client authentifié — sans effet tant
  que l'API était ouverte. Retiré. Chercher `self.client` ne suffisait pas non
  plus : une classe appelait `APIClient().get(...)` sans jamais passer par
  `self.client`. **Balayer les deux motifs** si l'exercice se répète.
- L'authentification réelle (refus anonyme, jeton, expiration, rotation) est
  testée **dans `accounts/tests.py` et nulle part ailleurs** : le reste de la
  suite utilise `force_authenticate`, qui court-circuite les classes d'auth.

### 🔒 Durcissement — étape 2 : connexion et session côté front — LIVRÉE (août 2026)

L'interface reçoit désormais un jeton et sait le renouveler. L'application
redevient utilisable ; les étapes 1 et 2 se déploient **ensemble**.

- **`stores/authStore.js`** (zustand + `persist`) — jetons en `localStorage`,
  même forme que celui de FoyerOS, moins le foyer courant (ici, une instance
  *est* un foyer). ⚠️ **`refresh` fait foi pour « suis-je connecté ? »**, pas
  `access` : ce dernier expire en 30 minutes, s'y fier renverrait sur l'écran de
  connexion une session parfaitement valide à chaque retour sur l'onglet.
- **`api/client.js`** — injection du `Bearer`, renouvellement **une fois** sur
  401 puis rejeu de la requête. Deux propriétés à ne pas défaire :
  - ⚠️ **Seul un rejet explicite (401/403) ferme la session.** Leçon prise sur
    FoyerOS *avant* d'avoir eu à la réapprendre ici : un `catch` qui attrape
    toute erreur attrape aussi un 502 de redéploiement, et efface les jetons
    pour une panne de deux secondes. Tout le reste est passager — la requête
    échoue, React Query réessaiera.
  - **Le renouvellement est mis en commun** entre les appels parallèles
    (`renouvellement`). Voir l'avertissement sur le blacklistage ci-dessous :
    c'est une économie aujourd'hui, une condition de correction demain.
  - Un 401 sur `/auth/token/` n'est **pas** traité comme une expiration : c'est
    un mot de passe faux, il doit remonter à l'écran.
- **`pages/ConnexionPage.jsx`** — la seule surface accessible sans jeton.
  **Aucune inscription** : un compte naît de `manage.py creer_utilisateur`, côté
  serveur. L'écran distingue « mot de passe refusé » de « serveur injoignable » :
  le premier appelle à retaper, le second à attendre.
- **`App.jsx` : pas de route `/connexion`.** Sans session, l'arbre des pages
  n'est simplement pas construit — une route de plus laisserait les URL profondes
  monter leurs écrans et partir en dix 401 avant la redirection.
- **Déconnexion : jetons effacés *et* `queryClient.clear()`.** Sans le vidage,
  React Query resservirait les comptes et les flux de la session précédente le
  temps que les requêtes se rejouent. Atteignable en bas de la sidebar (desktop)
  **et** dans une carte de `PlusPage` (mobile — la sidebar n'y existe pas, la
  déconnexion serait sinon inatteignable au téléphone).
- **`hooks/useAuth.js`** — `useMoi`, `useConnexion`, `useDeconnexion`. La
  connexion passe par `axios` nu et non `apiClient` : la route qui *crée* la
  session ne doit pas dépendre de l'intercepteur qui suppose une session.

> ⚠️ **Trouvé en vérifiant le contrat : la rotation ne révoque rien.**
> `ROTATE_REFRESH_TOKENS` est actif, mais **`BLACKLIST_AFTER_ROTATION` n'est pas
> posé et l'app `token_blacklist` n'est pas installée**. Constaté, pas supposé :
> rejouer un ancien jeton de rafraîchissement après rotation renvoie **200**. Un
> jeton fuité reste donc valable ses 7 jours pleins, et **se déconnecter ne
> l'invalide pas côté serveur**. FoyerOS a exactement la même limite, assumée et
> documentée chez lui. **À trancher au niveau de la suite** (les deux
> applications doivent décider ensemble) : installer `token_blacklist` donnerait
> une révocation réelle, au prix d'une table de jetons et d'une migration.
> Le jour où c'est fait, la mise en commun du renouvellement dans `client.js`
> devient **obligatoire** — ne pas la retirer d'ici là en la croyant décorative.

> ℹ️ **Non vérifié en navigateur** : l'environnement de développement n'a pas
> d'automatisation. Le contrat HTTP (connexion, rotation, `/auth/me/`, refus
> anonyme) a été validé bout en bout contre le backend réel, et le front
> compile ; le parcours à l'écran reste à cliquer.

### 🔗 Identité partagée — étape 4 : BudgetTracker vérifie (août 2026)

Cadrage : `FamilyToolSuite/FoyerOS/docs/cadrage-identite-partagee.md`.
BudgetTracker devient **vérificateur** des jetons émis par le service
`Identite`. Objectif du chantier atteint : **un compte, un mot de passe, trois
services.**

- **`accounts/annuaire.py::JetonAnnuaire`** — vérifie les jetons **RS256** avec
  la clé **publique** de l'annuaire. ⚠️ **Renvoie `None`** sur tout ce qui n'est
  pas RS256 : DRF s'arrête à la première classe qui **lève**, donc refuser ce
  qu'on ne reconnaît pas empêcherait `JWTAuthentication` d'examiner les jetons
  locaux — et déconnecterait tout le monde.
- **Aucun appel réseau pour vérifier** : la clé est lue au démarrage. C'est ce
  qui permet à BudgetTracker de tourner quand l'annuaire est éteint.
- ⚠️ **`IDENTITE_FOYER` — de quel foyer cette instance est-elle celle ?** Une
  instance par foyer (décision de suite du 2026-08-01) : le claim `foyers` est
  la **seule** chose qui permette de refuser un membre du foyer voisin.
  **Sans ce réglage, aucun jeton d'annuaire n'est accepté** — fermé par défaut
  plutôt qu'ouvert « au cas où ». Test de régression dédié.
- **Provisionnement à la volée, trivial ici** : BudgetTracker n'a **aucune clé
  étrangère vers `User`** — un compte n'y est qu'une porte, le créer ne laisse
  aucune donnée orpheline. ⚠️ **Le rapprochement se fait sur l'email**, pas sur
  `sub` : `auth.User` a une clé primaire entière et ne peut pas porter l'UUID de
  l'annuaire. L'email est unique (index CI partiel, cf. connexion par email) —
  un compte local existant est donc **retrouvé**, jamais dupliqué.
- **`IDENTITE_AUTORITE`** relaie `/auth/token/` et `/refresh/` vers l'annuaire au
  lieu de signer. **Le front n'a pas changé d'une ligne** : envoyer le navigateur
  vers l'annuaire aurait imposé du CORS et une seconde origine pour le même
  résultat. Sous autorité, l'identifiant est **l'email**.
- **Panne ≠ refus** : annuaire injoignable → **503**, jamais 401.
- **`providers/identite.py` ne sait qu'émettre.** ⚠️ Pas de compte de service,
  pas de fonction d'écriture : **BudgetTracker n'administre pas l'annuaire**, les
  comptes naissent dans FoyerOS. Ne pas en ajouter sans rouvrir la décision.
- ⚠️ **`cryptography` ajoutée aux dépendances** : PyJWT ne fait pas de RS256 sans
  elle et **ne le dit qu'à l'exécution** (`InvalidAlgorithmError`, sans nommer le
  paquet). Reconstruire l'image — un `pip install` ne survit pas à `up -d`.
- ⚠️ **`ALLOWED_HOSTS` doit contenir `host.docker.internal`** côté annuaire *et*
  FoyerOS : les piles ont des réseaux Docker distincts, et Django répond sinon un
  **400 DisallowedHost** qui ressemble à un mauvais mot de passe. Rencontré deux
  fois.
- **`core/test_runner.py`** neutralise ces réglages pendant les tests : un test ne
  décrit jamais l'état d'un déploiement. *(Leçon prise côté FoyerOS, où poser
  `IDENTITE_AUTORITE=True` dans un `.env` avait fait échouer 48 tests d'un coup
  en les envoyant sur le réseau.)*
- **17 tests** dédiés, **471 au total**. ✅ Vérifié en réel : un **seul** jeton de
  l'annuaire ouvre l'annuaire, FoyerOS *et* BudgetTracker.

##### Défaut trouvé en usage réel, corrigé le 2026-08-02

🐛 **Un compte d'un autre foyer se connectait, puis tout tombait en 401.**
L'annuaire ne connaît pas `IDENTITE_FOYER` : il délivrait des jetons
parfaitement valides à un membre du foyer voisin, la connexion réussissait, et
**chaque** appel était ensuite refusé — un écran qui s'ouvre, ne charge rien, et
n'explique rien.

- `_refuser_si_autre_foyer` **relit le claim à la connexion** et répond **403**
  avec un message lisible. ⚠️ Ce n'est **pas** la garantie — celle-ci reste à
  l'authentification, qui vérifie la signature à chaque requête. Ce contrôle ne
  fait que le dire **au moment où on peut encore comprendre**.
- Il est donc **tolérant** : un jeton illisible ne bloque pas la connexion.
  Faire échouer une amélioration de confort sur une réponse inattendue en ferait
  une panne. Test dédié.
- L'écran de connexion rend le `detail` du serveur sur un 403, au lieu de son
  message générique « serveur injoignable » — trois refus, trois gestes
  différents : retaper, s'adresser ailleurs, attendre.
- ⚠️ **Le lanceur de tests neutralise TOUT le bloc identité**, pas seulement
  l'interrupteur : `IDENTITE_FOYER` et `IDENTITE_CLE_PUBLIQUE` aussi. Les
  oublier laissait des tests passer **pour de mauvaises raisons**, ou échouer
  selon le `.env` de la machine.

**Reste** : le front de BudgetTracker ne dit pas encore que le mot de passe se
gère dans l'annuaire, et l'écran de connexion parle toujours d'« identifiant ».
Secours si l'annuaire est éteint : **admin Django** (session et mot de passe
locaux) — ne pas supprimer les comptes `pierre` / `pmourret_adm`.

### ✅ Backend — Phases 1 à 8 COMPLÈTES

| App | Contenu livré |
|---|---|
| `core` | `BaseModel` (UUID, soft delete, timestamps). **`services/periode.py`** : découpage en mois comptables — `mois_comptable(date, jour_bascule)`, `bornes_mois_comptable(label, jour_bascule)`, `jour_bascule_actif()`, `mois_comptable_courant()`. Fonctions pures (jour injecté) + lecture du paramètre administrable. Point unique de vérité du « mois » (règle §4.3). |
| `referentiels` | 9 modèles + serializers + commande `seed_demo` (idempotente). ViewSets read-only sauf **`TitulaireViewSet`** et **`EtablissementViewSet`** (passés en `ModelViewSet`) : création/édition possible via API. `code` auto-généré depuis le libellé (`TIT-XXX`, `ETA-XXX`) si non fourni — collision gérée avec suffixe numérique. **Singleton `ParametresBudget`** (`BaseModel`, `jour_debut_mois_comptable` 1–28, défaut 1) : paramètre administrable du mois comptable (`get_solo()` lazy, créé aussi par `seed_referentiels`). `ParametresBudgetSerializer` + `ParametresBudgetView` (`RetrieveUpdateAPIView` singleton, `queryset` requis par les permissions) → `/api/v1/referentiels/parametres-budget/`. Admin enregistré. Migration `0002`. |
| `comptes` | Modèle `Compte` + service de calcul de solde + `CompteViewSet` (ModelViewSet, CRUD complet). `perform_create()` ET `perform_update()` appellent `calculer_solde()` → les trois champs calculés (`solde_theorique`, `solde_reel`, `ecart_solde`) sont corrects dès la création. `solde_reel = solde_initial + Σ(flux dont statut.est_definitif=True)` : se met à jour automatiquement à chaque mutation de flux. **Champ `est_commun`** (Boolean, défaut `False`, éditable via l'API) : marque un compte partagé du foyer (joint), purement informatif — n'affecte aucun calcul. Migration `0002`. Migration `0003` aligne `solde_reel` (`editable=False`). **Champs `est_epargne`** (Boolean, défaut `False`) **et `taux_annuel`** (Decimal %, nullable) (Phase 13, migration `0004` ; data-migration `0005` amorce `est_epargne=True` sur les comptes de type EPARGNE existants — bootstrap ponctuel, la logique lit le flag, jamais le code de type). `est_epargne` marque un compte d'épargne (livret/PEL/PEA…), alimenté par transferts, agrégé dans le bloc analytique `epargne` ; `taux_annuel` est **informatif** au MVP (destiné à la projection des intérêts côté prévisionnel — à venir). Éditables via `CompteFormModal` (case à cocher + champ taux conditionnel) ; badge « Épargne · X % » sur la `CompteCard`. **Champ `code` = NUMÉRO DE COMPTE** (juillet 2026, migration `0006` : `max_length` 20→34 pour IBAN ; unique, requis, pas d'auto-génération) : sert au **rapprochement automatique** des relevés (l'`accountNum` du CSV = `Compte.code`). Front `CompteFormModal` : input labellisé **« N° Compte »**. Ce n'est pas un identifiant technique (la PK reste l'UUID `id`). |
| `categories` | Modèle `Categorie` hiérarchique 2 niveaux (parent/sous_categories) + soft delete protégé. `CategorieSerializer` : champ `code` rendu optionnel (`required=False`), auto-généré par slug depuis `nom` (unique, suffixe `-1`, `-2`… si collision) dans `create()` et `update()`. |
| `flux` | Modèle `Flux` + signals de recalcul de solde. **FK `abonnement`** (`abonnements.Abonnement`, `on_delete=SET_NULL`, nullable, migration `0003`) : trace l'abonnement d'origine quand un flux est généré depuis le référentiel. Le signal `post_save` (si `abonnement_id`) appelle `mettre_a_jour_derniere_occurrence` + `detecter_alerte_divergence_abonnement` (divergence auto → alerte `ABONNEMENT_DIVERGENCE`). Serializer expose `abonnement` (écriture) + `abonnement_nom` (lecture). Champ `est_ajustement` (Boolean, `read_only` dans le serializer) : identifie les flux générés par la réconciliation, exclus de tous les agrégats dépenses/revenus. `_calculer_mois()` délègue à `core.services.periode.mois_comptable` (mois **comptable**, pas calendaire — voir règle §4.3). Service **`services/recalcul_mois.py::recalculer_mois_flux()`** : remappe le `mois` de tous les flux selon le jour de bascule courant (re-save → signaux recalculent soldes/budgets), idempotent, renvoie `{total, modifies}`. Appelé par la commande **`recalculer_mois`** ET automatiquement par `ParametresBudgetView.perform_update` quand le jour change. **`FluxFilterSet`** (django-filter) : `compte`, `categorie`, `type_flux`, `statut`, `titulaire`, `est_transfert`, `est_ajustement`, `date_min`/`date_max`, `mois`, `montant_min`/`montant_max`, **`titulaire_compte`** (= `compte__titulaire`, propriétaire du compte ≠ titulaire du flux souvent nul) et **`est_definitif`** (= `statut__est_definitif` → prévisionnel/validé) ; `SearchFilter` sur `libelle`/`reference_externe`/`notes` ; `OrderingFilter` (`-date_flux` par défaut). **Remboursement (juillet 2026)** : self-FK **`flux_rembourse`** (`on_delete=SET_NULL`, `related_name="remboursements"` → partiels multiples possibles, migration `0004`) trace le lien contre-flux → dépense d'origine. Service isolé **`services/remboursement.py`** (`rembourser_flux(flux, montant, date, libelle=None)` + helpers `montant_deja_rembourse`/`reste_a_rembourser`) : crée une **recette** liée (CREDIT, statut définitif, **même compte/catégorie/devise**, libellé auto « Remboursement — <origine> »), garde-fous `RemboursementInvalide` (refus si transfert/ajustement, si le flux n'est **pas une dépense** montant ≥ 0, si montant ≤ 0 ou **> reste à rembourser**). Le signal `post_save` recalcule le solde (rien de spécial). `FluxViewSet` : action **`POST /flux/{id}/rembourser/`** (`RembourserSerializer` d'entrée `{montant, date, libelle?}` → 201 `{flux, contre_flux}`) + annotation **`montant_rembourse`** (`Coalesce(Sum(remboursements__montant, filter is_deleted=False))`, posée à côté de `est_pointe`). `FluxSerializer` expose `montant_rembourse` + `flux_rembourse` (read-only). Annulation d'un remboursement = suppression normale du contre-flux. Analytics inchangé (même catégorie des deux côtés → net auto) ; le contre-flux est un vrai crédit bancaire → se rapproche naturellement (phase 14). **+9 tests** (`RemboursementAPITest`, suite à 430 OK). |
| `transferts` | Modèle `Transfert` (paire débit/crédit atomique) |
| `budgets` | Modèle `Budget` + calcul de consommation + taux. `perform_create` et `perform_update` dans `BudgetViewSet` appellent `calculer_consommation()` → le taux se recalcule à chaque création ou modification du montant prévu. **Phase 11b-2 :** champs `est_budget_majeur` (Boolean, `read_only`, auto-détecté) et `categories_incluses` (M2M → Categorie). Auto-détection backend : majeure = racine avec au moins une sous-catégorie active. Auto-remplissage des mineures actives à la création. Validations : budget majeur sans mineure → 400 ; conflit majeure/mineure même mois → 400. Service `calculer_consommation` : budget majeur agrège les flux des mineures incluses ; filtre `est_ajustement=False` ajouté. Signal étendu aux budgets majeures incluant la catégorie du flux. **Phase 11c :** modèle `BudgetTemplate` (`BaseModel`, FK unique sur `categorie`, `montant_defaut`, `categories_incluses` M2M, `est_budget_majeur`, `actif`, `notes`) + FK `template` (nullable) sur `Budget`. `BudgetTemplateSerializer` : mêmes auto-détections que `BudgetSerializer`, valide unicité par catégorie, refuse `montant_defaut ≤ 0`. Service `reconduire_vers_mois()` idempotent (ignore budgets déjà existants). `BudgetTemplateViewSet` + action `POST /budget-templates/reconduire/`. Migration `0003`. **43 tests** (dont 15 nouveaux : BudgetTemplate CRUD + `ReconduireServiceTest` 7 cas + `ReconduireAPITest` 3 cas). |
| `abonnements` | **Référentiel** de prélèvements récurrents (refonte juillet 2026 — n'alimente plus le prévisionnel). Modèle `Abonnement` + `AbonnementViewSet`. Propriété **`materialise_ce_mois`** (bool, read_only) = un flux lié existe déjà sur le mois comptable courant (`self.flux.filter(mois=mois_comptable_courant())`) → statut du tableau + désactive le bouton « Générer ». `est_en_retard` conservé (cycle via `derniere_occurrence`+`frequence`). Action **`POST /abonnements/verifier-echeances/`** (`detail=False`, miroir `/patrimoine/verifier-rappels/`) : génère les alertes `ABONNEMENT_EN_RETARD` des actifs, idempotent, renvoie `{crees}`. La divergence n'est plus une action manuelle : elle est détectée **automatiquement** à la génération du flux (signal flux). Workflow : créer l'abonnement → à l'échéance, générer le flux au clic (FK `Flux.abonnement`) → budgétiser via la catégorie. **Analyse dédiée** (juillet 2026) : voir `analytics/services/abonnements.py` + endpoint `/api/v1/analytics/abonnements/` (coût mensuel/annuel normalisé, par catégorie, qui paye quoi, poids budget, dérive de prix, à-risque). |
| `alertes` | Alertes auto (budget, solde bas, retard abonnement, divergence, écart solde, **valorisation à faire**) + acquittement |
| `patrimoine` | `Actif` estimatif + `HistoriqueValorisation` (granularité fine) + service de valorisation + rappels de re-valorisation |
| `analytics` | Service `dashboard.py` (agrégats) + `DashboardView` (APIView) + serializer + 14 tests. Inclut `_calculer_depenses_par_categorie(mois)` : agrégation SQL par catégorie majeure (mineures regroupées sous leur parent, triées par montant décroissant). Champ `depenses_par_categorie` ajouté au `DashboardSerializer`. Filtre `est_ajustement=False` appliqué sur tous les agrégats (revenus, dépenses, catégories). **Phase 10-A (prévisionnel)** : services `projection.py` (`calculer_solde_projete`, `calculer_capacite_restante`, `calculer_previsionnel` + `reste_a_depenser_budgete`) et `trajectoire.py` (`calculer_trajectoire`), `PrevisionnelView` (APIView) + `PrevisionnelSerializer`. Lecture seule stricte, aucun modèle persisté, aucune migration. **⚠️ Refonte juillet 2026 : les abonnements NE nourrissent PLUS le prévisionnel** (devenus un référentiel matérialisé en flux). `solde_projete = solde_actuel + flux_futurs_mois − reste_a_depenser_budgete` ; `capacite = total_budgets − total_consomme` ; trajectoire mois futurs = flux datés + enveloppes `BudgetTemplate` (plus d'échéances d'abonnement). Champs `abonnements_a_echoir_non_budgetes`/`abonnements_restants` retirés des composantes. **Dashboard par compte** : `_calculer_depenses_par_categorie(mois, compte_id=None)` rendu scopable (rétrocompatible), service `compte_dashboard.py` (`calculer_compte_dashboard(compte_id, aujourd_hui=None)`, `aujourd_hui` injectable) → soldes du compte + métriques du mois (dépenses/revenus/épargne/nb_flux, transferts & ajustements exclus) + ventilation par catégorie scopée + top 5 dépenses, `CompteDashboardView` + `CompteDashboardSerializer`, route `analytics/compte/<uuid>/`, **+9 tests** (`CompteDashboardServiceTest` + `CompteDashboardAPITest`, 44 tests analytics). **Heatmap dépenses** : `_calculer_depenses_par_jour(mois)` → liste `[{date, total}]` (dépenses du mois ventilées par jour, valeur absolue, transferts/ajustements exclus, fiabilité réelle), champ `depenses_par_jour` ajouté au `DashboardSerializer`, +2 tests. **Navigation mensuelle** : `calculer_dashboard(nb_mois, mois=None)` accepte un mois comptable cible (libellé 1er du mois) ; tous les blocs mensuels (métriques, dépenses par catégorie, heatmap, budgets, derniers flux, **solde total = fin du mois sélectionné** via `_solde_fin_de_mois`, courbe d'évolution se terminant au mois affiché) suivent ce mois. Valeur bornée à `[mois_min, mois_max]` (premier mois ayant des flux → mois comptable courant ; pas de navigation dans le futur, le dashboard reste un agrégat RÉEL). Champs `mois_min`/`mois_max` ajoutés à la réponse. `DashboardView` lit `?mois=YYYY-MM-DD`. +4 tests (50 tests analytics). |
| `imports` | **Rapprochement bancaire (Phase 14-A, juillet 2026)** — confronte un relevé bancaire (BoursoBank) aux flux de l'app pour repérer oublis/erreurs de saisie. **Lecture seule vis-à-vis des flux** : ne crée ni ne modifie aucun flux, l'app reste la vérité. Parsers isolés `imports/parsers/` (`base.py` : format pivot `LigneBrute` + `hash_dedup` + `decoder_fichier` UTF-8/BOM/cp1252 ; `boursobank.py` : `;`, décimale FR virgule, milliers `"1 850,00"` espaces insécables + guillemets, 2 dates, lignes illisibles non bloquantes). Modèles `ImportBancaire` (lot rattaché à 1 `compte`, `banque`, `compte_num_source`, compteurs de rapport) + `LigneBancaire` (miroir persisté + `hash_dedup` indexé **sans unicité dure** + `statut` `StatutRapprochement` en_attente/rapproche/manquant_app/ambigu/ignore + FK `flux` nullable). Migration `imports/0001`. **`ImportBancaire.delete()` cascade le soft delete sur ses lignes** (sinon leurs hash resteraient comptés → anti-doublon faussé, ré-import bloqué). Service `services/rapprochement.py` : **pur** `filtrer_doublons` (anti-doublon par comptage d'occurrences), `apparier` (matching **STRICT** : passe 1 montant+date exacts → passe 2 tolérance ± N jours avec propagation de contraintes → reliquat `manquant_app`/`ambigu`) ; **DB** `executer_rapprochement`, `candidats_pour`, `valider_ligne`/`rejeter_ligne` (`ValidationInvalide`), `flux_orphelins` (flux app sans ligne banque, qualifiés `previsionnel_non_passe`/`erreur_saisie_probable`), `controle_solde` (solde relevé `accountbalance` vs `solde_initial + Σ flux définitifs ≤ date`, comparaison exacte au centime, fiabilité **contrôle**), `construire_rapport`. Virements : le flux `est_transfert` a le bon montant/date → rapproché naturellement (aucun parsing du libellé VIR) ; `est_ajustement` exclus du vivier. Service d'orchestration `services/creation.py::creer_import` (décoder→parser→vérif mono-compte `FichierMultiCompteError`→anti-doublon→lot+lignes bulk→rapprochement). Tolérance de date = **paramètre administrable** `ParametresBudget.tolerance_jours_rapprochement` (défaut 3, migration `referentiels/0005` ; règle 1, jamais en dur). **14-B** : `creer_flux_depuis_ligne` (seule écriture de flux du module — crée le flux manquant + rattache la ligne, `reference_externe` = trace lisible), `flux_ids_deja_pointes` (anti-re-match : flux pointés par un autre lot exclus du vivier), badge `est_pointe` annoté sur `FluxViewSet`/`FluxSerializer`. **48 tests** (parser, matching pur, orchestration DB, contrôle de solde, création de flux + anti-re-match, API multipart). |

**Endpoints clés :**
- CRUD ressources : `/api/v1/comptes/`, `/categories/`, `/flux/`, `/transferts/`, `/budgets/`, `/budget-templates/`, `/abonnements/`, `/alertes/`, `/patrimoine/`
- Référentiels (lecture seule sauf Titulaire et Etablissement) : `/api/v1/referentiels/...`
- Paramètres du foyer (singleton, GET + PATCH) : `/api/v1/referentiels/parametres-budget/` → `{ jour_debut_mois_comptable, valeur_point, tolerance_jours_rapprochement }` (`jour_debut_mois_comptable` 1–28 défaut 1 ; `tolerance_jours_rapprochement` 0–31 défaut 3, fenêtre de rapprochement bancaire). Pilote le découpage en mois comptables. **Le PATCH remappe automatiquement tout l'historique des flux** si le jour change (`ParametresBudgetView.perform_update` → `flux/services/recalcul_mois.py::recalculer_mois_flux()`) : l'UI n'a pas à lancer la commande à la main.
- Patrimoine : `/patrimoine/total/`, `/patrimoine/historique/?nb_mois=12`, `/patrimoine/verifier-rappels/` (POST)
- Dashboard : `/api/v1/analytics/dashboard/?nb_mois=6` (option `&mois=YYYY-MM-DD` pour naviguer dans l'historique ; réponse inclut `mois_min`/`mois_max` ; mois borné à [premier mois avec flux, mois courant])
- Dashboard par compte : `/api/v1/analytics/compte/<uuid>/` (lecture seule, fiabilité réelle ; blocs `compte`, `metriques`, `depenses_par_categorie`, `top_depenses` du mois courant scopés au compte ; 404 si compte inconnu)
- Prévisionnel (10-A) : `/api/v1/analytics/previsionnel/?nb_mois=6` (3 blocs `solde_projete`, `capacite_restante`, `trajectoire`, chacun avec `fiabilite` + `definition`)
- Analyse rétrospective (Phase 13) : `/api/v1/analytics/analyse/?nb_mois=6` (fenêtre glissante 3/6/12/24 mois comptables, lecture seule, **fiabilité RÉELLE**, transferts + ajustements exclus). 6 blocs : `tendances` (série mensuelle dépenses/revenus/épargne/taux + `totaux_periode`, `moyennes_mensuelles`, `comparaison_periode_precedente` neutre N vs N-1), `epargne` (épargne réellement mise de côté = **versements nets** (transferts) vers les comptes `est_epargne` : `encours_total` stock, `versements_par_mois` net + cumul, `ecart_budgetaire` épargne budgétaire rev−dép vs versement réel, `par_compte` encours+versements+`taux_annuel` ; le taux est informatif, pas encore projeté), `titulaires` (ventilation par propriétaire de compte : `par_titulaire` = {nom, est_commun, depenses, revenus, epargne_nette, part_depenses_pct} + `commun_vs_perso` ; **comptes communs = bucket « Commun » distinct**, jamais rattaché à une personne — arbitrage foyer), `categories` (par catégorie majeure : `total_periode`, `moyenne_mensuelle`, `part_pct`, `serie` mensuelle ; mineures agrégées sous parent), `rythme` (`par_jour_semaine` 1=lundi…7=dimanche + `libelles_recurrents` ≥2 occurrences), `saisonnalite` (comparaison année sur année sur **tout l'historique** : `comparaisons` = {mois, depenses, depenses_an_precedent, variation_pct} pour chaque mois **clôturé** ayant un homologue année-1 ; mois courant partiel exclu). Service `analytics/services/analyse.py::calculer_analyse(nb_mois, aujourd_hui=None)`, **aucune projection** (le prévisionnel reste séparé). **24 tests**.
- Analyse des abonnements : `/api/v1/analytics/abonnements/?nb_mois=6` (lecture seule ; **base référentiel = estimatif** pour synthese/par_categorie/par_titulaire, **réel** pour derive_prix/a_risque). Périmètre : abonnements **actifs de dépense** (`montant_attendu < 0`) uniquement ; fréquences ponctuelles (`nb_jours` null) exclues des totaux (comptées dans `nb_actifs`, pas `nb_recurrents`). 5 blocs : `synthese` (coûts normalisés `total_mensuel`/`total_annuel` via `nb_jours` — facteurs `30.4375`/`365.25` —, `poids_depenses_pct`/`poids_revenus_pct` = total mensuel abos ÷ moyennes RÉELLES sur `nb_mois`, liste `abonnements` triée par coût), `par_categorie` (regroupement par catégorie majeure, mineures sous parent, bucket « Sans catégorie » ; `total_mensuel`/`total_annuel`/`part_pct`/`nb` + liste `abonnements` détaillée par catégorie pour le modal), `par_titulaire` (« qui paye quoi » par `compte.titulaire`, **bucket « Commun » distinct** pour `est_commun` — même arbitrage que l'Analyse ; chaque bucket embarque une liste `abonnements` détaillée = {id, nom, categorie_nom, compte_id, compte_nom, compte_est_commun, cout_mensuel, cout_annuel, montant_attendu, frequence_libelle} pour un modal cliquable → repérer ce qui pourrait basculer en compte commun), `derive_prix` (dernier flux réel lié via FK `Flux.abonnement` vs `montant_attendu` → `ecart_pct`, `en_divergence` si > `seuil_divergence_pct` ; n'inclut que les abos ayant ≥1 flux), `a_risque` (motifs `en_retard`/`divergence_montant`/`jamais_genere`, signalétique — **aucune alerte créée**). Service `analytics/services/abonnements.py::calculer_abonnements(nb_mois, aujourd_hui=None)`. **16 tests** (`AbonnementsServiceTest` 14 + `AbonnementsAnalyseAPITest` 2). **Drill-down généralisé** : chaque agrégat (`synthese`, `par_categorie`, `par_titulaire`) embarque sa liste `abonnements` détaillée → modal cliquable front ; les blocs déjà itémisés (`derive_prix`, `a_risque`) exposent l'`id` d'abo. Côté front, un modal générique (`AbonnementsDetailModal`) + une ligne réutilisable (`AboLine`) avec bouton Éditer (ouvre `AbonnementFormModal` → changer de compte / résilier) sont branchés partout. `abonnements` (re)dépend de `'analytics'` dans `RESOURCE_DEPENDENCIES` (une mutation d'abo rafraîchit l'analyse).
- Rapprochement bancaire (Phase 14-A) : `POST /api/v1/imports/` (**multipart** `banque` + `fichier` + `compte` **optionnel** → parse+dédup+rapprochement, renvoie `{lot, nb_doublons, erreurs_parsing}` ; **si `compte` omis, résolution automatique via l'`accountNum` du fichier = `Compte.code`** → 400 `CompteIntrouvableError` avec `compte_num` si aucun compte ne porte ce numéro ; 400 aussi sur format invalide, banque non supportée, ou **fichier multi-comptes** avec la liste des `accountNum`), `GET /api/v1/imports/{id}/rapport/` (rapport détaillé : `controle_solde`, `lignes:[{statut, flux_detail, candidats:[FluxResume]}]`, `flux_sans_ligne:[{...FluxResume, motif}]`), `POST /api/v1/imports/{id}/relancer/`, `DELETE /api/v1/imports/{id}/` (soft delete cascadé). Lignes : `GET /api/v1/imports-lignes/{id}/candidats/`, `POST /api/v1/imports-lignes/{id}/valider/` (body `{"flux_id": ...}`), `POST /api/v1/imports-lignes/{id}/rejeter/`, **`POST /api/v1/imports-lignes/{id}/creer-flux/`** (14-B, body `{"categorie": ..., "libelle"?: ...}` → 201 `{ligne, flux}` ; crée le flux manquant et rattache la ligne).
- Actions custom : `/abonnements/{id}/verifier-divergence/`, `/patrimoine/{id}/valoriser/`, `/alertes/{id}/acquitter/`, `/alertes/acquitter-tout/`, `/budget-templates/reconduire/` (POST, body `{"mois": "YYYY-MM-DD"}`), **`/flux/{id}/rembourser/`** (POST, body `{montant, date, libelle?}` → 201 `{flux, contre_flux}` ; crée le contre-flux recette qui rembourse tout ou partie d'une dépense)

### ✅ Frontend — Phase 9 COMPLÈTE

Toutes les pages sont en Tailwind v4 + dark mode complet :

| Page | Route | État |
|---|---|---|
| Dashboard | `/dashboard` (+ `/` redirige ici) | ✅ métriques, courbe solde (sélecteur 3/6/12M), **dépenses par catégorie** (DoughnutChart + légende expandable majeures/mineures, **drill-down** : clic sur une catégorie-feuille → `FluxCategorieModal` listant les flux du mois avec compte d'origine), **calendrier des dépenses** (`HeatmapDepenses` : grille calendaire compacte du mois — hauteur de cellule fixe `h-12 sm:h-14`, pas `aspect-square` —, intensité rouge par jour **plafonnée au 90e centile** pour ne pas écraser l'échelle sur un gros flux, jours à venir atténués, **drill-down** : clic/Entrée sur un jour dépensé → `FluxJourModal` listant les dépenses du jour), budgets, derniers flux, alertes, bloc patrimoine estimé séparé. **Navigation mensuelle** : flèches ‹ › autour du libellé du mois (state `mois`, query key `['analytics','dashboard',nbMois,mois]`, `placeholderData: keepPreviousData` pour éviter le flash de toute la page) → recharge le dashboard sur mois −1/+1, bornées par `mois_min`/`mois_max` renvoyés par l'API (flèches désactivées aux bornes, pas de futur) |
| Comptes | `/comptes` | ✅ CRUD complet : `CompteFormModal` (création + édition — `solde_reel` non saisi, calculé automatiquement), boutons Éditer/Supprimer sur chaque carte, gestion du 400 « compte lié à des flux » avec lien « Désactiver à la place », création inline de Titulaire et Établissement. Affichage carte : « Solde confirmé » (= `solde_reel`) + « En attente » (= `ecart_solde`, négatif si dépenses prévisionnelles). Case à cocher **« Compte commun (partagé du foyer) »** (création + édition) → badge violet **« 👥 Commun »** sur la `CompteCard` et suffixe ` · Commun` dans les libellés de comptes des selects (`FluxFormModal`, `AbonnementFormModal`). **Bouton « Voir les transactions » (icône `BarChart3`)** sur chaque carte → page détail du compte. |
| Compte (détail) | `/comptes/:id` | ✅ Dashboard scopé à un compte (lecture seule) : en-tête (établissement, badges Commun/désactivé), soldes (théorique/confirmé/en attente), métriques du mois (dépenses/revenus/épargne/nb mouvements), **dépenses par catégorie en histogramme (`BarChart`) + donut/légende dépliable** (`DepensesCategories` partagé avec le Dashboard), **top dépenses du mois**, puis **section « Flux du compte » = `FluxSearchPanel` scopé** (`baseParams={{compte:id}}`, `hideCompteFilter`) → recherche + filtres + chargement paginé + **édition des flux directement depuis le compte** (remplace l'ancienne table lecture seule `?compte=<id>&page_size=1000`). Hook inline `useCompteDashboard` (query key `['analytics','compte',id]`, couverte par l'invalidation préfixe `'analytics'`). |
| Flux | `/flux` | ✅ CRUD complet + **recherche multi-critères** via **`FluxSearchPanel`** (composant partagé) : recherche texte debouncée (libellé/référence/notes), filtres Compte, **Propriétaire du compte**, Catégorie (groupée), Statut (Validé/Prévisionnel), Sens (Dépense/Recette), plage de dates ; bouton Réinitialiser. **Chargement dynamique paginé** (`useInfiniteResource` → suit le `next` DRF ; IntersectionObserver + bouton « Charger plus ») : corrige le bug où seuls les 50 premiers flux se chargeaient (mois anciens inaccessibles). `FluxFormModal` (création + édition), table desktop (Actions au hover) / cards mobile, bloc transfert protégé (message + redirection). `type_flux` auto-dérivé du sens (Dépense → DEBIT, Recette → CREDIT). Badges « Transfert »/« Ajustement » (amber) ; bouton Supprimer masqué sur ces flux ; `FluxFormModal` bloque leur édition. **Remboursement (juillet 2026)** : bouton **« Remboursé »** (`Undo2`) sur chaque dépense non-transfert/ajustement pas encore totalement remboursée → `RemboursementModal` (pré-remplie montant = reste à rembourser, date = aujourd'hui, libellé optionnel ; ajustable → gère partiels + vraie date du crédit). Badges **« Remboursé »** (vert, Σ ≥ \|montant\|) / **« Remboursé partiellement »** (amber) sur la dépense, **« Remboursement »** (teal) sur le contre-flux recette. Hook `useRembourserFlux` (`useResource.js`). L'annulation d'un remboursement = bouton Supprimer du contre-flux (libellé « Annuler le remboursement »). Helpers `statutRemboursement`/`peutEtreRembourse`, badge `RemboursementTag`, tone `green` ajouté au composant `Tag` interne. |
| Transferts | `/transferts` | ✅ Création + annulation : `TransfertFormModal` (compte source/destination, montant, date, statut — défaut « Validé »/`est_definitif`, notes) → `POST /transferts/` (la paire débit/crédit atomique est gérée backend ; le front envoie `type_flux_debit`=DEBIT, `type_flux_credit`=CREDIT, `devise` par défaut). `TransfertCard` affiche `source → destination`, montant, date ; bouton Annuler → `DELETE /transferts/{id}/` (soft delete des deux flux, recalcul des soldes). **Pas d'édition** (un transfert se supprime/recrée, miroir du viewset back). Accessible Sidebar (icône `Repeat`) + menu Plus. C'est le **seul** moyen UI d'alimenter un compte d'épargne (un Flux normal ne touche qu'un compte et serait compté en dépense/recette). |
| Budgets | `/budgets` | ✅ CRUD complet + budgets intelligents (11b-2) + budgets répétables (11c) : `BudgetFormModal` (cases à cocher mineures, majeure accessible via `Nom — budget global`). `BudgetCard` affiche les mineures incluses + icône RecycleArrow si issu d'un template. Onglets **"Ce mois"** / **"Modèles"** : `BudgetTemplateFormModal` (création + édition, catégorie désactivée en édition, toggle actif), `TemplateCard` (CRUD), bouton **"Reconduire sur Mois"** → `POST /budget-templates/reconduire/` → message de confirmation + bascule sur l'onglet Ce mois. Bouton Reconduire aussi dans l'EmptyState du mois si des templates existent. |
| Abonnements | `/abonnements` | ✅ **Onglets Liste / Analyse.** **Refonte juillet 2026 : tableau (façon Flux) + génération de flux au clic.** Barre de filtres serveur (recherche debouncée, compte, catégorie groupée, fréquence, état actif) → params `useResourceList('abonnements', params)`. Table desktop / cards mobile, colonnes Nom · Compte · Catégorie · Montant · Fréquence · Échéance · **Statut** (`Généré ce mois` / `À générer` / `En retard` / `Inactif`) · Actions. Bouton **« Générer le flux » (`FilePlus`)** → ouvre `FluxFormModal` pré-rempli (compte, catégorie, montant, `date_flux`=jour d'échéance du mois, statut par défaut Validé mais **modifiable**, FK `abonnement`) ; désactivé si inactif ou déjà généré ce mois. Appelle `verifier-echeances` au montage (comme `PatrimoinePage`/rappels). **Plus de modal « Vérifier divergence »** (divergence désormais automatique à la génération). `AbonnementFormModal` (CRUD) inchangé. |
| Alertes | `/alertes` | ✅ filtres chips + acquittement |
| Patrimoine | `/patrimoine` | ✅ CRUD complet : `ActifFormModal` étendu (création + édition), boutons Éditer/Supprimer sur chaque `ActifCard`, toggle « actif » en édition |
| Catégories | `/categories` | ✅ CRUD complet : `CategorieFormModal` (majeure ou mineure selon `parentId`), accordéon (majeures → clic → mineures). Boutons Éditer/Supprimer ; si 409 (flux liés) → propose de désactiver. Accessible depuis Sidebar + menu Plus. |
| Prévisionnel | `/previsionnel` | ✅ **Phase 10-A front** : 3 cartes (solde projeté fin de mois avec décomposition en briques réel/engagé/estimé/récurrent ; capacité à dépenser restante + jauge ; trajectoire d'épargne `LineChart`, sélecteur 3/6/12M). `FiabiliteBadge` (elevee=vert, moyenne=ambre, faible=gris) mappé sur la valeur API. Fiabilité dégressive de la trajectoire rendue par coupure plein/pointillés gris dérivée du champ `fiabilite` de chaque point (aucun seuil front). États skeleton/ErrorState (pas d'early return)/EmptyState. Accessible Sidebar (icône `TrendingUp`) + menu Plus. Wording « projeté », jamais vérité comptable. |
| Analyse | `/analyse` | ✅ **Phase 13** : vue analytique rétrospective (lecture seule, réel). `PeriodSelector` 3/6/12/24M. Bloc **Tendances** (3 tuiles récap revenus/dépenses/épargne avec moyenne/mois + `VariationChip` neutre gris vs période précédente ; `BarChart` groupé dépenses/revenus par mois). Bloc **Épargne** (`EpargneCard` : stats encours total + versé sur la période ; `BarChart` groupé épargne budgétaire vs réellement versé ; `LineChart` cumul versé ; liste par livret avec badge taux + encours ; message d'invitation si aucun compte `est_epargne`). Bloc **Répartition par titulaire** (`TitulairesCard` : liste par personne avec barre de part %, dépenses + épargne ; badge violet **« Commun »** pour le bucket des comptes joints ; barre bicolore **Commun vs perso**). Bloc **Catégories dans le temps** (`BarChart` empilé top 7 majeures + « Autres » ; liste avec pastille couleur `CAT_PALETTE`, barre de part %, moyenne/mois, total). Bloc **Rythme** (`BarChart` par jour de semaine + table des postes récurrents). Bloc **Comparaison à l'année précédente** (`SaisonnaliteCard` : YoY sur tout l'historique — `LineChart` deux séries « Cette année »/« Année précédente » + liste des 12 derniers mois clôturés avec Δ neutre ; message dédié si <13 mois d'historique). Hook `useAnalyse.js` (query key `['analytics','analyse',nbMois]`, couverte par le préfixe `'analytics'`). Accessible depuis un **lien dans l'en-tête du Dashboard** (icône `ChartColumn`) + Sidebar + menu Plus. États skeleton/ErrorState/EmptyState (pas d'early return). `BarChart` étendu (prop `stacked` + légende auto si >1 série). |
| Paramètres | `/parametres` | ✅ Réglages du foyer. Carte **« Mois comptable »** : `Select` jour de bascule (1–28, label spécial « 1 — mois calendaire »), exemple de période dynamique, avertissement si modifié (recalcul de tout l'historique), bouton Enregistrer (désactivé si inchangé/en cours) + feedback succès/erreur, `Tooltip` `DEFINITIONS.mois_comptable`. Hook dédié `useParametres.js` (`useParametres` GET + `useUpdateParametres` PATCH → invalide `flux`/`comptes`/`budgets`/`alertes`/`analytics` car le `mois` de tous les flux change). Le remap est fait backend au PATCH (pas de bouton séparé). Accessible Sidebar (icône `Settings`) + menu Plus. États Loading/Error (pas d'early return). Page extensible pour de futurs réglages. |
| Rapprochement | `/imports` | ✅ **Phase 14-A** : rapprochement bancaire (lecture seule). `ImportUploadModal` (banque + fichier CSV + **compte optionnel** — laissé vide, il est détecté via le N° de compte du fichier ; message dédié si `compte_num` introuvable ; upload **multipart** `FormData`, le compte n'est pas envoyé s'il est vide). Liste des lots dépliables (`LotCard`, badges compteurs, **bouton corbeille** → `useDeleteImport`, `window.confirm`, soft delete cascadé ; désélectionne si le lot ouvert est supprimé). **14-B** : bouton **« Créer »** (`FilePlus`) sur chaque ligne `manquant_app` → `CreerFluxModal` (catégorie requise, libellé éditable, montant/date figés, avertissement si libellé ~ « VIR ») → crée le flux + rapproche ; badge **« Pointé »** (teal) sur la page Flux (`FluxSearchPanel`, champ `est_pointe`). `RapportView` : bandeau **`ControleSolde`** (relevé vs app à la date, vert si concordant / ambre sinon, `Tooltip DEFINITIONS.controle_solde_import`), puis **3 sections** — « À valider » (ambigus `AmbiguRow` avec candidats + boutons valider ✓ / rejeter), « Écarts à corriger » (`manquant_app` = absent de l'app + orphelins `erreur_saisie_probable` = absent du relevé), « En attente (normal) » (orphelins `previsionnel_non_passe`), « Rapprochés » (repliable). Hook dédié `useImports.js` (`useImportsList`, `useRapport(lotId)`, `useUploadImport`, `useValiderLigne`, `useRejeterLigne`, `useRelancerRapprochement` — invalidation préfixe `['imports']`, hors `useResource` générique car upload multipart + rapport calculé). Accessible Sidebar (icône `FileUp`) + menu Plus. |
| Plus | `/plus` | ✅ menu mobile (accès **Analyse**/Prévisionnel/Comptes/Abonnements/Patrimoine/**Rapprochement**/Catégories/**Paramètres**) + toggle thème |

**Composants UI** (`src/components/ui/`) : `Button`, `Card`, `Input`, `Select` (prop `groups` pour `<optgroup>` natifs), `Modal`, `States` (Loading/Error/Empty), `Badge`, `IconBadge`, `PeriodSelector` (sélecteur 3/6/12M partagé, extrait du Dashboard et réutilisé par Dashboard + Prévisionnel), `Tooltip` (info-bulle d'aide : petite icône « i » révélée au **survol ET au clic/tap** — utilisable en tactile ; ferme au clic extérieur / Échap ; prop `align` `left`/`center`/`right` contre les débordements de bord ; dark mode via variables sémantiques ; props `titre`/`texte`/`formule`, alimenté par `DEFINITIONS`).

**Infos-bulles d'aide (passe transversale, juin 2026)** : tous les indicateurs calculés portent une bulle expliquant **ce que le chiffre représente** ET **comment il est calculé** (formule). Les textes sont **centralisés** dans `src/constants/definitions.js` (objet `DEFINITIONS`, une entrée = `{ titre, texte, formule }`), jamais codés au point d'usage. Usage : `<Tooltip {...DEFINITIONS.solde_total} align="left" />`. Couverture : Dashboard (Solde total, Dépenses/Revenus du mois, Épargne nette, titres « Dépenses par catégorie » + « Patrimoine estimé »), Comptes (Solde théorique/confirmé/En attente — métriques **et** cartes), Budgets (Total prévu/consommé, Reste, taux, badge « Global »), Patrimoine (Total estimé, Plus-value latente), Abonnements (Total mensuel estimé, En retard, Seuil de divergence), Prévisionnel (4 briques du solde projeté + titres des cards, en complément du `definition` déjà renvoyé par l'API). **Toute nouvelle métrique doit ajouter son entrée dans `definitions.js`** et préciser la fiabilité (réel / estimatif / projeté) quand c'est pertinent — pas de texte d'aide en dur.
**Charts** (`src/components/charts/`) : `chartSetup.js` (palette `CAT_PALETTE` 12 couleurs dans DashboardPage), `LineChart`, `BarChart`, `DoughnutChart`, `DepensesCategories` (donut + légende dépliable + drill-down via props `mois`/`compteId`), `HeatmapDepenses` (calendrier compact des dépenses du mois, props `data`=`depenses_par_jour`/`mois`/`compteId` optionnel ; échelle plafonnée au 90e centile, jours futurs atténués, cellule cliquable avec drill-down). Les deux drill-downs ouvrent des modaux de `src/components/flux/` qui réutilisent l'endpoint `/flux/` — aucun nouvel endpoint : `FluxCategorieModal` (filtres `categorie`+`mois`+`est_transfert`, +`compte` si scopé) pour le donut ; `FluxJourModal` (filtres `date_min`=`date_max`+`est_transfert`, +`compte` si scopé, dépenses seules) pour la heatmap.
**Layout** (`src/components/layout/`) : `Layout`, `Sidebar` (desktop, inclut Catégories + Prévisionnel + Paramètres), `BottomNav` (mobile <640px), `ThemeToggle` (variants `dark`/`light`).
**Composants Catégories** (`src/components/categories/`) : `CategorieFormModal` (prop `parentId` = création mineure ; prop `categorie` = édition).
**Composants Prévisionnel** (`src/components/previsionnel/`) : `FiabiliteBadge` (mappe `elevee`/`moyenne`/`faible` → variantes Badge `success`/`avertissement`/`neutre`). Hook dédié `usePrevisionnel.js` (query key `['analytics', 'previsionnel', nbMois]`, couverte par l'invalidation préfixe `'analytics'`).

**Dark mode :** variables CSS sémantiques dans `index.css` (`@theme` clair + bloc `.dark`) : `--color-surface`, `--color-surface-2/3`, `--color-border-app`, `--color-content`, `--color-content-2/3`, `--icon-badge-bg/fg`. Store Zustand `themeStore.js` (modes `system`/`light`/`dark`, persistance `localStorage`, écoute `prefers-color-scheme`). Les couleurs métier (rouge/vert/ambre/violet) restent identiques dans les deux thèmes ; seules surfaces et textes changent.

**Hooks** (`src/hooks/`) : `useResource.js` (`useResourceList(resource, params, options)` — `options` est étalé dans `useQuery` (ex. `{ enabled }` pour ne pas charger un modal fermé), **`useInfiniteResource(resource, params, options)`** (chargement paginé à la demande via `useInfiniteQuery` — suit le champ `next` de la pagination DRF ; query key `[resource,'infinite',params]`, couverte par l'invalidation préfixe `[resource]`), `useResourceDetail`, `useCreateResource`, `useUpdateResource`, `useDeleteResource`, `useResourceAction` + `RESOURCE_DEPENDENCIES` pour invalidations croisées), `useReferentiels.js` (9 hooks lecture + `useCreateTitulaire`, `useCreateEtablissement`), `useParametres.js` (`useParametres` GET + `useUpdateParametres` PATCH du singleton `ParametresBudget`, hors `useResource` car ressource unique sans id), `useMediaQuery.js` (`useIsMobile`, breakpoint 640px), **`useDebouncedValue.js`** (`useDebouncedValue(value, delay=350)` — stabilise une valeur pour la recherche texte, évite une requête à chaque frappe).

**Composants Flux** (`src/components/flux/`) : **`FluxSearchPanel`** (panneau recherche + filtres + liste paginée + édition, **partagé par FluxPage et CompteDetailPage**). Props : `baseParams` (filtres fixes fusionnés à chaque requête, ex. `{compte:id}`), `hideCompteFilter` (masque le select Compte quand scopé à un compte), `enableCreate` (affiche « + Nouveau flux »). Gère son propre état de filtres, la recherche debouncée, l'`useInfiniteResource('flux', params)`, la table/cards responsive et le `FluxFormModal` (création + édition). Filtres → query params : `search`, `compte`, `titulaire_compte`, `categorie`, `est_definitif`, `date_min`/`date_max`, et le **Sens** dérivé du signe du montant (`montant_max=-0.01` pour Dépense, `montant_min=0.01` pour Recette — pas de requête `type_flux` supplémentaire). `FluxFormModal`, `FluxCategorieModal`, `FluxJourModal` (drill-downs dashboard) vivent aussi ici.
**Composants Comptes** (`src/components/comptes/`) : `CompteFormModal` (création + édition, détecte le mode via prop `compte`). Contient `SelectWithCreate` (select + bouton « + Nouveau » + mini-formulaire inline) et `InlineCreate` (input + boutons Créer/Annuler).
**Composants Transferts** (`src/components/transferts/`) : `TransfertFormModal` (création seule — un transfert ne s'édite pas). Construit le payload `POST /transferts/` à partir de compte source/destination + montant + date + statut (défaut le statut `est_definitif`) ; injecte `type_flux_debit`=DEBIT, `type_flux_credit`=CREDIT et la `devise` par défaut. La paire débit/crédit atomique reste gérée par le service backend `creer_transfert`.

**`RESOURCE_DEPENDENCIES`** (invalidations de cache croisées) :
```js
{
  flux:               ['comptes', 'budgets', 'alertes', 'analytics', 'abonnements'],
  transferts:         ['comptes', 'flux', 'analytics'],
  budgets:            ['analytics'],
  'budget-templates': ['budgets', 'analytics'],
  abonnements:        ['alertes'],
  comptes:            ['flux', 'analytics'],
  patrimoine:         ['analytics'],
  alertes:            ['analytics'],
  categories:         ['flux', 'budgets', 'abonnements', 'budget-templates'],
}
```
La clé `'analytics'` couvre toutes les variantes du dashboard (`['analytics', 'dashboard', nbMois]`) **et du prévisionnel** (`['analytics', 'previsionnel', nbMois]`) via le prefix-matching de React Query. **Refonte juillet 2026** : `abonnements` ne dépend plus de `'analytics'` (il ne nourrit plus le prévisionnel) mais de `'alertes'` (l'action `verifier-echeances` crée des alertes) ; en retour `flux` invalide désormais `'abonnements'` (un flux généré met à jour `derniere_occurrence`/`materialise_ce_mois` et peut créer une alerte de divergence).

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
- ~~**Flux paginés côté liste (seuls 50 premiers chargés → mois anciens inaccessibles)**~~ : ✅ **CORRIGÉ (juillet 2026)**. `FluxSearchPanel` charge les flux via **`useInfiniteResource`** (suit le `next` DRF, IntersectionObserver + « Charger plus ») au lieu de la 1re page seule. Tous les flux du foyer sont donc atteignables (recherche + filtres serveur). 4 tests de régression (`FluxRechercheFiltresAPITest`).
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

### ✅ Phase 11b-3 — Budgets thématiques (transversaux) — TERMINÉE (juillet 2026)

Un budget peut désormais regrouper des **feuilles de catégories appartenant à des arbres différents** (ex. « Assurances » = mutuelle santé + assurance habitation + assurance animaux), en plus des budgets simple et majeur (arbre). Les 3 types convergent vers un mécanisme unique : un budget couvre `categories_incluses` si non vide, sinon sa `categorie` ancre.

**Arbitrages foyer validés :** enveloppes **exclusives** (une catégorie ne peut appartenir qu'à un seul budget par mois — total budgets = total dépenses, pas de chevauchement) ; regroupement de **feuilles uniquement** (pas de majeure entière).

- **Backend** : `Budget.categorie`/`BudgetTemplate.categorie` rendus **nullable** + champ `nom` (requis si `categorie` null = thématique). Contraintes d'unicité partielles : `(categorie, mois)` si categorie non-null, `(nom, mois)` si categorie null (idem template, sans mois). Branche thématique dans les serializers (nom + feuilles libres validées comme non-majeures) + **validation d'exclusivité généralisée** (`_premier_conflit_couverture` : aucune feuille cible déjà couverte par un autre budget du mois — remplace l'ancienne validation majeure/mineure). `consommation.py` unifié (`categories_incluses or [categorie]`) ; `recalculer_budgets_pour` retrouve aussi les thématiques (filtre `est_budget_majeur=True` retiré). `reconduire.py` gère les templates thématiques (idempotence par `template` FK quand categorie null). Serializers exposent `nom` + `libelle` (= nom ou categorie.nom). Migration `0005`. **+9 tests** (307 OK).
- **Frontend** : `BudgetFormModal`/`BudgetTemplateFormModal` — sélecteur de type **Par catégorie / Thématique** ; mode thématique = champ Nom + sélection multi-cases de feuilles **de tous les arbres** (groupées par parent). `BudgetCard`/`TemplateCard` affichent `libelle` + badge **« Thématique »** (`info`/bleu) et listent les catégories regroupées quel que soit le type. Type figé en édition de template (comme la catégorie).

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

> **⚠️ SUPERSÉDÉ EN PARTIE (refonte abonnements, juillet 2026) :** les abonnements ne nourrissent **plus** le prévisionnel. Toutes les mentions ci-dessous d'« échéances d'abonnement », « anti-double-comptage abonnement », `abonnements_a_echoir_non_budgetes`/`abonnements_restants` sont **caduques**. Formules actuelles : `solde_projete = solde_actuel + flux_futurs_mois − reste_a_depenser_budgete` ; `capacite = total_budgets − total_consomme` ; trajectoire mois futurs = flux datés + enveloppes `BudgetTemplate` seulement. Le reste du tableau (1 endpoint, lecture seule, fiabilité dégressive) reste valide.
>
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

### 🟡 Phase 12 — Budgets dynamiques (expertise financière requise)

**Besoin exprimé :** règles de calcul de budget en fonction des revenus, et/ou recalcul automatique selon les mois précédents (ex : moins dépensé en essence → capacité accrue ailleurs ; rééquilibrage inter-budgets).

| Mécanique | Description | État |
|---|---|---|
| A — Budget indexé sur les revenus | Enveloppe en % du revenu plutôt qu'en montant fixe | ⏳ gelée (spec à cadrer) |
| **B — Rééquilibrage inter-budgets** | Le sous-consommé d'une catégorie devient une réserve dépensable ailleurs | ✅ **spec cadrée (session juillet 2026)** — voir ci-dessous |
| C — Lissage de tendance | Budget par défaut ajusté sur la moyenne des mois précédents | ⏳ gelée (pourra réutiliser une fenêtre historique paramétrable) |

#### Mécanique B — Système de points « façon JDR » — SPEC CADRÉE (juillet 2026)

> Cadrée en session de réflexion (mode Projet). **Ne PAS s'écarter de cette spec sans re-valider avec l'utilisateur.** Découpée en **12-B-1** (socle lecture seule) puis **12-B-2** (distribution manuelle).

**Principe :** chaque enveloppe **en jeu** (opt-in) génère un solde de **points** à la clôture du mois comptable : sous-consommé → gain, dépassé → perte. Les points s'accumulent dans une **réserve** reportée de mois en mois, que l'utilisateur **distribue manuellement** au mois suivant pour agrandir des enveloppes. Purement pédagogique (organisation/discipline budgétaire), **jamais** de conseil réglementé.

**Décisions verrouillées (arbitrages foyer) :**
- **Finalité** = capacité budgétaire reportée (mécanique B pleine, effet réel sur les budgets N+1).
- **Périmètre** = enveloppes **opt-in** (flag `en_jeu`), pas tous les budgets.
- **Arrondi** = magnitude vers le haut : `points = signe(écart) × ⌈|écart| / VP⌉` (avec VP=10 € = ta « dizaine supérieure », mais généralisé à tout `valeur_point`).
- **Report** = cumul **signé** (la réserve peut être négative — une « dette de points » se traîne).
- **Mois en cours** = delta provisoire affiché et étiqueté **« projeté »** (fiabilité dégressive comme le prévisionnel), n'entre dans la réserve DISPONIBLE qu'à la clôture.

**Glossaire & formules :**
- `VP` = `valeur_point` (€/point, **administrable** via `ParametresBudget`, défaut 10 — règle 1, jamais en dur).
- **Prévu effectif** d'une enveloppe = `montant_prevu` (base, libre) `+ points_alloués × VP`.
- **Points d'une enveloppe** (clôture) = `signe(prévu_effectif − consommé) × ⌈|prévu_effectif − consommé| / VP⌉`.
- **Delta du mois** = `Σ` sur les enveloppes en jeu.
- **Réserve disponible** = `Σ(deltas des mois clôturés) − Σ(tous les points alloués)` → **calculée à la volée**, déterministe (comme les soldes depuis les flux). Pas de table ledger.

**Économie (insight validé) :** allouer 5 pts à une enveloppe (+50 € de prévu) puis la dépenser, coûte **exactement les mêmes points** que la dépasser de 50 € sans rien allouer. L'allocation n'achète pas un rabais mais : (1) l'intentionnalité (choisir où va la marge — esprit « distribution de points »), (2) l'absence d'alerte de dépassement (le prévu effectif a monté), (3) un garde-fou (l'allocation est plafonnée à la réserve disponible ; le dépassement non planifié, lui, fait plonger la réserve dans le négatif).

**Modélisation (minimale) :**
- `ParametresBudget.valeur_point` (Decimal, défaut 10). Migration referentiels.
- `Budget.en_jeu` (bool), `Budget.points_alloues` (int, défaut 0 — 12-B-2). `BudgetTemplate.en_jeu` (bool, porté par la reconduction). Migration budgets `0006`.
- Service `budgets/services/points.py` : `valeur_point()`, `points_enveloppe(budget, vp)`, `delta_mois(mois, vp)`, `solde_disponible(aujourd_hui)`, `historique_points(nb_mois, aujourd_hui)` (par mois : delta + cumul + drapeau provisoire), `allouer(budget, points)` (12-B-2, plafonné à la réserve). Tous acceptent `aujourd_hui` injectable (tests déterministes). Mois clôturé = `mois < mois_comptable_courant()` (passer par `core/services/periode.py`).
- Prévu effectif intégré à `calculer_consommation` (le taux se base sur base + bonus) — 12-B-2.
- Aucune alerte culpabilisante (règle 13) : les points sont un tableau de bord ; le dépassement reste signalé par l'alerte budget existante.

**Hypothèses actées :** arrondi en points (`⌈|écart|/VP⌉`, robuste si VP≠10) ; allocation plafonnée à la réserve clôturée et sur le mois en cours uniquement ; deltas recalculés à la volée (édits rétroactifs → historique reste vrai), allocations persistées ; enveloppes majeures/thématiques comptées une seule fois (l'exclusivité de la phase 11b-3 garantit zéro double-comptage).

**Découpage :**
- **12-B-1 — Socle lecture seule** ✅ **LIVRÉ (juillet 2026)** : `en_jeu`, `valeur_point`, calcul delta mensuel + réserve cumulée + **affichage**. *Pas encore d'allocation.*
  - Backend : `ParametresBudget.valeur_point` (migration referentiels `0003`/`0004`), `Budget.en_jeu` + `Budget.points_alloues` (déjà posé pour 12-B-2) + `BudgetTemplate.en_jeu` (migration budgets `0006`, `en_jeu` porté par `reconduire.py`). Service **`budgets/services/points.py`** (`valeur_point`, `points_enveloppe`, `delta_mois`, `solde_disponible`, `calculer_tableau_points`, `aujourd_hui` injectable). Endpoint **`GET /api/v1/analytics/points/?nb_mois=6`** (`PointsView` + `PointsSerializer`, lecture seule, mois courant `provisoire`). **+8 tests** (315 OK).
  - Frontend : `ParametresPage` carte « Système de points » (édite `valeur_point` via `useUpdateParametres`, pas de remap flux). Toggle `en_jeu` dans `BudgetFormModal`/`BudgetTemplateFormModal`. `BudgetsPage` : `usePoints` hook + panneau **« Réserve de points »** (solde disponible mois clôturés + delta courant projeté + points par enveloppe du mois), `PointsChip`/badge « En jeu » sur les cartes (points recalculés côté client via `computePoints`, miroir du backend). `DEFINITIONS` : `valeur_point`, `points_reserve`, `points_enveloppe`.
- **12-B-2 — Distribution manuelle** ✅ **LIVRÉ (juillet 2026)** : allocation de points depuis la réserve vers les enveloppes en jeu du mois courant.
  - Backend : service **`points.allouer(budget, points, aujourd_hui=None)`** (`AllocationInvalide` → 400) : plafonné à `solde_disponible + points_alloues` de l'enveloppe (on ne distribue que des points possédés), refuse hors-jeu et hors mois courant, recalcule la consommation. Action **`POST /api/v1/budgets/{id}/allouer/`** (body `{"points": N}`). `calculer_consommation` calcule désormais le taux contre le **prévu effectif** (`montant_prevu + points_alloues × valeur_point`) → allouer agrandit l'enveloppe et baisse le taux/les alertes. `BudgetSerializer` expose `montant_prevu_effectif` (VP lue une fois via `self._vp`) ; `montant_restant` basé sur l'effectif. **+7 tests** (322 OK).
  - Frontend : `AllocationModal` (stepper +/−, aperçu prévu effectif + réserve après, plafond `soldeDisponible + points_alloues`). Bouton « Distribuer » (icône `Coins`) sur les cartes en jeu du **mois courant uniquement** (`budget.mois === pointsData.mois_courant`). `BudgetCard` affiche le prévu effectif (« dont +N pts ») ; `computePoints` client intègre `points_alloues`. Allocation via `useResourceAction('budgets', 'allouer')` → invalide budgets + analytics (réserve rafraîchie).

⚠️ **Mécaniques A et C : toujours gelées.** Nécessitent leur propre cadrage (session Projet). Le lissage C pourra réutiliser une fenêtre historique paramétrable. Ne PAS coder sans spec. Rester pédagogique, sans conseil réglementé.

### ✅ Phase 13 — Analyse rétrospective — MVP LIVRÉ (back + front, juillet 2026)

Vue analytique dédiée « où part l'argent, quand et comment », accessible depuis le Dashboard. **Positionnement produit** : Dashboard = photo d'UN mois (état) ; Prévisionnel = prospectif (projeté) ; **Analyse = rétrospectif sur PLUSIEURS mois (réel)**. 100 % réel, aucune projection, lecture seule stricte, aucune alerte.

**Arbitrages foyer validés (session juillet 2026) :** MVP = **Tendances + Catégories dans le temps + Rythme** (l'axe **Épargne via transferts** est reporté à un incrément suivant — c'est l'angle mort actuel : les transferts vers comptes d'épargne ne sont visualisés nulle part) ; période = **fenêtre glissante** 3/6/12/24 mois (pas de plage libre) ; variations = **descriptives, sans mise en avant** (donc **aucun seuil, aucune migration** — respecte règles 1 & 13).

- **Backend** : service `analytics/services/analyse.py::calculer_analyse(nb_mois=6, aujourd_hui=None)` (miroir de `projection.py`/`trajectoire.py`), `AnalyseView` + `AnalyseSerializer`, route `/api/v1/analytics/analyse/`. Fenêtre bornée par `core/services/periode.py` (mois comptable) ; filtre `flux.mois` auto-correct. Blocs `tendances` / `epargne` / `titulaires` / `categories` / `rythme` / `saisonnalite` (détail dans « Endpoints clés »). `ExtractIsoWeekDay` pour le jour de semaine ; libellés récurrents regroupés par libellé normalisé (minuscule + espaces) en Python. **24 tests** (`AnalyseServiceTest` 22 + `AnalyseAPITest` 2 → suite à 346 OK).
- **Frontend** : `AnalysePage` + `useAnalyse` (préfixe `'analytics'` → invalidé par les mutations de flux). `BarChart` étendu (prop `stacked`, légende auto si >1 série). Lien d'accès dans l'en-tête du Dashboard (`ChartColumn`) + Sidebar + Plus. `DEFINITIONS` : `analyse_tendances`, `analyse_comparaison`, `analyse_epargne_encours`, `analyse_epargne_versements`, `analyse_epargne_ecart`, `taux_annuel`, `analyse_titulaires`, `analyse_commun_perso`, `analyse_categories`, `analyse_rythme_jour`, `analyse_recurrents`, `analyse_saisonnalite`.

**Incrément « ventilation par titulaire » — ✅ LIVRÉ (juillet 2026)** : bloc `titulaires`. Regroupement par **propriétaire du compte** (`compte__titulaire`, car `Flux.titulaire` est souvent nul). **Arbitrage foyer validé : bucket « Commun » séparé** — les comptes `est_commun` sont regroupés dans un groupe « Commun » distinct, jamais rattachés à leur propriétaire enregistré (parts sans double comptage). Sous-bloc `commun_vs_perso`. Chaque bucket : dépenses, revenus, épargne, part %.

**Incrément « saisonnalité » — ✅ LIVRÉ (juillet 2026)** : bloc `saisonnalite`. **Arbitrages foyer validés : horizon = tout l'historique** (indépendant du sélecteur nb_mois de la page) ; **une seule vue = comparaison à l'année précédente (YoY)** (le profil mensuel moyen et la heatmap année×mois ont été écartés). Uniquement les **mois clôturés** (le mois courant partiel est exclu — un YoY dessus serait trompeur) ; un mois n'apparaît que si son homologue année-1 est dans l'historique ; `variation_pct=None` si l'année précédente est nulle.

**Incrément « axe Épargne » — ✅ LIVRÉ (juillet 2026)** : bloc `epargne` + modèle compte épargne. **Arbitrages foyer validés : identification par flag `Compte.est_epargne`** (par compte, comme `est_commun`, pas de code de type en dur — règle 1) ; **mesure en versements nets** (Σ montant des transferts sur les comptes d'épargne, entrées +/sorties −) ; contenu = les 4 vues (encours, versements/mois + cumul, écart budgétaire vs réel, par compte). **Nouveau champ `Compte.taux_annuel`** ajouté (les livrets ont un taux : Livret A/PEL/PEA…) mais **informatif** — il n'entre PAS dans les mesures d'épargne. Distinction clé : épargne **budgétaire** (revenus−dépenses, bloc tendances) ≠ épargne **réellement mise de côté** (transferts, bloc epargne). Migrations comptes `0004`/`0005`.

**⏳ Incrément futur restant — demandé par l'utilisateur (à cadrer)** : **prévisionnel avec taux d'épargne** — projeter la croissance des comptes d'épargne via `taux_annuel` (intérêts composés). Le champ `taux_annuel` est déjà stocké par compte ; reste à l'exploiter dans `analytics/services/projection.py`/`trajectoire.py` (ou un service dédié). Rester estimatif/projeté (jamais vérité comptable), sans conseil réglementé. À cadrer en session avant de coder.

### 🟢 Phase 14 — Rapprochement bancaire (app `imports`) — 14-A + 14-B LIVRÉES (back + front, juillet 2026)

Module de **rapprochement** (réconciliation), pas d'import brut : confronter un relevé bancaire aux flux de l'app pour repérer oublis et erreurs de saisie. **Lecture seule vis-à-vis des flux** — l'app reste la seule vérité, le relevé est un contrôle externe.

**Arbitrages foyer validés (session cadrage) :** finalité MVP = **rapport d'écarts** (création des flux → 14-B) ; **persistance** des lots + lignes ; **mapping compte manuel** à l'upload (fichier mono-compte, avertir si plusieurs `accountNum`) ; **virements internes rapprochés** aux flux `est_transfert` ; matching **STRICT d'abord** (montant+date exacts) puis tolérance ; **ambigus signalés** pour validation/rejet manuel par l'utilisateur.

**✅ 14-A livrée** (voir la ligne `imports` du §5 pour le détail technique) : parser BoursoBank isolé, modèles `ImportBancaire`/`LigneBancaire`, moteur `rapprochement.py` (matching strict multi-passe + anti-doublon par comptage + contrôle de solde), endpoints multipart + validation/rejet des ambigus, page `/imports` à 3 sections. **43 tests.** Décision imposée par les données : `accountbalance` BoursoBank = instantané **journalier** → pas d'unicité dure sur `hash_dedup` (anti-doublon logique). `ImportBancaire.delete()` cascade le soft delete (sinon anti-doublon faussé).

**✅ 14-B livrée** (juillet 2026) : **création du flux manquant en 1 clic** depuis une ligne `manquant_app` + **pointage durable / anti-re-match**. C'est la **seule** écriture de flux du module. Service `rapprochement.py::creer_flux_depuis_ligne(ligne, categorie, libelle=None, statut=None)` (atomique : crée le flux — type_flux dérivé du signe, statut définitif par défaut, `reference_externe` = trace bancaire lisible — puis rattache la ligne → `rapproché` ; `CreationFluxInvalide` si déjà rapprochée). Endpoint `POST /imports-lignes/{id}/creer-flux/` (body `{categorie, libelle?}` → 201 `{ligne, flux}`). **Pointage / anti-re-match** : la détection « pointé » s'appuie sur le **lien de rapprochement** (`LigneBancaire.flux` rapproché, lot vivant), pas sur `reference_externe` (plus robuste ; `reference_externe` reste une trace lisible posée à la création). Helper `flux_ids_deja_pointes(compte, sauf_lot=None)` : les flux déjà pointés par un AUTRE lot sont **exclus du vivier** (`_flux_du_compte`, `candidats_pour`, `flux_orphelins`) → un relevé qui se chevauche ne re-propose pas un flux déjà rapproché. `FluxViewSet` annote `est_pointe` (`Exists` d'une ligne rapprochée) exposé par `FluxSerializer` → badge « Pointé » (teal) sur la page Flux. Front : `CreerFluxModal` (catégorie requise, libellé éditable, montant/date figés, **avertissement si libellé ~ « VIR »** = virement probable → renvoi vers Transferts), bouton « Créer » sur les lignes `manquant_app`, hook `useCreerFluxDepuisLigne` (invalide imports/flux/comptes/budgets/alertes/analytics). **+5 tests** (415 OK).

**Reste ouvert** : exposer le `controle_solde` par compte hors import (widget) ; import Excel (migration `SUIVI_BUDGET.xlsx`).

### ⏳ Phases ultérieures (non détaillées)

- **Objectifs** (`objectifs`) : objectifs d'épargne, suivi de progression.
- **Import Excel** (`imports`) : migration du classeur `SUIVI_BUDGET.xlsx` (l'import bancaire CSV = rapprochement, ci-dessus, livré).
- **Market data** (`market_data`) : providers isolés, fallback manuel, sécurité des clés (env), valorisation estimative des actifs de marché. **Jamais** vérité comptable.
- **Durcissement** : ~~réactiver l'auth (JWT)~~ **livrée, back + front (août 2026,
  §5 étapes 1 et 2)** ; ~~**révocation des jetons**~~ **livrée** —
  `token_blacklist` vit dans le dépôt `Identite`, seul émetteur ; BudgetTracker
  relaie `POST /auth/deconnexion/` ; ~~renouveler **`SECRET_KEY`**~~ (fait en
  dev, `.env.prod` restant ; contrôle **bloquant hors DEBUG**) ; permissions ;
  ~~multi-foyer~~ (**retiré**, voir la décision de suite ci-dessous) ; audit
  (`audit`) ; tests de charge.

### 🔗 Décision de suite — interopérabilité avec FoyerOS (arbitrée le 2026-08-01)

> **Rien n'est développé côté BudgetTracker.** Contrat complet :
> `FamilyToolSuite/FoyerOS/docs/interop-budgettracker.md`. Le chantier touche les
> deux applications ; **chaque étape tient dans un seul dépôt**, aucun commit ne
> mélange les deux (`FamilyToolSuite/CLAUDE.md` §2 et §8).

FoyerOS poussera les dépenses de courses ici. Quatre décisions engagent **ce
dépôt**, et il ne faut pas les redécouvrir :

1. **Pas de multi-foyer dans BudgetTracker — une instance par foyer.** C'est
   FoyerOS qui est multi-tenant ; ici, un déploiement = un foyer. L'item est donc
   sorti de la feuille de route ci-dessus, il n'est pas « à faire plus tard ».
2. **Le durcissement de l'auth passe en tête, et il est complet.** ✅ **Livré,
   back et front (§5, étapes 1 et 2).** N'authentifier que la route d'ingestion
   n'aurait rien protégé tant que `POST /flux/` restait ouvert.
   - Le **compte de service `foyeros`** n'est **volontairement pas créé** à
     l'étape 1. Avec `IsAuthenticated` seul et aucune permission par objet, il
     aurait accès à toute l'API — un identifiant dormant à pleins droits, des
     mois avant d'avoir un travail. Il naîtra **avec l'endpoint qu'il sert**
     (étape 3), et sa restriction se décidera là.
3. ⚠️ **Ne pas changer `AUTH_USER_MODEL` à cette occasion.** L'app tourne sur des
   données réelles ; basculer sur un `User` custom après migrations est
   l'opération la plus risquée de Django, pour un gain nul ici. FoyerOS
   s'identifie par email, BudgetTracker par `username` — divergence **assumée**,
   que le futur service d'identité partagé résoudra.
4. **L'ingestion est une route dédiée, pas `POST /flux/`** :
   `POST /api/v1/integrations/depenses/`, charge **sémantique**
   (`source`, `nature`, `reference`, `date`, `montant`, `libelle`, `notes`).
   - **C'est BudgetTracker qui résout** `compte` et `categorie`, via un nouveau
     référentiel administrable **`RegleIngestion(source, nature, compte,
     categorie, actif)`** (règle 1 — rien en dur), semé avec `(foyeros, courses)`.
     Le reste se dérive des `code` des référentiels : `TypeFlux` débit,
     `StatutFlux` définitif, `Devise.est_defaut`. *Motif : choisir une catégorie
     budgétaire est une décision financière, elle ne peut pas vivre dans FoyerOS.*
   - ⚠️ **`montant` arrive POSITIF ; le signe est posé ici.** La convention
     « négatif = dépense » est une règle de ce dépôt : la faire appliquer par
     l'appelant serait la dupliquer, et une inversion de signe ne se voit pas.
   - **Idempotent par `Flux.reference_externe`** (`foyeros:sortie:<uuid>`) :
     `201` à la création, **`200` + le flux existant** si la référence est déjà
     connue. La passe de rattrapage de FoyerOS rejoue par nature — sans cette
     clé, un redémarrage au mauvais moment double une dépense.
   - **`400` si aucune `RegleIngestion` ne correspond.** FoyerOS distingue 4xx
     (refus, pas de rejeu) de 5xx (panne, repris plus tard) : ne pas renvoyer un
     5xx sur une erreur de configuration, ce serait une boucle de rejeu.

**Granularité arbitrée : un flux par sortie**, jamais par ligne ni par rayon — un
débit = un passage en caisse, donc rapprochable 1 pour 1 avec le relevé bancaire
(phase 14). Le détail par produit reste dans FoyerOS. **BudgetTracker n'appelle
jamais FoyerOS** : le sens est unidirectionnel (suite §4).

---

## 7. PIÈGES CONNUS & BONNES PRATIQUES

- **Fichiers non sauvegardés (`Ctrl+S` oublié)** : cause récurrente de bugs fantômes dans la phase copier-coller (« champ X n'existe pas sur le modèle » alors qu'il a été « ajouté »). En Claude Code ce piège disparaît, mais après une édition, toujours relancer `python manage.py check`.
- **Encodage PowerShell** : des fichiers créés/édités via PowerShell ont parfois corrompu les accents (`Ã©` au lieu de `é`). Écrire en UTF-8 propre.
- **`AppRegistryNotReady`** : `python -c "from app.models import X"` hors contexte Django échoue. Utiliser `manage.py shell` ou `manage.py check` pour valider les imports de modèles.
- **Tailwind v4** : après un rebuild du conteneur, vérifier que `tailwindcss` + `@tailwindcss/vite` sont bien dans `package.json` (souci de persistance déjà rencontré). Toujours vérifier `package.json` après un `npm install`.
- **Dépendances front absentes après reconstruction du conteneur** : un paquet déclaré dans `package.json` mais absent du `node_modules` du conteneur fait échouer le `npm run build` (`Rollup failed to resolve import ...`). Rencontré après le déplacement du repo dans `FamilyToolSuite/` + reconstruction du conteneur : `@xyflow/react` (utilisé par `components/transferts/FluxGraph.jsx`) manquait → `docker compose exec frontend npm install` avant de builder. Remède systématique après tout rebuild `frontend` : relancer `npm install` dans le conteneur.
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
- **Solde projeté — ne pas repartir du `solde_theorique` brut (phase 10-A)** : `solde_theorique` inclut DÉJÀ les flux datés dans le futur. La projection part de `solde_actuel = Σ solde_theorique − Σ flux futurs (tous, transferts inclus)`, puis réintroduit chaque brique séparément (flux futurs du mois hors transferts/ajustements, reste-à-dépenser budgété). Réintroduire un flux futur sans l'avoir d'abord retiré du `solde_theorique` le compte deux fois. Les transferts futurs ne sont pas réintroduits (effet net nul sur le solde global). Voir `analytics/services/projection.py::calculer_solde_projete`.
- ~~**Anti-double-comptage abonnement dans le prévisionnel (phase 10-A)**~~ : **CADUC (refonte juillet 2026)** — les abonnements ne sont plus dans le prévisionnel. `projection.py`/`trajectoire.py` ne connaissent plus les abonnements ; toute la logique de déduplication d'échéances a été retirée. Un abonnement pèse sur la projection uniquement via les flux réellement générés.
- **Génération d'un flux depuis un abonnement (refonte juillet 2026)** : la FK `Flux.abonnement` (`SET_NULL`) est le seul lien. Le bouton « Générer le flux » (`AbonnementsPage`) ouvre `FluxFormModal` avec `initialValues` (dont `abonnement`, `statut` par défaut le `est_definitif` mais **modifiable**). Le signal flux `post_save` fait le reste (derniere_occurrence + divergence auto). Ne jamais recréer un chemin de matérialisation automatique côté abonnement : c'est un geste **manuel** au clic, à chaque échéance. `materialise_ce_mois` (flux lié dans le mois comptable courant) désactive le bouton pour éviter le doublon.
- **Budgets thématiques : `categorie` nullable + `nom` (phase 11b-3)** : un budget/template thématique a `categorie=None`, un `nom` obligatoire et des `categories_incluses` = feuilles libres (validées non-majeures). L'unicité et l'exclusivité sont gérées **manuellement dans `validate()`** (conditionnées à categorie null/non-null) — voir `_premier_conflit_couverture`. Ne jamais afficher `categorie_nom` directement pour un budget (peut être null) : utiliser `libelle` (= nom ou categorie.nom, exposé par le serializer). Un budget couvre `categories_incluses` si non vide, sinon `[categorie]` (mécanisme unifié dans `consommation.py` et `recalculer_budgets_pour`).
- **Système de points (mécanique B) : prévu effectif & réserve calculés à la volée** : le taux d'un budget est calculé contre le **prévu effectif** = `montant_prevu + points_alloues × valeur_point` (pas le prévu de base) — allouer des points agrandit l'enveloppe et baisse le taux. `points_alloues` est **read-only** dans le serializer : passer par l'action `POST /budgets/{id}/allouer/` (service `points.allouer`), jamais par un PATCH direct. La **réserve disponible** = `Σ(deltas des mois clôturés) − Σ(points_alloues)`, recalculée à la volée (pas de table). Deux limites connues acceptées au MVP : (1) changer `valeur_point` ne recalcule pas immédiatement les `taux_consommation` déjà stockés (ils se remettent à jour au prochain flux/allocation ; l'endpoint `/analytics/points/` est lui toujours à jour car il relit VP) ; (2) le prévisionnel/capacité (`analytics/projection.py`) utilise toujours le `montant_prevu` de base, pas l'effectif (le bonus de points est une marge discrétionnaire, hors plan budgété). L'allocation est **plafonnée** à `solde_disponible + points_alloues` de l'enveloppe et limitée au **mois comptable courant**.
- **DRF `UniqueConstraint` multi-champs → `UniqueTogetherValidator` qui rend les champs OBLIGATOIRES** (piège rencontré en 11b-3) : ajouter une `UniqueConstraint(fields=["nom","mois"], condition=...)` sur un modèle fait auto-générer par DRF un `UniqueTogetherValidator` dont `enforce_required_fields` exige **tous** ces champs présents dans chaque payload (erreur « Ce champ est obligatoire », code `required`) — même si le champ est `blank=True` / `required=False`, et **en ignorant la `condition` partielle**. Une `UniqueConstraint` **mono-champ** devient un simple `UniqueValidator` (pas d'exigence de présence), d'où une asymétrie déroutante entre deux serializers voisins. Remède quand l'unicité est conditionnelle ou déjà gérée à la main : `class Meta: validators = []` sur le serializer (neutralise les validateurs auto-générés), puis valider l'unicité dans `validate()`. Symptôme piégeux : `serializer.fields['x'].required` renvoie `False` alors que `is_valid()` lève quand même une erreur `required` sur `x` (elle vient du validateur, pas du champ).
- **Infos-bulles d'aide : textes centralisés, jamais en dur** : les explications des indicateurs vivent dans `src/constants/definitions.js` (objet `DEFINITIONS`, `{ titre, texte, formule }`) et sont rendues via `<Tooltip {...DEFINITIONS.xxx} />`. Ne jamais écrire un texte d'aide directement au point d'usage. Le composant `Tooltip` s'ouvre au **survol ET au clic/tap** (le `:hover` seul est inutilisable en tactile) : ne pas le réduire à un `title=` HTML natif. Positionnement : pas de moteur de placement type floating-ui ; gérer manuellement le risque de débordement de bord via la prop `align` (`right` pour les éléments en bord droit — dernière métrique d'une grille, valeurs alignées à droite ; `left` par défaut pour un libellé suivi de l'icône). Wording aligné sur les règles métier §4-5 et la fiabilité (réel/estimatif/projeté) précisée quand pertinent. **Toute nouvelle métrique calculée ajoute son entrée dans `definitions.js`.**
- **`seed_demo` est dev-only, garde-fou backend** : la commande crée un compte + des catégories de DÉMO et **lève une `CommandError` si `settings.DEBUG=False`** (prod), sauf `--force` explicite. En prod, l'app démarre vierge de données métier : seul `seed_referentiels` (idempotent, aucune donnée métier) est lancé — par l'`entrypoint.prod.sh` à chaque démarrage, et par `make init`/`make seed`. Ne jamais router `seed_demo` vers la prod. En dev : `make dev-seed` (stack dev) ou `python manage.py seed_demo`.
- **Makefile : cibles prod par défaut, dev préfixées `dev-`** : `up`/`down`/`migrate`/`seed`/`deploy`/`backup`… visent la **prod** (`docker-compose.prod.yml` + `.env.prod`). Le dev passe par `dev-up`/`dev-down`/`dev-logs`/`dev-seed` (`docker-compose.yml` + `.env`). `make deploy` = `backup → git pull → build → up → migrate → collectstatic → check` (rebuild back + front, migrations auto). `make reset-db` **détruit le volume `pgdata`** → confirmation `CONFIRMER` exigée. Attention : pour le dev local on utilise habituellement `docker compose ...` directement (cf. §8), pas le Makefile.
- **Onglet navigateur prod/dev** : le titre est posé dynamiquement dans `frontend/src/main.jsx` via `import.meta.env.PROD` — `BudgetTracker` en prod (`vite build`, Dockerfile.prod), `🛠️ BudgetTracker · DEV` en dev (`npm run dev`). `index.html` ne porte qu'un titre neutre par défaut. Ne pas remettre un titre figé dans `index.html`.
- **Mois comptable ≠ mois calendaire** : le `mois` d'un flux suit le paramètre `jour_debut_mois_comptable` (`ParametresBudget`, défaut 1). **Toute** logique « mois courant » ou « bornes de mois » DOIT passer par `core/services/periode.py` (`mois_comptable`, `bornes_mois_comptable`, `mois_comptable_courant`) — jamais réécrire `date.replace(day=1)` ou `mois + 1 mois − 1 jour` en dur (ça casse dès que le jour de bascule > 1). Services déjà alignés : `dashboard.py` (`_mois_courant`, `_calculer_evolution_solde`), `compte_dashboard.py`, `projection.py` (`_mois_de`/`_debut_de_mois`/`_fin_de_mois`) → `trajectoire.py` hérite par import. Filtrer par `flux.mois` est auto-correct ; filtrer par **plage de dates** dérivée d'un mois exige `bornes_mois_comptable`. Avec jour=1, toutes ces fonctions retombent sur le calendaire (rétro-compat totale, tests existants intacts). **Après changement du paramètre → `manage.py recalculer_mois`** sinon les flux gardent leur ancien découpage. Le `mois` d'un Budget/BudgetTemplate reste un libellé choisi par l'utilisateur (pas remappé). **296 tests OK**.
- **Heatmap dépenses : échelle plafonnée, jamais sur le max brut** : `HeatmapDepenses` colore chaque jour selon `total / plafond` où `plafond = 90e centile des jours dépensés` (`calculerPlafond`), pas le max. Un loyer ou gros achat isolé écrasait sinon toute l'échelle (tous les autres jours retombaient au niveau le plus faible → heatmap quasi monochrome) ; les jours au-delà du plafond saturent au niveau max. Ne pas « simplifier » en revenant à `total / max`. Plancher d'opacité à `0.4` et texte `text-content-3` (adaptatif) sur les niveaux faibles : un rouge trop transparent rendait le chiffre illisible en thème clair — ne pas remettre `text-white` partout. Cellules en hauteur fixe (`h-12 sm:h-14`), jamais `aspect-square` (sinon le calendrier fait toute la hauteur de l'écran sur desktop et casse l'esprit « coup d'œil » du dashboard).
- **Liste de flux : toujours passer par `FluxSearchPanel` + `useInfiniteResource`, jamais `useResourceList('flux')` seul** : ce dernier ne charge que la 1re page (50 flux) → les mois anciens deviennent inaccessibles (bug corrigé juillet 2026). La recherche/le filtrage sont faits **côté serveur** (query params `search`, `titulaire_compte`, `est_definitif`, etc.), pas en filtrant un tableau déjà chargé — sinon on ne filtre que les 50 premiers. Le **Sens** (Dépense/Recette) est dérivé du signe du montant (`montant_max=-0.01` / `montant_min=0.01`), pas d'un lookup `type_flux`. `baseParams` (ex. `{compte:id}`) est fusionné dans **toutes** les requêtes du panneau et ne doit pas être contournable par l'utilisateur (scope compte). La query key `[resource,'infinite',params]` est couverte par l'invalidation préfixe `[resource]` : une mutation de flux rafraîchit bien la liste infinie.
- **`titulaire_compte` ≠ `titulaire` (flux)** : le propriétaire d'un compte est `compte__titulaire` ; le champ `titulaire` du flux lui-même est souvent nul. Le filtre « Propriétaire du compte » de la recherche utilise `titulaire_compte`, pas `titulaire`.
- **Rapprochement bancaire : la SEULE écriture de flux est `creer_flux_depuis_ligne` (14-B)** — tout le reste du moteur `imports/services/rapprochement.py` (matching, validation d'ambigu, rejet) n'écrit que l'état de rapprochement de la `LigneBancaire` (`statut`/`flux`), jamais un flux. Un flux créé depuis une ligne est un flux normal (statut définitif, `reference_externe` = trace bancaire) ; jamais un transfert (l'UI avertit sur les libellés « VIR », mais ne bloque pas — un vrai transfert doit passer par `/transferts/`).
- **Pointage bancaire (14-B) : détection par le LIEN, pas par `reference_externe`** — un flux est « pointé » s'il est rattaché à une `LigneBancaire` rapprochée d'un lot vivant (annotation `est_pointe` = `Exists(...)` sur `FluxViewSet`, défaut `False` hors de ce contexte via `getattr`). `reference_externe` n'est qu'une **trace lisible** posée à la création (jamais utilisée pour détecter le pointage, jamais écrasée sur un flux existant). L'**anti-re-match** (`flux_ids_deja_pointes(compte, sauf_lot)`) exclut du vivier les flux pointés par un AUTRE lot → un relevé qui se chevauche ne re-propose pas un flux déjà rapproché ; le lot courant est exclu (`sauf_lot`) pour être recalculé à neuf.
- **`accountbalance` BoursoBank = instantané journalier, pas par opération** : les lignes d'un même jour partagent le même solde (constaté sur l'échantillon foyer). Conséquences : (1) **pas d'unicité dure** sur `LigneBancaire.hash_dedup` (deux opérations identiques le même jour se distingueraient mal → l'anti-doublon se fait par **comptage d'occurrences** dans `filtrer_doublons`, jamais par contrainte DB) ; (2) le `controle_solde` compare le **solde ACTUEL confirmé** de l'app (`solde_initial + Σ tous les flux définitifs` = solde_reel) au **dernier solde connu du relevé** (la ligne la plus récente), **au centime** (pas de seuil — règle 1). ⚠️ **Ne PAS ré-ancrer le contrôle « à la date du relevé »** (`Σ flux ≤ date_ref`) : ça crée de faux écarts par décalage de dates de saisie (une opération passée par la banque avant la date du relevé mais saisie plus tard dans l'app), constaté en prod. Comparer les soldes actuels neutralise ce bruit et détecte quand même un vrai manque. Le contrôle est le plus fiable si le relevé est à jour ; pour un relevé ancien, l'écart reflète les mouvements survenus depuis (wording du bandeau le précise).
- **Soft delete d'un `ImportBancaire` doit cascader sur ses lignes** : `BaseModel.delete` ne cascade pas ; `ImportBancaire.delete()` est surchargé pour soft-deleter ses `LigneBancaire` (`self.lignes.all().delete()`). Sinon les hash des lignes d'un lot supprimé restent comptés par l'anti-doublon (`filtrer_doublons` lit `LigneBancaire.objects.filter(import_lot__compte=…)`) → **ré-import du même relevé bloqué à tort** (tout en doublons, 0 ligne). Toute nouvelle relation enfant persistée d'un `BaseModel` parent doit prévoir ce cas.
- **Matching de rapprochement = STRICT puis tolérance, ambigus non devinés** : `apparier` fait passe 1 (montant ET date exacts) avant passe 2 (montant exact, date ± `tolerance_jours_rapprochement`). Un flux exact l'emporte toujours sur un flux « proche ». En passe 2, une ligne à **plusieurs** candidats reste `ambigu` (aucun flux consommé) → l'utilisateur tranche via `valider_ligne`/`rejeter_ligne` ; une ligne à **un seul** candidat est rapprochée automatiquement (propagation de contraintes : résoudre les singles peut lever d'autres ambiguïtés). Les **virements** se rapprochent sans parser le libellé VIR (le flux `est_transfert` a le bon montant/date) ; `est_ajustement` est hors vivier.
- **Remboursement d'un flux = contre-flux recette, JAMAIS un drapeau** : rembourser une dépense crée une **recette liée** (`Flux.flux_rembourse` FK) via `flux/services/remboursement.py::rembourser_flux` (seul point d'écriture), pas un champ `est_rembourse`. Raison décisive : le foyer fait du rapprochement bancaire — la banque montre le débit ET le crédit, un contre-flux laisse les deux lignes se rapprocher naturellement (un drapeau ferait ressortir le crédit banque en « manquant_app »). Le contre-flux est un **flux normal** (statut définitif, même compte/catégorie/devise) : son solde est recalculé par le signal, et l'annulation = suppression normale du contre-flux. Ne jamais rembourser un flux qui n'est pas une dépense (montant ≥ 0), un transfert ou un ajustement, ni au-delà du **reste à rembourser** (`|montant| − Σ remboursements`). Le badge « Remboursé »/« partiellement » se dérive côté front de l'annotation `montant_rembourse` (`Sum` filtré `is_deleted=False`, posée dans `FluxViewSet.get_queryset` **à côté** de `est_pointe` — ne pas casser l'une en touchant l'autre). Analytics volontairement inchangé (même catégorie des deux côtés → net auto, arbitrage foyer).
- **Upload multipart : curl sur Windows n'aime pas `-F "fichier=@x.csv;type=text/csv"`** (renvoie `HTTP 000`) → utiliser `-F "fichier=@x.csv"` sans le `;type=`.
- **⚠️ Upload `FormData` via `apiClient` (axios) → 415 « application/json non supporté »** : l'instance `api/client.js` fixe `Content-Type: application/json` par défaut. Avec axios v1, quand ce défaut est présent ET que le corps est un `FormData`, `transformRequest` **sérialise le FormData en JSON** (`defaults/index.js` : `hasJSONContentType ? JSON.stringify(formDataToJSON(data)) : data`) → le backend (parsers `MultiPartParser`/`FormParser`) renvoie **415**. Forcer `Content-Type: multipart/form-data` par requête ne suffit pas : l'adaptateur xhr ne retire le Content-Type que si `data === undefined`, donc le **boundary manque** (échec de parsing). **Solution retenue** (`useImports.js::useUploadImport`) : utiliser un **axios NU** (`import axios; axios.post('/api/v1/imports/', form)`), qui n'a aucun `Content-Type` par défaut → le FormData part tel quel et le navigateur pose le boundary. Chemin complet requis (pas de baseURL) ; le proxy Vite `/api` reste actif ; l'objet d'erreur conserve `response` (gestion 400/multi-comptes OK). Ne PAS refaire passer l'upload par `apiClient`.

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