"""
Services de projection financière — phase 10-A (lecture seule).

Tous les indicateurs de ce module sont de fiabilité PROJETÉE : une
projection n'est jamais une vérité comptable, le solde réel reste la
seule référence. Ces services LISENT flux / budgets et n'écrivent rien
(calcul à la volée, aucun modèle persisté).

Le patrimoine estimatif n'entre jamais dans ces projections (règle 10).
Transferts internes et flux d'ajustement sont exclus de toutes les
briques (mêmes filtres que analytics/services/dashboard.py).

Les abonnements ne sont PLUS pris en compte dans le prévisionnel : ils
sont devenus un référentiel dont l'utilisateur matérialise chaque échéance
en flux au moment du prélèvement (décision du foyer, juillet 2026). Seuls
les flux réellement saisis et les budgets nourrissent donc la projection.

Chaque service accepte un paramètre `aujourd_hui` injectable pour les
tests (même esprit que le pattern _calculer_xxx_avec_model).
"""
import datetime
from decimal import Decimal

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


# ---------------------------------------------------------------------------
# Couverture budgétaire du mois
# ---------------------------------------------------------------------------

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
                      - reste_a_depenser_budgete  (estimé)

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
            "reste_a_depenser_budgete": reste,
        },
        "solde_projete": solde_actuel + flux_futurs_mois - reste,
    }


# ---------------------------------------------------------------------------
# Indicateur 2 — Capacité à dépenser restante
# ---------------------------------------------------------------------------

def calculer_capacite_restante(aujourd_hui=None) -> dict:
    """
    Capacité à dépenser restante sur le mois courant :

        capacite = total_budgets - total_consomme

    Peut être négative (dépassement). Fiabilité : PROJETÉE (moyenne — dépend
    du réalisme des budgets saisis).
    """
    from budgets.models import Budget

    aujourd_hui = _aujourd_hui_ou(aujourd_hui)
    mois_courant = _mois_de(aujourd_hui)

    agregats = Budget.objects.filter(mois=mois_courant).aggregate(
        prevu=Sum("montant_prevu"), consomme=Sum("montant_consomme")
    )
    total_budgets = agregats["prevu"] or ZERO
    total_consomme = agregats["consomme"] or ZERO

    return {
        "definition": (
            "Montant encore dépensable ce mois dans le cadre des budgets, "
            "après consommation constatée. Projection consultative."
        ),
        "fiabilite": "moyenne",
        "composantes": {
            "total_budgets": total_budgets,
            "total_consomme": total_consomme,
        },
        "capacite": total_budgets - total_consomme,
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
