from django.db import models
from core.models import BaseModel


class BudgetTemplate(BaseModel):
    """
    Modèle de budget récurrent mensuel.

    Règles :
    - Un seul template par catégorie.
    - montant_defaut > 0 : valeur proposée à chaque reconduction.
    - est_budget_majeur est auto-détecté (backend autoritatif).
    - categories_incluses : miroir de Budget.categories_incluses pour les majeures.
    - La reconduction crée un Budget concret pour un mois donné ;
      le budget instancié garde un lien FK vers ce template.
    - Désactiver (actif=False) plutôt que supprimer pour conserver l'historique
      des budgets déjà instanciés.
    """

    categorie = models.ForeignKey(
        "categories.Categorie",
        on_delete=models.PROTECT,
        related_name="budget_templates",
    )
    montant_defaut = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant proposé à chaque reconduction. Toujours positif."
    )
    categories_incluses = models.ManyToManyField(
        "categories.Categorie",
        blank=True,
        related_name="budget_templates_incluant",
        help_text="Sous-catégories incluses (pertinent si est_budget_majeur=True)."
    )
    est_budget_majeur = models.BooleanField(
        default=False,
        help_text="Auto-détecté : True si la catégorie est une majeure avec mineures actives."
    )
    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Modèle de budget"
        verbose_name_plural = "Modèles de budget"
        ordering = ["categorie__nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["categorie"],
                condition=models.Q(is_deleted=False),
                name="budgettemplate_unique_categorie"
            )
        ]

    def __str__(self):
        statut = "" if self.actif else " [inactif]"
        return f"Template {self.categorie.nom} — {self.montant_defaut} €{statut}"


class Budget(BaseModel):
    """
    Budget prévisionnel pour une catégorie donnée sur un mois donné.

    Règles :
    - Un seul budget par couple (categorie, mois).
    - mois = toujours le 1er du mois (ex: 2024-03-01).
    - montant_prevu > 0 (toujours positif, représente une enveloppe).
    - montant_consomme et taux_consommation sont calculés par le service.
    - Jamais éditables manuellement.
    - template (nullable) : référence au BudgetTemplate dont ce budget est issu.
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

    est_budget_majeur = models.BooleanField(
        default=False,
        help_text="True si la catégorie ciblée est une majeure (agrège les mineures incluses)."
    )
    categories_incluses = models.ManyToManyField(
        "categories.Categorie",
        blank=True,
        related_name="budgets_incluant",
        help_text="Sous-catégories incluses dans ce budget majeur (pertinent uniquement si est_budget_majeur=True)."
    )
    template = models.ForeignKey(
        BudgetTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="budgets_mensuels",
        help_text="Template dont ce budget est issu. Null = budget ponctuel créé manuellement."
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Budget"
        verbose_name_plural = "Budgets"
        ordering = ["-mois", "categorie__nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["categorie", "mois"],
                condition=models.Q(is_deleted=False),
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
