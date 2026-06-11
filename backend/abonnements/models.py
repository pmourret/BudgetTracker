from django.db import models
from core.models import BaseModel


class Abonnement(BaseModel):
    """
    Représente un flux récurrent attendu (abonnement, salaire, loyer...).

    Règles :
    - La fréquence vient obligatoirement du référentiel (jamais codée en dur).
    - montant_attendu est le montant de référence signé (négatif = dépense).
    - seuil_divergence_pct : écart en % au-delà duquel une alerte est levée.
    - actif = False → l'abonnement ne génère plus de flux attendus.
    - date_fin null = abonnement sans fin définie.
    - Le dernier flux lié est tracé via derniere_occurrence pour détecter
      les oublis de saisie.
    """

    # Identification
    nom = models.CharField(max_length=150)

    # Compte et catégorie
    compte = models.ForeignKey(
        "comptes.Compte",
        on_delete=models.PROTECT,
        related_name="abonnements",
    )
    categorie = models.ForeignKey(
        "categories.Categorie",
        on_delete=models.PROTECT,
        related_name="abonnements",
        null=True,
        blank=True,
    )

    # Référentiels
    type_flux = models.ForeignKey(
        "referentiels.TypeFlux",
        on_delete=models.PROTECT,
        related_name="abonnements",
    )
    mode_paiement = models.ForeignKey(
        "referentiels.ModePaiement",
        on_delete=models.PROTECT,
        related_name="abonnements",
        null=True,
        blank=True,
    )
    frequence = models.ForeignKey(
        "referentiels.Frequence",
        on_delete=models.PROTECT,
        related_name="abonnements",
        help_text="Fréquence depuis le référentiel — jamais codée en dur."
    )

    # Montant de référence
    montant_attendu = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant signé de référence. Négatif = dépense, positif = recette."
    )
    seuil_divergence_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10,
        help_text="Écart en % au-delà duquel une divergence est signalée."
    )

    # Dates
    date_debut = models.DateField(
        help_text="Date du premier flux attendu."
    )
    date_fin = models.DateField(
        null=True,
        blank=True,
        help_text="Date de fin. Null = sans fin définie."
    )
    jour_echeance = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Jour du mois de l'échéance habituelle (1-31)."
    )

    # Suivi
    derniere_occurrence = models.DateField(
        null=True,
        blank=True,
        editable=False,
        help_text="Date du dernier flux rattaché à cet abonnement. Calculé."
    )
    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} | {self.montant_attendu} € | {self.frequence}"

    @property
    def est_en_retard(self):
        """
        Vrai si aucun flux n'a été saisi depuis plus d'un cycle.
        Fiabilité : estimative (dépend de la saisie manuelle des flux).
        """
        import datetime
        from referentiels.models import Frequence

        if not self.actif or not self.derniere_occurrence:
            return False

        nb_jours = self.frequence.nb_jours
        if not nb_jours:
            return False

        echeance_theorique = self.derniere_occurrence + datetime.timedelta(days=nb_jours)
        return datetime.date.today() > echeance_theorique