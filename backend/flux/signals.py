from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from .models import Flux


@receiver(pre_save, sender=Flux)
def memoriser_etat_precedent(sender, instance, **kwargs):
    """
    Mémorise compte/catégorie/mois avant sauvegarde.

    Si l'un de ces champs change, l'ancien compte et les anciens budgets
    doivent aussi être recalculés (sinon ils gardent des valeurs périmées).
    """
    instance._etat_precedent = (
        Flux.objects.all_with_deleted()
        .filter(pk=instance.pk)
        .values("compte_id", "categorie_id", "mois")
        .first()
    )


@receiver(post_save, sender=Flux)
def recalculer_apres_save(sender, instance, **kwargs):
    from comptes.services.solde import calculer_solde
    from budgets.services.consommation import (
        calculer_consommation_pour_flux,
        recalculer_budgets_pour,
    )
    from alertes.services import detecter_alertes_budget

    calculer_solde(instance.compte)
    calculer_consommation_pour_flux(instance)

    # Si le flux a changé de compte / catégorie / mois, recalculer aussi l'ancien
    precedent = getattr(instance, "_etat_precedent", None)
    if precedent:
        if precedent["compte_id"] != instance.compte_id:
            from comptes.models import Compte
            ancien_compte = (
                Compte.objects.all_with_deleted()
                .filter(pk=precedent["compte_id"])
                .first()
            )
            if ancien_compte:
                calculer_solde(ancien_compte)

        if (
            precedent["categorie_id"] != instance.categorie_id
            or precedent["mois"] != instance.mois
        ):
            recalculer_budgets_pour(precedent["categorie_id"], precedent["mois"])

    # Détection alertes budget : budget direct + budgets majeurs incluant la catégorie
    if not instance.est_transfert and instance.categorie_id:
        from budgets.models import Budget
        budgets_concernes = Budget.objects.filter(
            categorie_id=instance.categorie_id,
            mois=instance.mois,
        ) | Budget.objects.filter(
            mois=instance.mois,
            est_budget_majeur=True,
            categories_incluses=instance.categorie_id,
        )
        for budget in budgets_concernes.distinct():
            detecter_alertes_budget(budget)


@receiver(post_delete, sender=Flux)
def recalculer_apres_delete(sender, instance, **kwargs):
    from comptes.services.solde import calculer_solde
    from budgets.services.consommation import calculer_consommation_pour_flux

    calculer_solde(instance.compte)
    calculer_consommation_pour_flux(instance)
