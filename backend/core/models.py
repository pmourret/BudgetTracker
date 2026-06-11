import uuid
from django.db import models

# Create your models here.
class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet exclut automatiquement les enregistrements supprimés."""

    def delete(self):
        """Soft delete sur un queryset entier"""
        return self.update(is_deleted=True)

    def hard_delete(self):
        """Suppression physique - reservée aux migrations/fixtures de test"""
        return super().delete()
    
    def alive(self):
        """Filtre explicite : uniquement les enregistrements actifs"""
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

class SoftDeleteManager(models.Manager):
    """Manager par défaut : n'expose que les enregistrements non supprimés."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def alive(self):
        return self.get_queryset().alive()

    def deleted(self):
        # Bypass du filtre par défaut pour accéder aux supprimés
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=True)

    def all_with_deleted(self):
        """Accès à tout l'historique — utile pour l'audit."""
        return SoftDeleteQuerySet(self.model, using=self._db)

class BaseModel(models.Model):
    """
    Modèle abstrait dont héritent tous les modèles métier.

    Fournit :
    - id UUID (non prédictible, safe pour les URLs)
    - created_at / updated_at automatiques
    - is_deleted + soft delete via SoftDeleteManager
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = SoftDeleteManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def delete(self, using=None, keep_parents=False):
        """Soft delete unitaire — ne supprime jamais physiquement."""
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        """Suppression physique — uniquement pour les tests/fixtures."""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """Restaure un enregistrement soft-deleté."""
        self.is_deleted = False
        self.save(update_fields=["is_deleted", "updated_at"])