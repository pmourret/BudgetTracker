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

    # Identification — sert de NUMÉRO DE COMPTE bancaire : il permet le
    # rapprochement automatique d'un relevé (accountNum du CSV = ce code).
    # Longueur large pour accepter un IBAN. Reste unique.
    code = models.CharField(
        max_length=34,
        unique=True,
        help_text="Numéro de compte (ex: 00040553758 ou IBAN). "
                  "Sert au rapprochement automatique des relevés bancaires."
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
        editable=False,
        help_text="Calculé : solde_initial + Σ(flux dont statut.est_definitif=True). Jamais éditable."
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
    est_commun = models.BooleanField(
        default=False,
        help_text="Compte partagé du foyer (joint) — affiché avec un indicateur dédié."
    )
    est_epargne = models.BooleanField(
        default=False,
        help_text="Compte d'épargne (livret, PEL, PEA…) — alimenté par transferts, "
                  "suivi dans l'analyse de l'épargne. Purement informatif pour les soldes."
    )
    taux_annuel = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Taux d'intérêt annuel en % (ex. 3.00 pour un Livret A). "
                  "Informatif au MVP ; destiné à la projection des intérêts (prévisionnel, à venir)."
    )
    date_ouverture = models.DateField(null=True, blank=True)
    date_fermeture = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Compte"
        verbose_name_plural = "Comptes"

    def __str__(self):
        return f"{self.code} — {self.nom} ({self.titulaire})"