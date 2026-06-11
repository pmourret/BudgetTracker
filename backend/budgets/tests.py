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
from budgets.models import Budget, BudgetTemplate
from budgets.services.consommation import (
    calculer_consommation, _calculer_consommation_avec_model
)
from budgets.services.reconduire import reconduire_vers_mois


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


class BudgetMajeurAPITest(APITestCase):
    """Tests pour la logique des budgets de catégorie majeure (phase 11b-2)."""

    def setUp(self):
        self.majeure = Categorie.objects.create(code="ALIM", nom="Alimentation")
        self.mineure1 = Categorie.objects.create(
            code="COURSES", nom="Courses", parent=self.majeure
        )
        self.mineure2 = Categorie.objects.create(
            code="RESTO", nom="Restaurant", parent=self.majeure
        )
        self.mineure_inactive = Categorie.objects.create(
            code="TRAITEUR", nom="Traiteur", parent=self.majeure, actif=False
        )

    def test_budget_mineure_est_budget_majeur_false(self):
        """Budget sur catégorie mineure → est_budget_majeur=False."""
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(self.mineure1.id),
            "mois": "2024-03-01",
            "montant_prevu": "200.00",
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertFalse(response.data["est_budget_majeur"])
        self.assertEqual(response.data["categories_incluses"], [])

    def test_budget_majeure_auto_detecte(self):
        """Budget sur catégorie majeure → est_budget_majeur=True auto-détecté."""
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(self.majeure.id),
            "mois": "2024-03-01",
            "montant_prevu": "500.00",
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertTrue(response.data["est_budget_majeur"])

    def test_budget_majeure_mineures_actives_auto_remplies(self):
        """À la création d'un budget majeur, les mineures actives sont auto-incluses."""
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(self.majeure.id),
            "mois": "2024-03-01",
            "montant_prevu": "500.00",
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        ids_inclus = [str(d["id"]) for d in response.data["categories_incluses_detail"]]
        self.assertIn(str(self.mineure1.id), ids_inclus)
        self.assertIn(str(self.mineure2.id), ids_inclus)
        # La mineure inactive ne doit PAS être incluse
        self.assertNotIn(str(self.mineure_inactive.id), ids_inclus)

    def test_budget_majeure_sans_mineure_refuse(self):
        """Budget majeur avec categories_incluses vide → 400."""
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(self.majeure.id),
            "mois": "2024-03-01",
            "montant_prevu": "500.00",
            "categories_incluses": [],
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categories_incluses", response.data)

    def test_conflit_mineure_dans_budget_majeur_puis_budget_propre(self):
        """Si une mineure est déjà incluse dans un budget majeur, créer un budget propre → 400."""
        # Créer le budget majeur (inclut mineure1 et mineure2)
        self.client.post(reverse("budget-list"), {
            "categorie": str(self.majeure.id),
            "mois": "2024-03-01",
            "montant_prevu": "500.00",
        }, format="json")
        # Tenter de créer un budget propre pour mineure1 le même mois
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(self.mineure1.id),
            "mois": "2024-03-01",
            "montant_prevu": "100.00",
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categorie", response.data)

    def test_conflit_budget_propre_mineure_puis_budget_majeur_incluant(self):
        """Si une mineure a un budget propre, créer un budget majeur qui l'inclut → 400."""
        # Créer d'abord le budget mineure
        self.client.post(reverse("budget-list"), {
            "categorie": str(self.mineure1.id),
            "mois": "2024-03-01",
            "montant_prevu": "100.00",
        }, format="json")
        # Créer le budget majeur qui inclut mineure1 → conflit
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(self.majeure.id),
            "mois": "2024-03-01",
            "montant_prevu": "500.00",
            "categories_incluses": [str(self.mineure1.id)],
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categories_incluses", response.data)

    def test_budget_majeur_sans_conflit_mois_different(self):
        """Budget mineure sur mois M et budget majeur sur mois M+1 → OK."""
        self.client.post(reverse("budget-list"), {
            "categorie": str(self.mineure1.id),
            "mois": "2024-03-01",
            "montant_prevu": "100.00",
        }, format="json")
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(self.majeure.id),
            "mois": "2024-04-01",
            "montant_prevu": "500.00",
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)


