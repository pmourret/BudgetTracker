from django.db import models
from core.models import BaseModel


class TypeActif(models.TextChoices):
    """
    Types d'actifs patrimoniaux supportés.
    Jamais codés en dur dans la logique métier.
    """
    IMMOBILIER = "IMMOBILIER", "Immobilier"
    EPARGNE = "EPARGNE", "Épargne bancaire"
    PEA = "PEA", "PEA"
    ASSURANCE_VIE = "ASSURANCE_VIE", "Assurance-vie"
    COMPTE_TITRES = "COMPTE_TITRES", "Compte-titres"
    CRYPTO = "CRYPTO", "Crypto-actifs"
    AUTRE = "AUTRE", "Autre"


class Actif(BaseModel):
    """
    Représente un actif patrimonial non bancaire.

    Règles critiques :
    - La valorisation est TOUJOURS estimative — jamais une vérité comptable.
    - Ces données n'impactent JAMAIS les soldes bancaires réels.
    - valeur_actuelle est saisie manuellement ou enrichie via market_data
      (phase 12) — toujours traitée comme estimative.
    - valeur_acquisition sert au calcul de la plus-value latente estimative.
    """

    nom = models.CharField(max_length=150)
    type_actif = models.CharField(
        max_length=30,
        choices=TypeActif.choices,
    )

    # Compte bancaire lié (optionnel — ex: PEA lié à un compte espèces)
    compte_associe = models.ForeignKey(
        "comptes.Compte",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actifs",
        help_text="Compte bancaire associé à cet actif (optionnel)."
    )

    # Fiscalité depuis référentiel
    fiscalite = models.ForeignKey(
        "referentiels.Fiscalite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="actifs",
    )
    devise = models.ForeignKey(
        "referentiels.Devise",
        on_delete=models.PROTECT,
        related_name="actifs",
    )

    # Valorisation
    valeur_acquisition = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valeur au moment de l'acquisition. Saisie manuelle."
    )
    valeur_actuelle = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text=(
            "Valeur estimative actuelle. "
            "Saisie manuelle — jamais une vérité comptable."
        )
    )
    date_valorisation = models.DateField(
        null=True,
        blank=True,
        help_text="Date de la dernière valorisation manuelle."
    )

    # Périodicité de re-valorisation (rappel)
    frequence_valorisation = models.ForeignKey(
        "referentiels.Frequence",
        on_delete=models.PROTECT,
        related_name="actifs_a_valoriser",
        null=True,
        blank=True,
        help_text=(
            "Fréquence à laquelle cet actif doit être re-valorisé. "
            "Null = pas de rappel."
        )
    )
    rappel_jours_avant = models.PositiveSmallIntegerField(
        default=7,
        help_text="Nombre de jours avant l'échéance pour déclencher le rappel."
    )

    # Metadata
    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Actif patrimonial"
        verbose_name_plural = "Actifs patrimoniaux"
        ordering = ["type_actif", "nom"]
        indexes = [
            models.Index(fields=["type_actif"]),
            models.Index(fields=["actif"]),
        ]

    def __str__(self):
        return f"{self.get_type_actif_display()} | {self.nom} | {self.valeur_actuelle} €"

    @property
    def plus_value_latente(self):
        """
        Plus-value latente estimative = valeur_actuelle - valeur_acquisition.

        Fiabilité : ESTIMATIVE — basée sur des valorisations manuelles.
        Ne jamais présenter comme une vérité comptable.
        """
        if self.valeur_acquisition is None:
            return None
        return self.valeur_actuelle - self.valeur_acquisition

    @property
    def est_valorise_recemment(self):
        """
        Vrai si la valorisation date de moins de 30 jours.
        Indicateur de fraîcheur — fiabilité estimative.
        """
        import datetime
        if not self.date_valorisation:
            return False
        delta = datetime.date.today() - self.date_valorisation
        return delta.days <= 30

    @property
    def date_prochaine_valorisation(self):
        """Date à laquelle l'actif devrait être re-valorisé. Estimative."""
        import datetime
        if not self.frequence_valorisation or not self.date_valorisation:
            return None
        nb_jours = self.frequence_valorisation.nb_jours
        if not nb_jours:
            return None
        return self.date_valorisation + datetime.timedelta(days=nb_jours)

    @property
    def valorisation_a_faire(self):
        """Vrai si on entre dans la fenêtre de rappel. Estimative."""
        import datetime
        prochaine = self.date_prochaine_valorisation
        if not prochaine:
            return False
        seuil = prochaine - datetime.timedelta(days=self.rappel_jours_avant)
        return datetime.date.today() >= seuil


class HistoriqueValorisation(BaseModel):
    """
    Point d'historique de la valeur estimative d'un actif.

    Granularité fine : un point est créé à CHAQUE valorisation,
    plusieurs points par mois sont donc possibles.

    Pour une courbe mensuelle, on prend la dernière valorisation
    de chaque mois (la plus récente par date_valorisation).

    Fiabilité : ESTIMATIVE — comme toute valeur patrimoniale.
    Ces points ne touchent jamais aux soldes bancaires réels.
    """

    actif = models.ForeignKey(
        "patrimoine.Actif",
        on_delete=models.CASCADE,
        related_name="historique_valorisations",
    )
    valeur = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Valeur estimative enregistrée à cette date."
    )
    date_valorisation = models.DateField(
        help_text="Date à laquelle cette valeur a été constatée."
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Historique de valorisation"
        verbose_name_plural = "Historiques de valorisation"
        ordering = ["-date_valorisation", "-created_at"]
        indexes = [
            models.Index(fields=["actif", "date_valorisation"]),
        ]

    def __str__(self):
        return f"{self.actif.nom} | {self.date_valorisation} | {self.valeur} €"