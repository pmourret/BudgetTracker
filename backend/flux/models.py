from django.db import models
from django.utils import timezone
from core.models import BaseModel
from referentiels.models import (
    TypeFlux, Titulaire, ModePaiement, StatutFlux, Devise
)


class Flux(BaseModel):
    """
    Journal central de tous les mouvements financiers.

    Règles critiques :
    - montant signé : négatif = dépense, positif = recette
    - mois calculé automatiquement depuis date_flux (1er du mois)
    - est_transfert = True si le flux fait partie d'un transfert interne
    - les transferts ne sont jamais comptabilisés comme dépenses
    - un flux soft-deleté déclenche le recalcul du solde du compte
    """

    # Compte rattaché — import local pour éviter la circularité
    compte = models.ForeignKey(
        "comptes.Compte",
        on_delete=models.PROTECT,
        related_name="flux",
    )
    categorie = models.ForeignKey(
        "categories.Categorie",
        on_delete=models.PROTECT,
        related_name="flux",
        null=True,
        blank=True,
        help_text="Null autorisé uniquement pour les transferts internes."
    )

    # Référentiels
    type_flux = models.ForeignKey(
        TypeFlux,
        on_delete=models.PROTECT,
        related_name="flux",
    )
    titulaire = models.ForeignKey(
        Titulaire,
        on_delete=models.PROTECT,
        related_name="flux",
        null=True,
        blank=True,
    )
    mode_paiement = models.ForeignKey(
        ModePaiement,
        on_delete=models.PROTECT,
        related_name="flux",
        null=True,
        blank=True,
    )
    statut = models.ForeignKey(
        StatutFlux,
        on_delete=models.PROTECT,
        related_name="flux",
    )
    devise = models.ForeignKey(
        Devise,
        on_delete=models.PROTECT,
        related_name="flux",
    )

    # Données financières
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant signé : négatif = dépense, positif = recette."
    )
    date_flux = models.DateField(
        default=timezone.now,
        help_text="Date réelle du mouvement."
    )
    mois = models.DateField(
        editable=False,
        help_text="Premier jour du mois de date_flux. Calculé automatiquement."
    )

    # Flags
    est_transfert = models.BooleanField(
        default=False,
        help_text="True si ce flux fait partie d'un transfert interne entre comptes."
    )
    est_ajustement = models.BooleanField(
        default=False,
        help_text="True si ce flux est un ajustement de solde généré par la réconciliation. "
                  "Exclu de tous les agrégats dépenses/revenus."
    )

    # Metadata
    libelle = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    reference_externe = models.CharField(
        max_length=100,
        blank=True,
        help_text="Référence bancaire ou numéro de pièce."
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Flux"
        verbose_name_plural = "Flux"
        ordering = ["-date_flux", "-created_at"]
        indexes = [
            models.Index(fields=["compte", "mois"]),
            models.Index(fields=["compte", "date_flux"]),
            models.Index(fields=["categorie", "mois"]),
            models.Index(fields=["est_transfert"]),
            models.Index(fields=["est_ajustement"]),
        ]

    def __str__(self):
        signe = "+" if self.montant >= 0 else ""
        return f"{self.date_flux} | {signe}{self.montant} € | {self.libelle or 'Sans libellé'}"

    def _calculer_mois(self):
        """Retourne le premier jour du mois de date_flux."""
        return self.date_flux.replace(day=1)

    def save(self, *args, **kwargs):
        """
        Calcule le champ `mois` avant chaque sauvegarde.
        Le recalcul du solde est déclenché par signal (étape 4B).
        """
        self.mois = self._calculer_mois()
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete — le recalcul du solde est déclenché par signal (étape 4B).
        """
        super().delete(using=using, keep_parents=keep_parents)