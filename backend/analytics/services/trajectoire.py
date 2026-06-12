"""
Service de trajectoire d'épargne projetée — phase 10-A (lecture seule).

Pour chaque mois de l'horizon : épargne = revenus_attendus − dépenses_attendues,
cumulée. Fiabilité dégressive avec l'horizon (élevée / moyenne / faible).
Projection consultative : jamais une vérité comptable.

Sources par mois :
- mois courant : flux du mois (réalisés + futurs datés) + reste à dépenser
  budgété + abonnements à échoir non budgétés — mêmes briques que le solde
  projeté (projection.py) ;
- mois futurs : flux futurs datés + échéances d'abonnements + enveloppes des
  BudgetTemplates actifs (estimation des dépenses variables, miroir de la
  reconduction phase 11c). Sans double comptage : la part déjà couverte par
  flux datés ou abonnements est déduite de chaque enveloppe.
"""
import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Sum

from .projection import (
    ZERO,
    _aujourd_hui_ou,
    _fin_de_mois,
    _mois_de,
    abonnements_a_echoir,
    categories_budgetees,
    compteur_flux_futurs,
    filtrer_echeances_deja_saisies,
    occurrences_abonnement,
    reste_a_depenser_budgete,
)


def _fiabilite_pour(indice_mois: int) -> str:
    """Fiabilité dégressive : M0 élevée, M+1 à M+3 moyenne, au-delà faible."""
    if indice_mois == 0:
        return "elevee"
    if indice_mois <= 3:
        return "moyenne"
    return "faible"


def _abonnements_actifs():
    from abonnements.models import Abonnement
    return list(
        Abonnement.objects.filter(actif=True).select_related("frequence")
    )


def _enveloppes_templates():
    """
    Liste (template, ids des catégories couvertes) des templates actifs :
    la catégorie du template + ses mineures incluses s'il est majeur.
    """
    from budgets.models import BudgetTemplate

    enveloppes = []
    templates = BudgetTemplate.objects.filter(actif=True).prefetch_related(
        "categories_incluses"
    )
    for template in templates:
        categories = {template.categorie_id}
        if template.est_budget_majeur:
            categories.update(
                template.categories_incluses.values_list("id", flat=True)
            )
        enveloppes.append((template, categories))
    return enveloppes


def _point_mois_courant(aujourd_hui, mois, compteur):
    """
    Revenus / dépenses attendus du mois courant : flux du mois (réalisés et
    futurs datés) + reste à dépenser budgété + abonnements non budgétés.
    """
    from flux.models import Flux

    fin_mois = _fin_de_mois(mois)
    flux_mois = Flux.objects.filter(
        mois=mois, est_transfert=False, est_ajustement=False
    )
    revenus_flux = (
        flux_mois.filter(montant__gt=0).aggregate(t=Sum("montant"))["t"] or ZERO
    )
    depenses_flux = -(
        flux_mois.filter(montant__lt=0).aggregate(t=Sum("montant"))["t"] or ZERO
    )

    reste = reste_a_depenser_budgete(mois)
    couvertes = categories_budgetees(mois)
    abonnements = abonnements_a_echoir(aujourd_hui, fin_mois, compteur, couvertes)

    revenus = revenus_flux + abonnements["recettes"]
    depenses = depenses_flux + reste - abonnements["depenses"]
    return revenus, depenses


def _point_mois_futur(aujourd_hui, mois, compteur, abonnements, enveloppes):
    """
    Revenus / dépenses attendus d'un mois futur : flux futurs datés +
    échéances d'abonnements (dédupliquées) + complément des enveloppes de
    templates au-delà de la part déjà couverte par flux/abonnements.
    """
    from flux.models import Flux

    fin_mois = _fin_de_mois(mois)
    debut_fenetre = max(aujourd_hui, mois - datetime.timedelta(days=1))

    flux_mois = Flux.objects.filter(
        mois=mois,
        date_flux__gt=aujourd_hui,
        est_transfert=False,
        est_ajustement=False,
    )
    revenus = (
        flux_mois.filter(montant__gt=0).aggregate(t=Sum("montant"))["t"] or ZERO
    )

    # Dépenses datées par catégorie (en positif), pour déduire la part déjà
    # couverte de chaque enveloppe de template.
    depenses_par_categorie = {}
    lignes = (
        flux_mois.filter(montant__lt=0)
        .values("categorie_id")
        .annotate(t=Sum("montant"))
    )
    for ligne in lignes:
        depenses_par_categorie[ligne["categorie_id"]] = -ligne["t"]
    depenses = sum(depenses_par_categorie.values(), ZERO)

    # Échéances d'abonnements du mois, dédupliquées des flux datés.
    abos_par_categorie = {}
    for abonnement in abonnements:
        echeances = occurrences_abonnement(abonnement, debut_fenetre, fin_mois)
        echeances = filtrer_echeances_deja_saisies(abonnement, echeances, compteur)
        montant = abonnement.montant_attendu * len(echeances)
        if abonnement.montant_attendu >= 0:
            revenus += montant
        else:
            depenses += -montant
            cle = abonnement.categorie_id
            abos_par_categorie[cle] = abos_par_categorie.get(cle, ZERO) - montant

    # Enveloppes des templates actifs : estimation des dépenses variables,
    # complément au-delà de la part déjà couverte par flux datés/abonnements.
    for template, categories in enveloppes:
        deja_couvert = sum(
            (
                depenses_par_categorie.get(c, ZERO) + abos_par_categorie.get(c, ZERO)
                for c in categories
            ),
            ZERO,
        )
        depenses += max(ZERO, template.montant_defaut - deja_couvert)

    return revenus, depenses


def calculer_trajectoire(nb_mois: int = 6, aujourd_hui=None) -> dict:
    """
    Trajectoire d'épargne projetée sur nb_mois (mois courant inclus).
    Chaque point porte sa fiabilité propre (dégressive avec l'horizon) ;
    le bloc porte la fiabilité du point le plus lointain (la plus faible).
    """
    aujourd_hui = _aujourd_hui_ou(aujourd_hui)
    mois_courant = _mois_de(aujourd_hui)
    fin_horizon = _fin_de_mois(mois_courant + relativedelta(months=nb_mois - 1))

    compteur = compteur_flux_futurs(aujourd_hui, fin_horizon)
    abonnements = _abonnements_actifs()
    enveloppes = _enveloppes_templates()

    points = []
    cumul = ZERO
    for indice in range(nb_mois):
        mois = mois_courant + relativedelta(months=indice)
        if indice == 0:
            revenus, depenses = _point_mois_courant(aujourd_hui, mois, compteur)
        else:
            revenus, depenses = _point_mois_futur(
                aujourd_hui, mois, compteur, abonnements, enveloppes
            )
        epargne = revenus - depenses
        cumul += epargne
        points.append({
            "mois": mois.isoformat(),
            "revenus_attendus": revenus,
            "depenses_attendues": depenses,
            "epargne_mois": epargne,
            "cumul": cumul,
            "fiabilite": _fiabilite_pour(indice),
        })

    return {
        "definition": (
            "Épargne projetée mois par mois (revenus attendus − dépenses "
            "attendues), cumulée. Projection consultative à fiabilité "
            "dégressive avec l'horizon, jamais une vérité comptable."
        ),
        "fiabilite": _fiabilite_pour(nb_mois - 1),
        "nb_mois": nb_mois,
        "points": points,
    }
