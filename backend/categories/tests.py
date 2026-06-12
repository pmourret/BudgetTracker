from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from unittest.mock import MagicMock, patch

from categories.models import Categorie


# ---------------------------------------------------------------------------
# Tests modèle
# ---------------------------------------------------------------------------

class CategorieModelTest(TestCase):

    def setUp(self):
        self.racine = Categorie.objects.create(
            code="ALIMENTATION",
            nom="Alimentation",
        )
        self.enfant = Categorie.objects.create(
            code="COURSES",
            nom="Courses",
            parent=self.racine,
        )

    def test_str_racine(self):
        self.assertEqual(str(self.racine), "Alimentation")

    def test_str_sous_categorie(self):
        self.assertEqual(str(self.enfant), "Alimentation › Courses")

    def test_est_racine(self):
        self.assertTrue(self.racine.est_racine)
        self.assertFalse(self.enfant.est_racine)

    def test_niveau(self):
        self.assertEqual(self.racine.niveau, 1)
        self.assertEqual(self.enfant.niveau, 2)

    def test_soft_delete_racine_sans_flux(self):
        """Soft delete d'une racine supprime aussi ses enfants."""
        self.racine.delete()
        self.assertFalse(Categorie.objects.filter(code="ALIMENTATION").exists())
        self.assertFalse(Categorie.objects.filter(code="COURSES").exists())
        # Mais les deux existent toujours en base
        self.assertTrue(
            Categorie.objects.all_with_deleted().filter(code="ALIMENTATION").exists()
        )
        self.assertTrue(
            Categorie.objects.all_with_deleted().filter(code="COURSES").exists()
        )

    def test_restore(self):
        self.racine.delete()
        self.racine.restore()
        self.assertTrue(Categorie.objects.filter(code="ALIMENTATION").exists())

    def test_code_unique(self):
        from django.db.utils import IntegrityError
        with self.assertRaises(IntegrityError):
            Categorie.objects.create(code="ALIMENTATION", nom="Doublon")

    def test_suppression_bloquee_si_flux(self):
        """Soft delete bloqué si des flux actifs sont liés."""
        MockFlux = MagicMock()
        MockFlux.objects.filter.return_value.exists.return_value = True
        with self.assertRaises(ValueError):
            self.enfant.delete(FluxModel=MockFlux)


# ---------------------------------------------------------------------------
# Tests API
# ---------------------------------------------------------------------------

class CategorieAPITest(APITestCase):

    def setUp(self):
        self.racine = Categorie.objects.create(
            code="TRANSPORT",
            nom="Transport",
        )
        self.enfant = Categorie.objects.create(
            code="CARBURANT",
            nom="Carburant",
            parent=self.racine,
        )

    def test_liste_categories(self):
        response = self.client.get(reverse("categorie-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_creation_categorie_racine(self):
        payload = {"code": "LOISIRS", "nom": "Loisirs"}
        response = self.client.post(reverse("categorie-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["parent"])
        self.assertEqual(response.data["niveau"], 1)

    def test_creation_sous_categorie(self):
        payload = {
            "code": "CINEMA",
            "nom": "Cinéma",
            "parent": str(self.racine.id),
        }
        response = self.client.post(reverse("categorie-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["niveau"], 2)

    def test_profondeur_max_2(self):
        """Une sous-catégorie ne peut pas être parente d'une autre."""
        payload = {
            "code": "TROP_PROFOND",
            "nom": "Trop profond",
            "parent": str(self.enfant.id),
        }
        response = self.client.post(reverse("categorie-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent", response.data)

    def test_categorie_ne_peut_pas_etre_sa_propre_parente(self):
        payload = {
            "code": self.racine.code,
            "nom": self.racine.nom,
            "parent": str(self.racine.id),
        }
        response = self.client.patch(
            reverse("categorie-detail", args=[self.racine.id]),
            payload,
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete_sans_flux(self):
        """Suppression autorisée si aucun flux lié."""
        response = self.client.delete(
            reverse("categorie-detail", args=[self.enfant.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        liste = self.client.get(reverse("categorie-list"))
        codes = [c["code"] for c in liste.data["results"]]
        self.assertNotIn("CARBURANT", codes)

    def test_suppression_bloquee_si_flux_api(self):
        """Suppression refusée avec 409 si des flux actifs sont liés."""
        MockFlux = MagicMock()
        MockFlux.objects.filter.return_value.exists.return_value = True

        with patch("categories.models._get_flux_model", return_value=MockFlux):
            response = self.client.delete(
                reverse("categorie-detail", args=[self.enfant.id])
            )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_action_sous_categories(self):
        response = self.client.get(
            reverse("categorie-sous-categories", args=[self.racine.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["code"], "CARBURANT")

    def test_action_desactiver(self):
        response = self.client.post(
            reverse("categorie-desactiver", args=[self.racine.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.racine.refresh_from_db()
        self.assertFalse(self.racine.actif)
        self.enfant.refresh_from_db()
        self.assertFalse(self.enfant.actif)

    def test_filtre_par_actif(self):
        self.racine.actif = False
        self.racine.save()
        response = self.client.get(reverse("categorie-list"), {"actif": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [c["code"] for c in response.data["results"]]
        self.assertNotIn("TRANSPORT", codes)

    def test_recherche_par_nom(self):
        response = self.client.get(reverse("categorie-list"), {"search": "Carbu"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["code"], "CARBURANT")

class CategorieCodeSoftDeleteTest(APITestCase):
    """
    Régression : le code auto-généré doit éviter les collisions avec les
    catégories soft-deletées (la contrainte d'unicité en base les compte aussi).
    """

    def test_auto_code_evite_collision_avec_supprimee(self):
        create = self.client.post(
            reverse("categorie-list"), {"nom": "Vacances"}, format="json"
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        code_initial = create.data["code"]

        delete = self.client.delete(
            reverse("categorie-detail", args=[create.data["id"]])
        )
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)

        recreate = self.client.post(
            reverse("categorie-list"), {"nom": "Vacances"}, format="json"
        )
        self.assertEqual(recreate.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(recreate.data["code"], code_initial)

    def test_code_manuel_en_collision_avec_supprimee_refuse(self):
        create = self.client.post(
            reverse("categorie-list"), {"nom": "Sport", "code": "SPORT"}, format="json"
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.client.delete(reverse("categorie-detail", args=[create.data["id"]]))

        recreate = self.client.post(
            reverse("categorie-list"), {"nom": "Sport", "code": "SPORT"}, format="json"
        )
        self.assertEqual(recreate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", recreate.data)
