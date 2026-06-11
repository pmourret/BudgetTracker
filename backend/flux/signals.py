from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Flux


@receiver(post_save, sender=Flux)
def recalculer_apres_save(sender, instance, **kwargs):
    from comptes.services.solde import calculer_solde
    from budgets.services.consommation import calculer_consommation_pour_flux
    from alertes.services import detecter_alertes_budget

    calculer_solde(instance.compte)
    calculer_consommation_pour_flux(instance)

    # Détection alertes budget si un budget existe pour ce flux
    if not instance.est_transfert and instance.categorie:
        from budgets.models import Budget
        try:
            budget = Budget.objects.get(
                categorie=instance.categorie,
                mois=instance.mois,
            )
            detecter_alertes_budget(budget)
        except Budget.DoesNotExist:
            pass


@receiver(post_delete, sender=Flux)
def recalculer_apres_delete(sender, instance, **kwargs):
    from comptes.services.solde import calculer_solde
    from budgets.services.consommation import calculer_consommation_pour_flux

    calculer_solde(instance.compte)
    calculer_consommation_pour_flux(instance)