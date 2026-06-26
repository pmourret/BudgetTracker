"""
Services de projection financière — phase 10-A (lecture seule).

Tous les indicateurs de ce module sont de fiabilité PROJETÉE : une
projection n'est jamais une vérité comptable, le solde réel reste la
seule référence. Ces services LISENT flux / budgets / abonnements et
n'écrivent rien (calcul à la volée, aucun modèle persisté).

Le patrimoine estimatif n'entre jamais dans ces projections (règle 10).
Transferts internes et flux d'ajustement sont exclus de toutes les
briques (mêmes filtres que analytics/services/dashboard.py).

Chaque service accepte un paramètre `aujourd_hui` injectable pour les
tests (même esprit que le pattern _calculer_xxx_avec_model).
"""
import calendar
import datetime
from collections import Counter
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Sum

ZERO = Decimal("0.00")


def _aujourd_hui_ou(aujourd_hui):
    return aujourd_hui or datetime.date.today()


def _mois_de(d: datetime.date) -> datetime.date:
    """Libellé du mois comptable de `d` (cohérent avec flux.mois)."""
    from core.services.periode import jour_bascule_actif, mois_comptable

    return mois_comptable(d, jour_bascule_actif())


def _debut_de_mois(mois: datetime.date) -> datetime.date:
    """Premier jour de la période comptable `mois`."""
    from core.services.periode import bornes_mois_comptable, jour_bascule_actif

    return bornes_mois_comptable(mois, jour_bascule_actif())[0]


def _fin_de_mois(mois: datetime.date) -> datetime.date:
    """Dernier jour de la période comptable `mois`."""
    from core.services.periode import bornes_mois_comptable, jour_bascule_actif

    return bornes_mois_comptable(mois, jour_bascule_actif())[1]


def _au_jour(d: datetime.date, jour: int) -> datetime.date:
    """Cale une date sur un jour du mois donné, borné à la fin du mois."""
    dernier = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=min(jour, dernier))


# ---------------------------------------------------------------------------
# Échéances d'abonnements
# ---------------------------------------------------------------------------

def occurrences_abonnement(abonnement, debut, fin):
    """
    Dates d'échéance attendues d'un abonnement, strictement après `debut`
    et jusqu'à `fin` inclus.

    La périodicité vient exclusivement du référentiel Frequence (nb_jours,
    règle 1 : rien de codé en dur). Les fréquences d'au moins 28 jours sont
    converties en pas calendaires mensuels (nb_jours / 30 arrondi) pour
    éviter la dérive d'un simple pas en jours sur un horizon long ;
    jour_echeance, s'il est renseigné, fixe le jour du mois.
    """
    if not abonnement.actif:
        return []

    nb_jours = abonnement.frequence.nb_jours
    date_min = abonnement.date_debut
    date_max = abonnement.date_fin  # None = sans fin

    if not nb_jours:
        # Fréquence ponctuelle : une seule occurrence attendue, à date_debut.
        d = abonnement.date_debut
        if debut < d <= fin and (date_max is None or d <= date_max):
            return [d]
        return []

    en_pas_mensuels = nb_jours >= 28
    if en_pas_mensuels:
        pas = relativedelta(months=max(1, round(nb_jours / 30)))
    else:
        pas = datetime.timedelta(days=nb_jours)

    if abonnement.derniere_occurrence:
        # La dernière occurrence est déjà matérialisée : on part du cycle suivant.
        base, indice = abonnement.derniere_occurrence, 1
    else:
        base, indice = abonnement.date_debut, 0

    occurrences = []
    while True:
        # base + pas * n (et non += pas) : évite la dérive cumulative des
        # fins de mois courts avec relativedelta.
        echeance = base + pas * indice
        if en_pas_mensuels and abonnement.jour_echeance:
            echeance = _au_jour(echeance, abonnement.jour_echeance)
        if echeance > fin:
            break
        if (
            echeance > debut
            and echeance >= date_min
            and (date_max is None or echeance <= date_max)
        ):
            occurrences.append(echeance)
        indice += 1
    return occurrences


def compteur_flux_futurs(aujourd_hui, fin):
    """
    Multiset (categorie_id, montant, mois) des flux futurs déjà saisis,
    utilisé pour dédupliquer les échéances d'abonnement déjà matérialisées
    en flux daté (pas de FK Flux → Abonnement dans le modèle).
    """
    from flux.models import Flux

    compteur = Counter()
    lignes = Flux.objects.filter(
        date_flux__gt=aujourd_hui,
        date_flux__lte=fin,
        est_transfert=False,
        est_ajustement=False,
    ).values_list("categorie_id", "montant", "mois")
    for categorie_id, montant, mois in lignes:
        compteur[(categorie_id, montant, mois)] += 1
    return compteur


