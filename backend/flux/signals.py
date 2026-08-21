from django.db.models.signals import post_delete, post_save, pre_save
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
    from alertes.services import detecter_alertes_budget
    from budgets.services.consommation import (
        calculer_consommation_pour_flux,
        recalculer_budgets_pour,
    )
    from comptes.services.solde import calculer_solde

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

    # Abonnement d'origine : mise à jour du suivi + divergence automatique
    if instance.abonnement_id:
        from abonnements.services import mettre_a_jour_derniere_occurrence
        from alertes.services import detecter_alerte_divergence_abonnement

        abonnement = instance.abonnement
        mettre_a_jour_derniere_occurrence(abonnement, instance.date_flux)
        detecter_alerte_divergence_abonnement(abonnement, instance.montant)

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
    """
    ⚠️ Recalculer la consommation ne suffit pas : il faut **réévaluer les
    alertes**. Sans cela, supprimer le flux qui avait fait franchir un seuil
    laissait l'alerte ouverte pour toujours — elle continuait d'annoncer un
    dépassement qui n'existait plus, et le dédoublonnage empêchait qu'une
    alerte juste vienne la remplacer. (D01 de la revue UI/UX du 2026-08-20.)
    """
    from alertes.services import refermer_alertes_budget_perimees
    from budgets.models import Budget
    from budgets.services.consommation import calculer_consommation_pour_flux
    from comptes.services.solde import calculer_solde

    calculer_solde(instance.compte)
    calculer_consommation_pour_flux(instance)

    if instance.est_transfert or instance.categorie_id is None:
        return

    budgets_concernes = Budget.objects.filter(
        categorie_id=instance.categorie_id,
        mois=instance.mois,
    ) | Budget.objects.filter(
        mois=instance.mois,
        categories_incluses=instance.categorie_id,
    )
    for budget in budgets_concernes.distinct():
        budget.refresh_from_db()
        refermer_alertes_budget_perimees(budget)