class BudgetMajeurConsommationTest(TestCase):
    """Teste le calcul de consommation pour les budgets majeures."""

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="COURANT2", libelle="Courant")
        titulaire = Titulaire.objects.create(code="PIERRE2", libelle="Pierre")
        etablissement = Etablissement.objects.create(code="BNP2", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR2", libelle="Euro", symbole="€", est_defaut=False
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT2", libelle="Débit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE2", libelle="Validé", est_definitif=True
        )
        self.compte = Compte.objects.create(
            code="CPT-B002",
            nom="Compte budget majeur test",
            type_compte=type_compte,
            titulaire=titulaire,
            etablissement=etablissement,
            devise=self.devise,
            solde_initial=Decimal("3000.00"),
            solde_reel=Decimal("3000.00"),
        )
        self.majeure = Categorie.objects.create(code="ALIM2", nom="Alimentation")
        self.mineure1 = Categorie.objects.create(
            code="COURSES2", nom="Courses", parent=self.majeure
        )
        self.mineure2 = Categorie.objects.create(
            code="RESTO2", nom="Restaurant", parent=self.majeure
        )
        self.budget_majeur = Budget.objects.create(
            categorie=self.majeure,
            mois=datetime.date(2024, 3, 1),
            montant_prevu=Decimal("600.00"),
            est_budget_majeur=True,
        )
        self.budget_majeur.categories_incluses.set([self.mineure1, self.mineure2])

    def _flux(self, categorie, montant, date_flux=None, est_transfert=False):
        return Flux.objects.create(
            compte=self.compte,
            categorie=categorie,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal(str(montant)),
            date_flux=date_flux or datetime.date(2024, 3, 10),
            est_transfert=est_transfert,
        )

    def test_consommation_majeure_agrege_mineures(self):
        """Budget majeur : consommation = somme des flux des mineures incluses."""
        self._flux(self.mineure1, "-150.00")
        self._flux(self.mineure2, "-100.00")
        self.budget_majeur.refresh_from_db()
        self.assertEqual(self.budget_majeur.montant_consomme, Decimal("250.00"))

    def test_flux_mineure_non_incluse_exclu(self):
        """Un flux d'une mineure non incluse n'impacte pas le budget majeur."""
        mineure_hors = Categorie.objects.create(
            code="AUTRE2", nom="Autre", parent=self.majeure
        )
        self._flux(mineure_hors, "-200.00")
        self.budget_majeur.refresh_from_db()
        self.assertEqual(self.budget_majeur.montant_consomme, Decimal("0.00"))

    def test_transfert_exclu_budget_majeur(self):
        """Transfert non compté dans un budget majeur."""
        self._flux(self.mineure1, "-300.00", est_transfert=True)
        self.budget_majeur.refresh_from_db()
        self.assertEqual(self.budget_majeur.montant_consomme, Decimal("0.00"))

    def test_budget_mineure_independant(self):
        """Un budget mineure calcule uniquement sa propre catégorie."""
        budget_min = Budget.objects.create(
            categorie=self.mineure1,
            mois=datetime.date(2024, 4, 1),
            montant_prevu=Decimal("200.00"),
        )
        self._flux(self.mineure1, "-80.00", date_flux=datetime.date(2024, 4, 5))
        self._flux(self.mineure2, "-120.00", date_flux=datetime.date(2024, 4, 5))
        budget_min.refresh_from_db()
        self.assertEqual(budget_min.montant_consomme, Decimal("80.00"))


