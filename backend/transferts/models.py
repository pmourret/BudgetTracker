from django.db import models
from core.models import BaseModel


class Transfert(BaseModel):
    """
    Représente un transfert interne entre deux comptes.

    Un transfert lie deux flux :
    - flux_debit  : montant négatif sur le compte source
    - flux_credit : montant positif sur le compte destination

    Règles :
    - Les deux flux sont créés atomiquement (transaction).
    - est_transfert=True est positionné sur les deux flux.
    - Un transfert ne peut pas être supprimé physiquement.
    - L'annulation passe par le soft delete des deux flux liés.
    """

    flux_debit = models.OneToOneField(
        "flux.Flux",
        on_delete=models.PROTECT,
        related_name="transfert_debit",
        help_text="Flux négatif sur le compte source."
    )
    flux_credit = models.OneToOneField(
        "flux.Flux",
        on_delete=models.PROTECT,
        related_name="transfert_credit",
        help_text="Flux positif sur le compte destination."
    )
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant transféré (toujours positif)."
    )
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Transfert"
        verbose_name_plural = "Transferts"

    def __str__(self):
        return (
            f"Transfert {self.montant} € | "
            f"{self.flux_debit.compte} → {self.flux_credit.compte} | "
            f"{self.flux_debit.date_flux}"
        )

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete du transfert + soft delete atomique des deux flux liés.
        Le recalcul des soldes est déclenché par les signals sur chaque flux.
        """
        from django.db import transaction
        with transaction.atomic():
            self.flux_debit.delete()
            self.flux_credit.delete()
            super().delete(using=using, keep_parents=keep_parents)