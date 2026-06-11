import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from django.test import TestCase

from referentiels.models import (
    TypeFlux, StatutFlux, Devise, TypeCompte, Etablissement, Titulaire
)
from comptes.models import Compte
from categories.models import Categorie
from flux.models import Flux
from budgets.models import Budget
from budgets.services.consommation import (
    calculer_consommation, _calculer_consommation_avec_model
)


class CalculConsommationServiceTest(TestCase):
    """Teste la logique pure via _calculer_consommation_avec_model."""

    def setUp(self):
        self.categorie = Categorie.objects.create(
            code="ALIMENTATION", nom="Alimentation"
        )
        self.budget = Budget.objects.create(
            categorie=self.categorie,
            mois=datetime.date(2024, 3, 1),
            montant_prevu=Decimal("500.00"),
        )

    def _make_flux_model(self, total):
        MockFlux = MagicMock()
        MockFlux.objects.filter.return_value.aggregate.return_value = {
            "total": Decimal(str(total)) if total is not None else None
        }
        return MockFlux

    def test_consommation_partielle(self):
        """Taux = 60% si 300 consommés sur 500 prévus."""
        _calculer_consommation_avec_model(
            self.budget, self._make_flux_model("-300.00")
        )
        self.assertEqual(self.budget.montant_consomme, Decimal("300.00"))
        self.assertEqual(self.budget.taux_consommation, Decimal("60.00"))

    def test_consommation_depassement(self):
        """Taux > 100% si dépassement."""
        _calculer_consommation_avec_model(
            self.budget, self._make_flux_model("-600.00")
        )
        self.assertEqual(self.budget.montant_consomme, Decimal("600.00"))
        self.assertEqual(self.budget.taux_consommation, Decimal("120.00"))

    def test_aucune_depense(self):
        """Taux = 0% si aucun flux ce mois."""
        _calculer_consommation_avec_model(
            self.budget, self._make_flux_model(None)
        )
        self.assertEqual(self.budget.montant_consomme, Decimal("0.00"))
        self.assertEqual(self.budget.taux_consommation, Decimal("0.00"))

    def test_pas_division_par_zero(self):
        """Si montant_prevu = 0, taux = 0 sans exception."""
        self.budget.montant_prevu = Decimal("0.00")
        self.budget.save()
        _calculer_consommation_avec_model(
            self.budget, self._make_flux_model("-100.00")
        )
        self.assertEqual(self.budget.taux_consommation, Decimal("0.00"))

    def test_save_appele_avec_bons_champs(self):
        """save() est appelé uniquement sur les champs calculés."""
        saved_kwargs = {}
        original_save = self.budget.save

        def mock_save(**kwargs):
            saved_kwargs.update(kwargs)
            original_save(**kwargs)

        self.budget.save = mock_save
        _calculer_consommation_avec_model(
            self.budget, self._make_flux_model("-100.00")
        )
        self.assertIn("montant_consomme", saved_kwargs.get("update_fields", []))
        self.assertIn("taux_consommation", saved_kwargs.get("update_fields", []))


class SignalBudgetTest(TestCase):
    """Teste le recalcul automatique du budget via signal Flux."""

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="COURANT", libelle="Courant")
        titulaire = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        etablissement = Etablissement.objects.create(code="BNP", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True
        )
        self.compte = Compte.objects.create(
            code="CPT-B001",
            nom="Compte budget test",
            type_compte=type_compte,
            titulaire=titulaire,
            etablissement=etablissement,
            devise=self.devise,
            solde_initial=Decimal("2000.00"),
            solde_reel=Decimal("2000.00"),
        )
        self.categorie = Categorie.objects.create(
            code="COURSES", nom="Courses"
        )
        self.budget = Budget.objects.create(
            categorie=self.categorie,
            mois=datetime.date(2024, 3, 1),
            montant_prevu=Decimal("400.00"),
        )

    def _make_flux(self, montant, date_flux=None, est_transfert=False):
        return Flux.objects.create(
            compte=self.compte,
            categorie=self.categorie,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal(str(montant)),
            date_flux=date_flux or datetime.date(2024, 3, 10),
            est_transfert=est_transfert,
        )

    def test_budget_recalcule_apres_flux(self):
        """Création d'un flux → budget recalculé automatiquement."""
        self._make_flux("-200.00")
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.montant_consomme, Decimal("200.00"))
        self.assertEqual(self.budget.taux_consommation, Decimal("50.00"))

    def test_budget_recalcule_apres_soft_delete(self):
        """Soft delete d'un flux → budget recalculé."""
        flux = self._make_flux("-200.00")
        flux.delete()
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.montant_consomme, Decimal("0.00"))
        self.assertEqual(self.budget.taux_consommation, Decimal("0.00"))

    def test_transfert_exclu_du_budget(self):
        """Un flux de transfert n'impacte pas le budget."""
        self._make_flux("-300.00", est_transfert=True)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.montant_consomme, Decimal("0.00"))

    def test_flux_autre_mois_exclu(self):
        """Un flux d'un autre mois n'impacte pas le budget de mars."""
        self._make_flux("-150.00", date_flux=datetime.date(2024, 4, 5))
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.montant_consomme, Decimal("0.00"))

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status as drf_status


class BudgetAPITest(APITestCase):

    def setUp(self):
        self.categorie = Categorie.objects.create(
            code="TRANSPORT", nom="Transport"
        )
        self.payload_valide = {
            "categorie": str(self.categorie.id),
            "mois": "2024-03-15",   # sera normalisé au 1er du mois
            "montant_prevu": "300.00",
        }

    def test_creation_budget(self):
        response = self.client.post(
            reverse("budget-list"), self.payload_valide, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        # Mois normalisé au 1er
        self.assertEqual(response.data["mois"], "2024-03-01")

    def test_montant_prevu_nul_refuse(self):
        payload = {**self.payload_valide, "montant_prevu": "0.00"}
        response = self.client.post(
            reverse("budget-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_montant_prevu_negatif_refuse(self):
        payload = {**self.payload_valide, "montant_prevu": "-100.00"}
        response = self.client.post(
            reverse("budget-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_unicite_categorie_mois(self):
        """Impossible de créer deux budgets pour la même catégorie et le même mois."""
        self.client.post(reverse("budget-list"), self.payload_valide, format="json")
        response = self.client.post(
            reverse("budget-list"), self.payload_valide, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_champs_calcules_read_only(self):
        """montant_consomme et taux_consommation sont refusés en écriture."""
        payload = {
            **self.payload_valide,
            "montant_consomme": "999.00",
            "taux_consommation": "99.00",
        }
        response = self.client.post(
            reverse("budget-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("montant_consomme", response.data)

    def test_statut_consommation_ok(self):
        """Taux < 50% → statut ok."""
        response = self.client.post(
            reverse("budget-list"), self.payload_valide, format="json"
        )
        self.assertEqual(response.data["statut_consommation"], "ok")

    def test_action_recalculer(self):
        """L'action recalculer retourne le budget mis à jour."""
        create = self.client.post(
            reverse("budget-list"), self.payload_valide, format="json"
        )
        budget_id = create.data["id"]
        response = self.client.post(
            reverse("budget-recalculer", args=[budget_id])
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertIn("montant_consomme", response.data)

    def test_filtre_par_mois(self):
        self.client.post(reverse("budget-list"), self.payload_valide, format="json")
        response = self.client.get(
            reverse("budget-list"), {"mois": "2024-03-01"}
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)