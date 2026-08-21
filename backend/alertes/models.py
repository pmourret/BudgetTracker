from django.db import models

from core.models import BaseModel


class TypeAlerte(models.TextChoices):
    """
    Types d'alertes supportés.
    Extensible sans migration — ajout d'une valeur ici suffit.
    """
    BUDGET_DEPASSE = "BUDGET_DEPASSE", "Budget dépassé"
    BUDGET_ALERTE = "BUDGET_ALERTE", "Budget en alerte (seuil approche)"
    SOLDE_BAS = "SOLDE_BAS", "Solde bas"
    ABONNEMENT_EN_RETARD = "ABONNEMENT_EN_RETARD", "Abonnement en retard"
    ABONNEMENT_DIVERGENCE = "ABONNEMENT_DIVERGENCE", "Divergence de montant abonnement"
    ECART_SOLDE = "ECART_SOLDE", "Écart de solde inhabituel"


class NiveauAlerte(models.TextChoices):
    INFO = "INFO", "Information"
    AVERTISSEMENT = "AVERTISSEMENT", "Avertissement"
    CRITIQUE = "CRITIQUE", "Critique"


class Alerte(BaseModel):
    """
    Alerte générée automatiquement par les services de détection.

    Règles :
    - Toujours explicable : le champ `explication` décrit le contexte.
    - Non culpabilisante : ton neutre et factuel.
    - Configurable : les seuils viennent des modèles liés, jamais codés en dur.
    - acquittee = True → l'utilisateur a pris connaissance de l'alerte.
    - Une alerte acquittée reste visible dans l'historique (soft delete).
    """

    type_alerte = models.CharField(
        max_length=50,
        choices=TypeAlerte.choices,
    )
    niveau = models.CharField(
        max_length=20,
        choices=NiveauAlerte.choices,
        default=NiveauAlerte.AVERTISSEMENT,
    )

    # Contexte — une seule de ces FK sera renseignée selon le type
    compte = models.ForeignKey(
        "comptes.Compte",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alertes",
    )
    budget = models.ForeignKey(
        "budgets.Budget",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alertes",
    )
    abonnement = models.ForeignKey(
        "abonnements.Abonnement",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alertes",
    )

    # Explication lisible — obligatoire
    explication = models.TextField(
        help_text="Description factuelle et neutre de la situation détectée."
    )

    # Valeurs au moment de la détection (snapshot)
    valeur_constatee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valeur mesurée au moment de la détection."
    )
    valeur_seuil = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Seuil configuré au moment de la détection."
    )

    # Suivi
    acquittee = models.BooleanField(
        default=False,
        help_text="True si l'utilisateur a pris connaissance de l'alerte."
    )
    acquittee_le = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )

    actif = models.ForeignKey(
        "patrimoine.Actif",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alertes",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"
        ordering = ["-created_at"]
        constraints = [
            # ⚠️ **Le dédoublonnage était une course, pas une garantie.**
            #
            # Les sept générateurs faisaient `filter(...).exists()` **puis**
            # `create()`. Entre les deux, rien : deux appels concurrents
            # passaient tous deux le test et créaient tous deux. Deux alertes
            # « Abonnement en retard » identiques coexistaient en base, créées
            # à la même seconde — et `verifier-echeances` **documentait**
            # pourtant une idempotence qu'il n'assurait pas.
            # (D27 de la revue UI/UX du 2026-08-20.)
            #
            # ⚠️ `condition` porte **`is_deleted=False`** : sur un `BaseModel`,
            # une contrainte qui l'oublie compte aussi les lignes soft-deletées
            # et bloque une recréation légitime (piège du §7).
            #
            # ⚠️ `nulls_distinct=False` est **indispensable** : une seule des
            # quatre cibles est renseignée, les trois autres sont `NULL`, et
            # PostgreSQL considère par défaut deux `NULL` comme distincts — la
            # contrainte n'aurait alors jamais mordu. Demande PostgreSQL 15+
            # (on est en 16) et Django 5+ (on est en 6).
            models.UniqueConstraint(
                "type_alerte",
                "compte",
                "budget",
                "abonnement",
                "actif",
                condition=models.Q(acquittee=False, is_deleted=False),
                nulls_distinct=False,
                name="alerte_ouverte_unique_par_cible",
            ),
        ]
        indexes = [
            models.Index(fields=["type_alerte", "acquittee"]),
            models.Index(fields=["compte"]),
            models.Index(fields=["budget"]),
            models.Index(fields=["abonnement"]),
            models.Index(fields=["actif"]),
        ]

    def __str__(self):
        return f"{self.get_type_alerte_display()} | {self.niveau} | {self.created_at:%Y-%m-%d}"

    def acquitter(self):
        """Marque l'alerte comme acquittée."""
        from django.utils import timezone
        self.acquittee = True
        self.acquittee_le = timezone.now()
        self.save(update_fields=["acquittee", "acquittee_le", "updated_at"])