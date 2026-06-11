import datetime
from decimal import Decimal
from django.test import TestCase

from referentiels.models import Devise, Fiscalite
from patrimoine.models import Actif, TypeActif


class ActifModelTest(TestCase):

    def setUp(self):
        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True
        )
        self.fiscalite = Fiscalite.objects.create(
            code="PEA", libelle="PEA"
        )

    def _make_actif(self, **kwargs):
        defaults = {
            "nom": "Appartement Paris",
            "type_actif": TypeActif.IMMOBILIER,
            "devise": self.devise,
            "valeur_actuelle": Decimal("250000.00"),
        }
        defaults.update(kwargs)
        return Actif.objects.create(**defaults)

    def test_str(self):
        actif = self._make_actif()
        self.assertIn("Appartement Paris", str(actif))
        self.assertIn("250000.00", str(actif))

    def test_plus_value_latente(self):
        """Plus-value = valeur_actuelle - valeur_acquisition."""
        actif = self._make_actif(
            valeur_acquisition=Decimal("200000.00"),
            valeur_actuelle=Decimal("250000.00"),
        )
        self.assertEqual(actif.plus_value_latente, Decimal("50000.00"))

    def test_plus_value_latente_negative(self):
        """Moins-value possible."""
        actif = self._make_actif(
            valeur_acquisition=Decimal("300000.00"),
            valeur_actuelle=Decimal("250000.00"),
        )
        self.assertEqual(actif.plus_value_latente, Decimal("-50000.00"))

    def test_plus_value_latente_sans_acquisition(self):
        """Sans valeur d'acquisition, plus-value = None."""
        actif = self._make_actif(valeur_acquisition=None)
        self.assertIsNone(actif.plus_value_latente)

    def test_est_valorise_recemment_vrai(self):
        actif = self._make_actif(
            date_valorisation=datetime.date.today()
        )
        self.assertTrue(actif.est_valorise_recemment)

    def test_est_valorise_recemment_faux(self):
        actif = self._make_actif(
            date_valorisation=datetime.date.today() - datetime.timedelta(days=60)
        )
        self.assertFalse(actif.est_valorise_recemment)

    def test_est_valorise_recemment_sans_date(self):
        actif = self._make_actif(date_valorisation=None)
        self.assertFalse(actif.est_valorise_recemment)

    def test_soft_delete(self):
        actif = self._make_actif()
        actif_id = actif.id
        actif.delete()
        self.assertFalse(Actif.objects.filter(id=actif_id).exists())
        self.assertTrue(
            Actif.objects.all_with_deleted().filter(id=actif_id).exists()
        )

    def test_types_disponibles(self):
        """Vérifie que tous les types sont accessibles."""
        self.assertIn("IMMOBILIER", TypeActif.values)
        self.assertIn("PEA", TypeActif.values)
        self.assertIn("ASSURANCE_VIE", TypeActif.values)
        self.assertIn("CRYPTO", TypeActif.values)

from patrimoine.services import (
    calculer_patrimoine_total,
    mettre_a_jour_valorisation,
)


class CalculPatrimoineTotalTest(TestCase):

    def setUp(self):
        self.devise = Devise.objects.create(
            code="EUR2", libelle="Euro", symbole="€", est_defaut=False
        )

    def _make_actif(self, type_actif, valeur, valeur_acq=None, actif=True):
        return Actif.objects.create(
            nom=f"Actif {type_actif}",
            type_actif=type_actif,
            devise=self.devise,
            valeur_actuelle=Decimal(str(valeur)),
            valeur_acquisition=(
                Decimal(str(valeur_acq)) if valeur_acq else None
            ),
            actif=actif,
        )

    def test_total_global(self):
        self._make_actif(TypeActif.IMMOBILIER, "250000.00")
        self._make_actif(TypeActif.PEA, "50000.00")
        result = calculer_patrimoine_total()
        self.assertEqual(result["total_estime"], Decimal("300000.00"))

    def test_total_par_type(self):
        self._make_actif(TypeActif.PEA, "50000.00")
        self._make_actif(TypeActif.PEA, "30000.00")
        result = calculer_patrimoine_total()
        self.assertEqual(
            result["par_type"]["PEA"]["total_estime"],
            Decimal("80000.00")
        )

    def test_inactifs_exclus_par_defaut(self):
        self._make_actif(TypeActif.IMMOBILIER, "250000.00")
        self._make_actif(TypeActif.EPARGNE, "10000.00", actif=False)
        result = calculer_patrimoine_total()
        self.assertEqual(result["total_estime"], Decimal("250000.00"))

    def test_inactifs_inclus_si_demande(self):
        self._make_actif(TypeActif.IMMOBILIER, "250000.00")
        self._make_actif(TypeActif.EPARGNE, "10000.00", actif=False)
        result = calculer_patrimoine_total(inclure_inactifs=True)
        self.assertEqual(result["total_estime"], Decimal("260000.00"))

    def test_plus_value_globale(self):
        self._make_actif(
            TypeActif.IMMOBILIER, "300000.00", valeur_acq="200000.00"
        )
        result = calculer_patrimoine_total()
        self.assertEqual(
            result["plus_value_latente_globale_estimee"],
            Decimal("100000.00")
        )

    def test_fiabilite_toujours_estimative(self):
        result = calculer_patrimoine_total()
        self.assertEqual(result["fiabilite"], "estimative")
        self.assertIn("avertissement", result)

    def test_aucun_actif(self):
        result = calculer_patrimoine_total()
        self.assertEqual(result["total_estime"], Decimal("0.00"))
        self.assertIsNone(result["plus_value_latente_globale_estimee"])