def filtrer_echeances_deja_saisies(abonnement, echeances, compteur_flux):
    """
    Retire les échéances déjà matérialisées en flux futur daté
    (clé catégorie + montant + mois). Chaque flux ne neutralise
    qu'une seule échéance (le compteur est décrémenté).
    """
    retenues = []
    for echeance in echeances:
        cle = (abonnement.categorie_id, abonnement.montant_attendu, _mois_de(echeance))
        if compteur_flux[cle] > 0:
            compteur_flux[cle] -= 1
        else:
            retenues.append(echeance)
    return retenues


def abonnements_a_echoir(debut, fin, compteur_flux, categories_couvertes):
    """
    Échéances d'abonnements actifs attendues sur la fenêtre, hors échéances
    déjà saisies en flux futur (déduplication) et hors dépenses déjà
    couvertes par un budget (elles sont incluses dans le reste à dépenser
    budgété — décision actée anti double-comptage).

    Les abonnements positifs (ex. salaire récurrent) sont toujours comptés :
    les budgets ne couvrent que des dépenses.

    Retourne {"recettes": Decimal >= 0, "depenses": Decimal <= 0 (signé)}.
    """
    from abonnements.models import Abonnement

    recettes = ZERO
    depenses = ZERO
    for abonnement in Abonnement.objects.filter(actif=True).select_related("frequence"):
        if abonnement.montant_attendu < 0 and abonnement.categorie_id in categories_couvertes:
            continue
        echeances = occurrences_abonnement(abonnement, debut, fin)
        echeances = filtrer_echeances_deja_saisies(abonnement, echeances, compteur_flux)
        montant = abonnement.montant_attendu * len(echeances)
        if abonnement.montant_attendu >= 0:
            recettes += montant
        else:
            depenses += montant
    return {"recettes": recettes, "depenses": depenses}


# ---------------------------------------------------------------------------
# Couverture budgétaire du mois
# ---------------------------------------------------------------------------

def categories_budgetees(mois):
    """
    Ids des catégories couvertes par un budget du mois : la catégorie du
    budget elle-même + les mineures incluses des budgets majeurs.
    """
    from budgets.models import Budget

    couvertes = set()
    budgets = Budget.objects.filter(mois=mois).prefetch_related("categories_incluses")
    for budget in budgets:
        couvertes.add(budget.categorie_id)
        if budget.est_budget_majeur:
            couvertes.update(
                budget.categories_incluses.values_list("id", flat=True)
            )
    return couvertes


def reste_a_depenser_budgete(mois):
    """
    Somme des restes à dépenser des budgets du mois :
    max(0, montant_prevu - montant_consomme) par budget.

    montant_consomme inclut déjà les flux datés dans le futur du mois (le
    service de consommation filtre par mois, pas par date) : la brique
    flux_futurs_mois et celle-ci sont donc complémentaires, sans double
    comptage (le futur daté réduit le reste via la consommation).
    """
    from budgets.models import Budget

    reste = ZERO
    for budget in Budget.objects.filter(mois=mois):
        reste += max(ZERO, budget.montant_prevu - budget.montant_consomme)
    return reste


# ---------------------------------------------------------------------------
# Indicateur 1 — Solde projeté fin de mois courant
# ---------------------------------------------------------------------------

