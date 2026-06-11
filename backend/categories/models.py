from django.db import models
from core.models import BaseModel


def _get_flux_model():
    """
    Retourne le modèle Flux s'il existe, None sinon.
    Évite la dépendance circulaire et le crash si Flux n'est pas encore créé.
    """
    try:
        from flux.models import Flux
        return Flux
    except ImportError:
        return None


class Categorie(BaseModel):
    """
    Catégorie de flux budgétaire, organisée en hiérarchie à deux niveaux.

    Règles :
    - parent null = catégorie racine (niveau 1)
    - parent renseigné = sous-catégorie (niveau 2)
    - Une catégorie liée à des flux ne peut pas être supprimée,
      seulement désactivée.
    - Soft delete bloqué si des flux actifs sont rattachés.
    """

    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sous_categories",
        help_text="Null = catégorie racine. Renseigné = sous-catégorie."
    )
    actif = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["ordre", "nom"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.nom} › {self.nom}"
        return self.nom

    @property
    def est_racine(self):
        return self.parent_id is None

    @property
    def niveau(self):
        return 1 if self.est_racine else 2

    def _a_des_flux_actifs(self, FluxModel=None):
        """
        Vérifie si des flux actifs sont liés à cette catégorie.
        FluxModel injectable pour les tests.
        """
        if FluxModel is None:
            FluxModel = _get_flux_model()
        if FluxModel is None:
            return False
        return FluxModel.objects.filter(categorie=self).exists()

    def delete(self, using=None, keep_parents=False, FluxModel=None):
        """
        Soft delete protégé :
        - Bloqué si des flux actifs sont rattachés.
        - Soft delete en cascade sur les sous-catégories sans flux.
        """
        if self._a_des_flux_actifs(FluxModel=FluxModel):
            raise ValueError(
                f"La catégorie '{self.nom}' est liée à des flux actifs. "
                "Désactivez-la plutôt que de la supprimer."
            )

        if self.est_racine:
            for sous_cat in self.sous_categories.all():
                sous_cat.delete(FluxModel=FluxModel)

        super().delete(using=using, keep_parents=keep_parents)