class BudgetTemplateAPITest(APITestCase):
    """Tests CRUD pour les modèles de budget récurrents."""

    def setUp(self):
        self.cat_simple = Categorie.objects.create(code="TRANSPORT3", nom="Transport")
        self.majeure = Categorie.objects.create(code="ALIM3", nom="Alimentation")
        self.mineure1 = Categorie.objects.create(
            code="COURSES3", nom="Courses", parent=self.majeure
        )
        self.mineure2 = Categorie.objects.create(
            code="RESTO3", nom="Restaurant", parent=self.majeure
        )

    def test_creation_template_simple(self):
        """Créer un template pour une catégorie sans enfants."""
        response = self.client.post(
            reverse("budget-template-list"),
            {"categorie": str(self.cat_simple.id), "montant_defaut": "150.00"},
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertFalse(response.data["est_budget_majeur"])

    def test_creation_template_majeure_auto_detecte(self):
        """Template sur majeure → est_budget_majeur=True et mineures auto-incluses."""
        response = self.client.post(
            reverse("budget-template-list"),
            {"categorie": str(self.majeure.id), "montant_defaut": "500.00"},
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertTrue(response.data["est_budget_majeur"])
        ids = [d["id"] for d in response.data["categories_incluses_detail"]]
        self.assertIn(str(self.mineure1.id), ids)
        self.assertIn(str(self.mineure2.id), ids)

    def test_unicite_categorie_template(self):
        """Impossible de créer deux templates pour la même catégorie."""
        self.client.post(
            reverse("budget-template-list"),
            {"categorie": str(self.cat_simple.id), "montant_defaut": "150.00"},
            format="json",
        )
        response = self.client.post(
            reverse("budget-template-list"),
            {"categorie": str(self.cat_simple.id), "montant_defaut": "200.00"},
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categorie", response.data)

    def test_montant_defaut_nul_refuse(self):
        response = self.client.post(
            reverse("budget-template-list"),
            {"categorie": str(self.cat_simple.id), "montant_defaut": "0.00"},
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_template_majeure_sans_mineure_refuse(self):
        response = self.client.post(
            reverse("budget-template-list"),
            {
                "categorie": str(self.majeure.id),
                "montant_defaut": "500.00",
                "categories_incluses": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categories_incluses", response.data)


class ReconduireServiceTest(TestCase):
    """Tests du service de reconduction de templates vers un mois cible."""

    def setUp(self):
        self.cat1 = Categorie.objects.create(code="CAT_T1", nom="Loyer")
        self.cat2 = Categorie.objects.create(code="CAT_T2", nom="Épargne")
        self.majeure = Categorie.objects.create(code="CAT_T3", nom="Courses maj")
        self.mineure = Categorie.objects.create(
            code="CAT_T4", nom="Super", parent=self.majeure
        )
        self.t1 = BudgetTemplate.objects.create(
            categorie=self.cat1, montant_defaut=Decimal("800.00")
        )
        self.t2 = BudgetTemplate.objects.create(
            categorie=self.cat2, montant_defaut=Decimal("200.00")
        )
        self.t_maj = BudgetTemplate.objects.create(
            categorie=self.majeure,
            montant_defaut=Decimal("400.00"),
            est_budget_majeur=True,
        )
        self.t_maj.categories_incluses.set([self.mineure])

    def test_reconduction_cree_budgets(self):
        """Les budgets sont créés pour chaque template actif."""
        result = reconduire_vers_mois(datetime.date(2024, 5, 1))
        self.assertEqual(result["crees"], 3)
        self.assertEqual(result["ignores"], 0)
        self.assertEqual(Budget.objects.filter(mois=datetime.date(2024, 5, 1)).count(), 3)

    def test_reconduction_idempotente(self):
        """Relancer la reconduction sur le même mois ne crée pas de doublons."""
        reconduire_vers_mois(datetime.date(2024, 5, 1))
        result = reconduire_vers_mois(datetime.date(2024, 5, 1))
        self.assertEqual(result["crees"], 0)
        self.assertEqual(result["ignores"], 3)
        self.assertEqual(Budget.objects.filter(mois=datetime.date(2024, 5, 1)).count(), 3)

    def test_reconduction_preserve_budget_existant(self):
        """Un budget créé manuellement avant la reconduction n'est pas écrasé."""
        Budget.objects.create(
            categorie=self.cat1,
            mois=datetime.date(2024, 5, 1),
            montant_prevu=Decimal("999.00"),
        )
        result = reconduire_vers_mois(datetime.date(2024, 5, 1))
        self.assertEqual(result["ignores"], 1)
        # Le montant manuel est conservé
        b = Budget.objects.get(categorie=self.cat1, mois=datetime.date(2024, 5, 1))
        self.assertEqual(b.montant_prevu, Decimal("999.00"))

    def test_template_inactif_ignore(self):
        """Un template inactif n'est pas reconduit."""
        self.t2.actif = False
        self.t2.save()
        result = reconduire_vers_mois(datetime.date(2024, 5, 1))
        self.assertEqual(result["crees"], 2)
        self.assertFalse(
            Budget.objects.filter(categorie=self.cat2, mois=datetime.date(2024, 5, 1)).exists()
        )

    def test_budget_cree_lie_au_template(self):
        """Le budget créé référence le template source."""
        reconduire_vers_mois(datetime.date(2024, 5, 1))
        b = Budget.objects.get(categorie=self.cat1, mois=datetime.date(2024, 5, 1))
        self.assertEqual(b.template, self.t1)

    def test_budget_majeur_reconduit_avec_mineures(self):
        """Le budget majeur reconduit hérite des categories_incluses du template."""
        reconduire_vers_mois(datetime.date(2024, 5, 1))
        b = Budget.objects.get(categorie=self.majeure, mois=datetime.date(2024, 5, 1))
        self.assertTrue(b.est_budget_majeur)
        self.assertIn(self.mineure, b.categories_incluses.all())

    def test_montant_normalise_au_1er_du_mois(self):
        """Le mois est normalisé au 1er du mois même si un autre jour est passé."""
        reconduire_vers_mois(datetime.date(2024, 5, 15))
        self.assertTrue(
            Budget.objects.filter(mois=datetime.date(2024, 5, 1)).exists()
        )


class ReconduireAPITest(APITestCase):
    """Tests de l'endpoint POST /budget-templates/reconduire/."""

    def setUp(self):
        self.cat = Categorie.objects.create(code="CAT_API_T", nom="Internet")
        BudgetTemplate.objects.create(
            categorie=self.cat, montant_defaut=Decimal("40.00")
        )

    def test_action_reconduire(self):
        response = self.client.post(
            reverse("budget-template-reconduire"),
            {"mois": "2024-06-01"},
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(response.data["crees"], 1)
        self.assertTrue(
            Budget.objects.filter(categorie=self.cat, mois=datetime.date(2024, 6, 1)).exists()
        )

    def test_action_reconduire_mois_manquant(self):
        response = self.client.post(
            reverse("budget-template-reconduire"), {}, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_action_reconduire_mois_invalide(self):
        response = self.client.post(
            reverse("budget-template-reconduire"),
            {"mois": "pas-une-date"},
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
