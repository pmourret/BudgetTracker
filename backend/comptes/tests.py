from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from unittest.mock import MagicMock
from rest_framework.test import APITestCase
from rest_framework import status

from comptes.services.solde import _calculer_solde_avec_model
from referentiels.models import TypeCompte, Titulaire, Etablissement, Devise


class CalculSoldeServiceTest(TestCase):

    def _make_compte(self, solde_initial, solde_reel):
        compte = MagicMock()
        compte.solde_initial = Decimal(str(solde_initial))
        compte.solde_reel = Decimal(str(solde_reel))
        compte.solde_theorique = Decimal("0.00")
        compte.ecart_solde = Decimal("0.00")
        return compte

    def _make_flux_model(self, total_flux):
        MockFlux = MagicMock()
        MockFlux.objects.filter.return_value.aggregate.return_value = {
            "total": Decimal(str(total_flux)) if total_flux is not None else None
        }
        return MockFlux

    def test_solde_theorique_avec_flux_negatifs(self):
        compte = self._make_compte("4196.49", "3500.00")
        _calculer_solde_avec_model(compte, self._make_flux_model("-696.49"))
        self.assertEqual(compte.solde_theorique, Decimal("3500.00"))
        self.assertEqual(compte.ecart_solde, Decimal("0.00"))

    def test_solde_theorique_avec_flux_positifs(self):
        compte = self._make_compte("1000.00", "1500.00")
        _calculer_solde_avec_model(compte, self._make_flux_model("500.00"))
        self.assertEqual(compte.solde_theorique, Decimal("1500.00"))
        self.assertEqual(compte.ecart_solde, Decimal("0.00"))

    def test_ecart_solde_positif(self):
        compte = self._make_compte("1000.00", "1200.00")
        _calculer_solde_avec_model(compte, self._make_flux_model("100.00"))
        self.assertEqual(compte.solde_theorique, Decimal("1100.00"))
        self.assertEqual(compte.ecart_solde, Decimal("100.00"))

    def test_ecart_solde_negatif(self):
        compte = self._make_compte("1000.00", "900.00")
        _calculer_solde_avec_model(compte, self._make_flux_model("100.00"))
        self.assertEqual(compte.solde_theorique, Decimal("1100.00"))
        self.assertEqual(compte.ecart_solde, Decimal("-200.00"))

    def test_aucun_flux(self):
        compte = self._make_compte("4196.49", "4196.49")
        _calculer_solde_avec_model(compte, self._make_flux_model(None))
        self.assertEqual(compte.solde_theorique, Decimal("4196.49"))
        self.assertEqual(compte.ecart_solde, Decimal("0.00"))

    def test_save_appele_avec_bons_champs(self):
        compte = self._make_compte("1000.00", "1000.00")
        _calculer_solde_avec_model(compte, self._make_flux_model("0.00"))
        compte.save.assert_called_once_with(
            update_fields=["solde_theorique", "ecart_solde", "updated_at"]
        )


class CompteAPITest(APITestCase):

    def setUp(self):
        self.type_compte = TypeCompte.objects.create(
            code="COURANT", libelle="Compte courant"
        )
        self.titulaire = Titulaire.objects.create(
            code="PIERRE", libelle="Pierre"
        )
        self.etablissement = Etablissement.objects.create(
            code="BOURSOBANK", libelle="BoursoBank"
        )
        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True
        )
        self.payload_valide = {
            "code": "CPT-0001",
            "nom": "Compte principal",
            "type_compte": str(self.type_compte.id),
            "titulaire": str(self.titulaire.id),
            "etablissement": str(self.etablissement.id),
            "devise": str(self.devise.id),
            "solde_initial": "4196.49",
            "solde_reel": "4196.49",
        }

    def test_creation_compte(self):
        url = reverse("compte-list")
        response = self.client.post(url, self.payload_valide, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["code"], "CPT-0001")

    def test_solde_theorique_read_only_a_la_creation(self):
        url = reverse("compte-list")
        payload = {**self.payload_valide, "solde_theorique": "9999.99"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("solde_theorique", response.data)

    def test_ecart_solde_read_only_a_la_creation(self):
        url = reverse("compte-list")
        payload = {**self.payload_valide, "ecart_solde": "100.00"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ecart_solde", response.data)

    def test_liste_comptes(self):
        self.client.post(reverse("compte-list"), self.payload_valide, format="json")
        response = self.client.get(reverse("compte-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_detail_compte(self):
        create = self.client.post(
            reverse("compte-list"), self.payload_valide, format="json"
        )
        compte_id = create.data["id"]
        response = self.client.get(reverse("compte-detail", args=[compte_id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "CPT-0001")

    def test_code_unique(self):
        url = reverse("compte-list")
        self.client.post(url, self.payload_valide, format="json")
        response = self.client.post(url, self.payload_valide, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete(self):
        create = self.client.post(
            reverse("compte-list"), self.payload_valide, format="json"
        )
        compte_id = create.data["id"]
        response = self.client.delete(
            reverse("compte-detail", args=[compte_id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        liste = self.client.get(reverse("compte-list"))
        self.assertEqual(liste.data["count"], 0)