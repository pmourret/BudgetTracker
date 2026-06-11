from django.db import models
from core.models import BaseModel


class Budget(BaseModel):
    """
    Budget prévisionnel pour une catégorie donnée sur un mois donné.

    Règles :
    - Un seul budget par couple (categorie, mois).
    - mois = toujours le 1er du mois (ex: 2024-03-01).
    - montant_prevu > 0 (toujours positif, représente une enveloppe).
    - montant_consomme et taux_consommation sont calculés par le service.
    - Jamais éditables manuellement.
    """

    categorie = models.ForeignKey(
        "categories.Categorie",
        on_delete=models.PROTECT,
        related_name="budgets",
    )
    mois = models.DateField(
        help_text="Premier jour du mois budgété (ex: 2024-03-01)."
    )
    montant_prevu = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Enveloppe budgétaire prévue. Toujours positif."
    )
    montant_consomme = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        editable=False,
        help_text="Calculé : somme des flux de dépense sur cette catégorie ce mois."
    )
    taux_consommation = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        editable=False,
        help_text="Calculé : montant_consomme / montant_prevu * 100."
    )
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Budget"
        verbose_name_plural = "Budgets"
        ordering = ["-mois", "categorie__nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["categorie", "mois"],
                name="budget_unique_categorie_mois"
            )
        ]
        indexes = [
            models.Index(fields=["mois"]),
            models.Index(fields=["categorie", "mois"]),
        ]

    def __str__(self):
        return f"{self.categorie.nom} | {self.mois:%Y-%m} | {self.montant_prevu} €"

    def save(self, *args, **kwargs):
        """Force le mois au 1er du mois avant chaque sauvegarde."""
        self.mois = self.mois.replace(day=1)
        super().save(*args, **kwargs)