def calculer_solde_projete(aujourd_hui=None) -> dict:
    """
    Solde bancaire projeté en fin de mois courant, décomposé en briques
    traçables. Fiabilité : PROJETÉE (élevée — horizon fin de mois).

        solde_projete = solde_actuel              (flux datés jusqu'à aujourd'hui)
                      + flux_futurs_mois          (engagé : flux datés > aujourd'hui, dans le mois)
                      + abonnements_a_echoir_non_budgetes   (récurrent, signé)
                      - reste_a_depenser_budgete            (estimé)

    Piège évité : compte.solde_theorique inclut DÉJÀ les flux datés dans le
    futur. On les retire (solde_actuel) puis on réintroduit chaque brique
    séparément — sinon ils seraient comptés deux fois.
    """
    from comptes.models import Compte
    from flux.models import Flux

    aujourd_hui = _aujourd_hui_ou(aujourd_hui)
    mois_courant = _mois_de(aujourd_hui)
    fin_mois = _fin_de_mois(mois_courant)

    solde_theorique_total = (
        Compte.objects.filter(actif=True)
        .aggregate(t=Sum("solde_theorique"))["t"]
        or ZERO
    )
    # Tous les flux futurs (transferts inclus : ils sont dans solde_theorique).
    # Les transferts futurs ne sont pas réintroduits ensuite — leur effet net
    # sur le solde global est nul (paire débit/crédit).
    flux_futurs_tous = (
        Flux.objects.filter(compte__actif=True, date_flux__gt=aujourd_hui)
        .aggregate(t=Sum("montant"))["t"]
        or ZERO
    )
    solde_actuel = solde_theorique_total - flux_futurs_tous

    flux_futurs_mois = (
        Flux.objects.filter(
            compte__actif=True,
            date_flux__gt=aujourd_hui,
            date_flux__lte=fin_mois,
            est_transfert=False,
            est_ajustement=False,
        ).aggregate(t=Sum("montant"))["t"]
        or ZERO
    )

    reste = reste_a_depenser_budgete(mois_courant)

    compteur = compteur_flux_futurs(aujourd_hui, fin_mois)
    couvertes = categories_budgetees(mois_courant)
    abonnements = abonnements_a_echoir(aujourd_hui, fin_mois, compteur, couvertes)
    total_abonnements = abonnements["recettes"] + abonnements["depenses"]

    return {
        "definition": (
            "Projection consultative du solde bancaire total des comptes "
            "actifs en fin de mois courant. N'est pas une vérité comptable : "
            "le solde réel reste la seule référence."
        ),
        "fiabilite": "elevee",
        "composantes": {
            "solde_actuel": solde_actuel,
            "flux_futurs_mois": flux_futurs_mois,
            "abonnements_a_echoir_non_budgetes": total_abonnements,
            "reste_a_depenser_budgete": reste,
        },
        "solde_projete": solde_actuel + flux_futurs_mois + total_abonnements - reste,
    }


# ---------------------------------------------------------------------------
# Indicateur 2 — Capacité à dépenser restante
# ---------------------------------------------------------------------------

def calculer_capacite_restante(aujourd_hui=None) -> dict:
    """
    Capacité à dépenser restante sur le mois courant :

        capacite = total_budgets - total_consomme - abonnements_restants

    abonnements_restants = dépenses d'abonnement à échoir non couvertes par
    un budget (les couvertes consommeront leur enveloppe : déjà comptées).
    Peut être négative (dépassement). Fiabilité : PROJETÉE (moyenne — dépend
    du réalisme des budgets saisis).
    """
    from budgets.models import Budget

    aujourd_hui = _aujourd_hui_ou(aujourd_hui)
    mois_courant = _mois_de(aujourd_hui)
    fin_mois = _fin_de_mois(mois_courant)

    agregats = Budget.objects.filter(mois=mois_courant).aggregate(
        prevu=Sum("montant_prevu"), consomme=Sum("montant_consomme")
    )
    total_budgets = agregats["prevu"] or ZERO
    total_consomme = agregats["consomme"] or ZERO

    compteur = compteur_flux_futurs(aujourd_hui, fin_mois)
    couvertes = categories_budgetees(mois_courant)
    abonnements = abonnements_a_echoir(aujourd_hui, fin_mois, compteur, couvertes)
    abonnements_restants = -abonnements["depenses"]  # exposé en positif

    return {
        "definition": (
            "Montant encore dépensable ce mois dans le cadre des budgets, "
            "après consommation constatée et abonnements restants non "
            "couverts par un budget. Projection consultative."
        ),
        "fiabilite": "moyenne",
        "composantes": {
            "total_budgets": total_budgets,
            "total_consomme": total_consomme,
            "abonnements_restants": abonnements_restants,
        },
        "capacite": total_budgets - total_consomme - abonnements_restants,
    }


# ---------------------------------------------------------------------------
# Agrégat de l'endpoint /analytics/previsionnel/
# ---------------------------------------------------------------------------

def calculer_previsionnel(nb_mois: int = 6, aujourd_hui=None) -> dict:
    """Assemble les trois blocs du prévisionnel. Lecture seule, projeté."""
    from .trajectoire import calculer_trajectoire

    aujourd_hui = _aujourd_hui_ou(aujourd_hui)
    return {
        "date_calcul": aujourd_hui.isoformat(),
        "mois_courant": _mois_de(aujourd_hui).isoformat(),
        "solde_projete": calculer_solde_projete(aujourd_hui),
        "capacite_restante": calculer_capacite_restante(aujourd_hui),
        "trajectoire": calculer_trajectoire(nb_mois, aujourd_hui),
    }
