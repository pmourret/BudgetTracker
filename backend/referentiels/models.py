from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from core.models import BaseModel


class ParametresBudget(BaseModel):
    """
    Paramètres globaux du foyer (singleton). Référentiel administrable :
    aucune valeur codée en dur (règle métier 1).

    `jour_debut_mois_comptable` définit le découpage en mois comptables
    (voir core/services/periode.py) — 1 = mois calendaire.
    """

    jour_debut_mois_comptable = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text=(
            "Jour du mois où débute le mois comptable (1 = mois calendaire). "
            "Borné à 28 pour rester valide tous les mois. Ex. 25 : la période "
            "du 25 au 24 du mois suivant est le mois comptable du suivant."
        ),
    )

    class Meta:
        verbose_name = "Paramètres budget"
        verbose_name_plural = "Paramètres budget"

    def __str__(self):
        return f"Paramètres (mois comptable au {self.jour_debut_mois_comptable})"

    @classmethod
    def get_solo(cls):
        """Renvoie l'unique instance, la crée avec les défauts si absente."""
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj


class ReferentielBase(BaseModel):
    """
    Socle commun à tous les référentiels :
    code unique + libellé + ordre d'affichage + actif.
    """
    code = models.CharField(max_length=50, unique=True)
    libelle = models.CharField(max_length=100)
    ordre = models.PositiveSmallIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        abstract = True
        ordering = ["ordre", "libelle"]

    def __str__(self):
        return f"{self.code} — {self.libelle}"


class TypeCompte(ReferentielBase):
    class Meta(ReferentielBase.Meta):
        verbose_name = "Type de compte"
        verbose_name_plural = "Types de compte"


class TypeFlux(ReferentielBase):
    class Meta(ReferentielBase.Meta):
        verbose_name = "Type de flux"
        verbose_name_plural = "Types de flux"


class Titulaire(ReferentielBase):
    class Meta(ReferentielBase.Meta):
        verbose_name = "Titulaire"
        verbose_name_plural = "Titulaires"


class ModePaiement(ReferentielBase):
    class Meta(ReferentielBase.Meta):
        verbose_name = "Mode de paiement"
        verbose_name_plural = "Modes de paiement"


class Frequence(ReferentielBase):
    # Nombre de jours entre deux occurrences — utile pour les abonnements
    nb_jours = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Nombre de jours entre deux occurrences (null = ponctuel)"
    )

    class Meta(ReferentielBase.Meta):
        verbose_name = "Fréquence"
        verbose_name_plural = "Fréquences"


class Etablissement(ReferentielBase):
    class Meta(ReferentielBase.Meta):
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"


class Devise(ReferentielBase):
    symbole = models.CharField(max_length=5)
    est_defaut = models.BooleanField(
        default=False,
        help_text="Une seule devise par défaut autorisée"
    )

    class Meta(ReferentielBase.Meta):
        verbose_name = "Devise"
        verbose_name_plural = "Devises"


class Fiscalite(ReferentielBase):
    class Meta(ReferentielBase.Meta):
        verbose_name = "Fiscalité"
        verbose_name_plural = "Fiscalités"


class StatutFlux(ReferentielBase):
    est_definitif = models.BooleanField(
        default=False,
        help_text="Un statut définitif ne peut plus être modifié"
    )

    class Meta(ReferentielBase.Meta):
        verbose_name = "Statut de flux"
        verbose_name_plural = "Statuts de flux"