from django.db import models
from core.models import BaseModel
from referentiels.models import TypeCompte, Titulaire, Etablissement, Devise


class Compte(BaseModel):
    """
    Représente un compte bancaire ou d'épargne.

    Règles critiques :
    - solde_theorique = solde_initial + Σ(flux du compte)
    - ecart_solde = solde_reel - solde_theorique
    - Ces deux champs sont calculés par le service, jamais éditables.
    """

    # Identification
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Code unique du compte (ex: CPT-0001)"
    )
    nom = models.CharField(max_length=100)

    # Relations référentiels
    type_compte = models.ForeignKey(
        TypeCompte,
        on_delete=models.PROTECT,
        related_name="comptes"
    )
    titulaire = models.ForeignKey(
        Titulaire,
        on_delete=models.PROTECT,
        related_name="comptes"
    )
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.PROTECT,
        related_name="comptes"
    )
    devise = models.ForeignKey(
        Devise,
        on_delete=models.PROTECT,
        related_name="comptes"
    )

    # Soldes
    solde_initial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Solde au moment de la création du compte dans l'application"
    )
    solde_reel = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Solde réel constaté (saisi manuellement ou via import bancaire)"
    )
    solde_theorique = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        editable=False,
        help_text="Calculé : solde_initial + Σ flux. Jamais éditable."
    )
    ecart_solde = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        editable=False,
        help_text="Calculé : solde_reel - solde_theorique. Jamais éditable."
    )

    # Metadata
    actif = models.BooleanField(default=True)
    date_ouverture = models.DateField(null=True, blank=True)
    date_fermeture = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Compte"
        verbose_name_plural = "Comptes"

    def __str__(self):
        return f"{self.code} — {self.nom} ({self.titulaire})"