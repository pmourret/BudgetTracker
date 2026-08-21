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
        null=True,
        blank=True,
        help_text="Catégorie ancre (simple ou majeure). Null = budget thématique (voir nom)."
    )
    nom = models.CharField(
        max_length=120,
        blank=True,
        help_text="Libellé du modèle. Requis pour un budget thématique (categorie null)."
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
        help_text="Catégories couvertes (mineures d'une majeure, ou feuilles libres d'un thématique)."
    )
    est_budget_majeur = models.BooleanField(
        default=False,
        help_text="Auto-détecté : True si la catégorie est une majeure avec mineures actives."
    )
    en_jeu = models.BooleanField(
        default=False,
        help_text="Mécanique B (points) : l'enveloppe participe au calcul des points. "
                  "Reporté sur les budgets reconduits depuis ce modèle."
    )
    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Modèle de budget"
        verbose_name_plural = "Modèles de budget"
        ordering = ["categorie__nom", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["categorie"],
                condition=models.Q(is_deleted=False, categorie__isnull=False),
                name="budgettemplate_unique_categorie"
            ),
            models.UniqueConstraint(
                fields=["nom"],
                condition=models.Q(is_deleted=False, categorie__isnull=True),
                name="budgettemplate_unique_nom_thematique"
            ),
        ]

    def __str__(self):
        statut = "" if self.actif else " [inactif]"
        libelle = self.categorie.nom if self.categorie_id else self.nom
        return f"Template {libelle} — {self.montant_defaut} €{statut}"


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
        null=True,
        blank=True,
        help_text="Catégorie ancre (simple ou majeure). Null = budget thématique (voir nom)."
    )
    nom = models.CharField(
        max_length=120,
        blank=True,
        help_text="Libellé du budget. Requis pour un budget thématique (categorie null)."
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
        help_text="Catégories couvertes (mineures d'une majeure, ou feuilles libres d'un thématique)."
    )
    template = models.ForeignKey(
        BudgetTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="budgets_mensuels",
        help_text="Template dont ce budget est issu. Null = budget ponctuel créé manuellement."
    )
    en_jeu = models.BooleanField(
        default=False,
        help_text="Mécanique B (points) : cette enveloppe participe au calcul des points "
                  "du mois (sous-consommé → gain, dépassé → perte)."
    )
    points_alloues = models.PositiveIntegerField(
        default=0,
        help_text="Mécanique B (12-B-2) : points distribués depuis la réserve vers cette "
                  "enveloppe. Prévu effectif = montant_prevu + points_alloues × valeur_point."
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Budget"
        verbose_name_plural = "Budgets"
        ordering = ["-mois", "categorie__nom", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["categorie", "mois"],
                condition=models.Q(is_deleted=False, categorie__isnull=False),
                name="budget_unique_categorie_mois"
            ),
            models.UniqueConstraint(
                fields=["nom", "mois"],
                condition=models.Q(is_deleted=False, categorie__isnull=True),
                name="budget_unique_nom_mois_thematique"
            ),
        ]
        indexes = [
            models.Index(fields=["mois"]),
            models.Index(fields=["categorie", "mois"]),
        ]

    @property
    def libelle(self) -> str:
        """
        Nom lisible du budget, quelle que soit sa forme.

        ⚠️ `categorie` est **nullable** : un budget thématique n'en a pas, il
        porte un `nom`. Écrire `budget.categorie.nom` plante donc sur un
        thématique — et comme la détection d'alertes tourne dans un signal
        `post_save` de Flux, le plantage remonte en 500 sur la création du flux.
        Passer par cette propriété, jamais par `categorie.nom`.
        """
        return (self.categorie.nom if self.categorie_id else self.nom) or "?"

    def __str__(self):
        return f"{self.libelle} | {self.mois:%Y-%m} | {self.montant_prevu} €"

    def save(self, *args, **kwargs):
        """Force le mois au 1er du mois avant chaque sauvegarde."""
        self.mois = self.mois.replace(day=1)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete — et **referme les alertes que ce budget avait levées**.

        Une alerte survivait à la disparition de son objet : le budget quittait
        l'application, sa phrase restait dans « Alertes récentes », datée et
        affirmative, à côté d'un tableau où le budget n'existait plus. Constaté
        le 2026-08-21 sur un budget de juin soft-deleté dont l'alerte
        s'affichait encore.

        C'est le second déclencheur de la règle posée par ADR-0067 — « une
        alerte se referme quand sa cause disparaît ». Le premier était le retour
        sous le seuil ; celui-ci est la disparition pure et simple.
        """
        from alertes.models import Alerte

        for alerte in Alerte.objects.filter(budget=self, acquittee=False):
            alerte.acquitter()

        super().delete(using=using, keep_parents=keep_parents)
