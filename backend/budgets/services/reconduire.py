from datetime import date
from django.db import transaction

from .consommation import calculer_consommation


def reconduire_vers_mois(mois_cible: date) -> dict:
    """
    Crée les budgets du mois cible depuis tous les templates actifs.

    Idempotent : si un budget existe déjà pour (categorie, mois_cible),
    ce template est ignoré (pas d'écrasement).

    Retourne un dict :
    {
        "crees": int,          # nombre de budgets créés
        "ignores": int,        # budgets déjà existants, non touchés
        "details_crees": [...] # noms des catégories créées
        "details_ignores": [...] # noms des catégories ignorées
    }

    Fiabilité : réel (les montants_consomme sont recalculés après création).
    """
    from budgets.models import Budget, BudgetTemplate

    mois = mois_cible.replace(day=1)
    details_crees = []
    details_ignores = []

    with transaction.atomic():
        templates = (
            BudgetTemplate.objects
            .filter(actif=True)
            .select_related("categorie")
            .prefetch_related("categories_incluses")
        )

        for template in templates:
            if Budget.objects.filter(categorie=template.categorie, mois=mois).exists():
                details_ignores.append(template.categorie.nom)
                continue

            budget = Budget.objects.create(
                categorie=template.categorie,
                mois=mois,
                montant_prevu=template.montant_defaut,
                est_budget_majeur=template.est_budget_majeur,
                template=template,
                notes=template.notes,
            )
            budget.categories_incluses.set(template.categories_incluses.all())
            calculer_consommation(budget)
            details_crees.append(template.categorie.nom)

    return {
        "crees": len(details_crees),
        "ignores": len(details_ignores),
        "details_crees": details_crees,
        "details_ignores": details_ignores,
    }
