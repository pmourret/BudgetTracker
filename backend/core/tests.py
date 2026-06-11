from django.test import TestCase
from core.models import BaseModel, SoftDeleteManager, SoftDeleteQuerySet


class BaseModelMetaTest(TestCase):
    """Vérifie que BaseModel est bien abstrait et correctement configuré."""

    def test_est_abstrait(self):
        self.assertTrue(BaseModel._meta.abstract)

    def test_champs_presents(self):
        champs = [f.name for f in BaseModel._meta.fields]
        self.assertIn("id", champs)
        self.assertIn("created_at", champs)
        self.assertIn("updated_at", champs)
        self.assertIn("is_deleted", champs)

    def test_manager_par_defaut(self):
        # Sur un modèle abstrait, on vérifie la déclaration du manager
        # via _meta.managers rather than l'accès direct à .objects
        manager_classes = [
            type(m) for m in BaseModel._meta.managers
        ]
        self.assertIn(SoftDeleteManager, manager_classes)