class MiseAJourValorisationTest(TestCase):

    def setUp(self):
        self.devise = Devise.objects.create(
            code="EUR3", libelle="Euro", symbole="€", est_defaut=False
        )
        self.actif = Actif.objects.create(
            nom="PEA Test",
            type_actif=TypeActif.PEA,
            devise=self.devise,
            valeur_actuelle=Decimal("50000.00"),
        )

    def test_mise_a_jour_valeur(self):
        mettre_a_jour_valorisation(self.actif, Decimal("55000.00"))
        self.actif.refresh_from_db()
        self.assertEqual(self.actif.valeur_actuelle, Decimal("55000.00"))

    def test_date_valorisation_mise_a_jour(self):
        mettre_a_jour_valorisation(self.actif, Decimal("55000.00"))
        self.actif.refresh_from_db()
        self.assertEqual(
            self.actif.date_valorisation, datetime.date.today()
        )

    def test_valeur_negative_refusee(self):
        with self.assertRaises(ValueError):
            mettre_a_jour_valorisation(self.actif, Decimal("-1000.00"))

    def test_valeur_zero_acceptee(self):
        """Un actif peut valoir 0 (ex: crypto dépréciée)."""
        mettre_a_jour_valorisation(self.actif, Decimal("0.00"))
        self.actif.refresh_from_db()
        self.assertEqual(self.actif.valeur_actuelle, Decimal("0.00"))

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status as drf_status


class ActifAPITest(APITestCase):

    def setUp(self):
        self.devise = Devise.objects.create(
            code="EUR4", libelle="Euro", symbole="€", est_defaut=False
        )
        self.payload_valide = {
            "nom": "Appartement Paris",
            "type_actif": TypeActif.IMMOBILIER,
            "devise": str(self.devise.id),
            "valeur_actuelle": "250000.00",
        }

    def test_creation_actif(self):
        response = self.client.post(
            reverse("actif-list"), self.payload_valide, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertEqual(response.data["nom"], "Appartement Paris")
        self.assertEqual(
            response.data["type_actif_display"], "Immobilier"
        )

    def test_valeur_negative_refusee(self):
        payload = {**self.payload_valide, "valeur_actuelle": "-1000.00"}
        response = self.client.post(
            reverse("actif-list"), payload, format="json"
        )
        self.assertEqual(
            response.status_code, drf_status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("valeur_actuelle", response.data)

    def test_action_valoriser(self):
        create = self.client.post(
            reverse("actif-list"), self.payload_valide, format="json"
        )
        actif_id = create.data["id"]
        response = self.client.post(
            reverse("actif-valoriser", args=[actif_id]),
            {"valeur": "280000.00"},
            format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(
            response.data["valeur_actuelle"], "280000.00"
        )
        self.assertIsNotNone(response.data["date_valorisation"])

    def test_action_valoriser_negative_refusee(self):
        create = self.client.post(
            reverse("actif-list"), self.payload_valide, format="json"
        )
        actif_id = create.data["id"]
        response = self.client.post(
            reverse("actif-valoriser", args=[actif_id]),
            {"valeur": "-500.00"},
            format="json"
        )
        self.assertEqual(
            response.status_code, drf_status.HTTP_400_BAD_REQUEST
        )

    def test_action_total(self):
        self.client.post(
            reverse("actif-list"), self.payload_valide, format="json"
        )
        response = self.client.get(reverse("actif-total"))
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertIn("total_estime", response.data)
        self.assertIn("fiabilite", response.data)
        self.assertIn("avertissement", response.data)
        self.assertEqual(response.data["fiabilite"], "estimative")

    def test_action_total_inclure_inactifs(self):
        self.client.post(
            reverse("actif-list"), self.payload_valide, format="json"
        )
        # Désactive l'actif
        actif_id = self.client.post(
            reverse("actif-list"), self.payload_valide, format="json"
        ).data["id"]
        self.client.patch(
            reverse("actif-detail", args=[actif_id]),
            {"actif": False},
            format="json"
        )
        response = self.client.get(
            reverse("actif-total"), {"inclure_inactifs": "true"}
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)

    def test_filtre_par_type(self):
        self.client.post(
            reverse("actif-list"), self.payload_valide, format="json"
        )
        response = self.client.get(
            reverse("actif-list"),
            {"type_actif": TypeActif.IMMOBILIER}
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_soft_delete(self):
        create = self.client.post(
            reverse("actif-list"), self.payload_valide, format="json"
        )
        actif_id = create.data["id"]
        response = self.client.delete(
            reverse("actif-detail", args=[actif_id])
        )
        self.assertEqual(
            response.status_code, drf_status.HTTP_204_NO_CONTENT
        )
        liste = self.client.get(reverse("actif-list"))
        self.assertEqual(liste.data["count"], 0)