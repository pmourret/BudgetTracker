from decimal import Decimal
from django.db import transaction
from django.db.models import Sum


def _calculer_consommation_avec_model(budget, FluxModel) -> None:
    """
    Logique pure — séparée pour être testable sans dépendance à Flux.

    Budget majeur : somme des flux des mineures incluses dans categories_incluses.
    Budget mineure : somme des flux de la catégorie directe.
    Dans les deux cas : exclut les transferts et les flux d'ajustement.
    """
    with transaction.atomic():
        if budget.est_budget_majeur:
            categories = list(budget.categories_incluses.all())
            total = (
                FluxModel.objects
                .filter(
                    categorie__in=categories,
                    mois=budget.mois,
                    montant__lt=0,
                    est_transfert=False,
                    est_ajustement=False,
                )
                .aggregate(total=Sum("montant"))
                ["total"]
            ) or Decimal("0.00")
        else:
            total = (
                FluxModel.objects
                .filter(
                    categorie=budget.categorie,
                    mois=budget.mois,
                    montant__lt=0,
                    est_transfert=False,
                    est_ajustement=False,
                )
                .aggregate(total=Sum("montant"))
                ["total"]
            ) or Decimal("0.00")

        budget.montant_consomme = abs(total)

        if budget.montant_prevu > 0:
            budget.taux_consommation = (
                budget.montant_consomme / budget.montant_prevu * 100
            ).quantize(Decimal("0.01"))
        else:
            budget.taux_consommation = Decimal("0.00")

        budget.save(update_fields=[
            "montant_consomme", "taux_consommation", "updated_at"
        ])


def calculer_consommation(budget) -> None:
    """
    Recalcule montant_consomme et taux_consommation pour un budget donné.

    Règles :
    - Budget mineure : somme des dépenses (montant < 0) sur la catégorie et le mois,
      hors transferts et ajustements.
    - Budget majeur : somme des dépenses des mineures incluses dans categories_incluses,
      hors transferts et ajustements.
    - taux_consommation = montant_consomme / montant_prevu * 100.
    - Si montant_prevu = 0, taux = 0 (pas de division par zéro).

    Fiabilité : réel.
    Fréquence : à chaque CREATE/UPDATE/DELETE de Flux.
    """
    from flux.models import Flux
    _calculer_consommation_avec_model(budget, Flux)


def calculer_consommation_pour_flux(flux) -> None:
    """
    Point d'entrée appelé par le signal sur Flux.
    Recalcule le/les budget(s) correspondant(s) si ils existent.
    """
    from budgets.models import Budget

    if flux.est_transfert or flux.categorie is None:
        return

    # Budget direct sur la catégorie du flux (mineure ou majeure ciblée directement)
    try:
        budget = Budget.objects.get(
            categorie=flux.categorie,
            mois=flux.mois,
        )
        calculer_consommation(budget)
    except Budget.DoesNotExist:
        pass

    # Budgets majeures qui incluent cette catégorie dans leurs mineures
    for budget_majeur in Budget.objects.filter(
        mois=flux.mois,
        est_budget_majeur=True,
        categories_incluses=flux.categorie,
    ):
        calculer_consommation(budget_majeur)
