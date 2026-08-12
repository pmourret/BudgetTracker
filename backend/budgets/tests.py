import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase

from budgets.models import Budget, BudgetTemplate
from budgets.services.consommation import _calculer_consommation_avec_model
from budgets.services.reconduire import reconduire_vers_mois
from categories.models import Categorie
from comptes.models import Compte
from flux.models import Flux
from referentiels.models import Devise, Etablissement, StatutFlux, Titulaire, TypeCompte, TypeFlux


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
from rest_framework import status as drf_status

from core.tests_base import APIAuthTestCase


class BudgetAPITest(APIAuthTestCase):

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


class BudgetMajeurAPITest(APIAuthTestCase):
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


class BudgetTemplateAPITest(APIAuthTestCase):
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


class ReconduireAPITest(APIAuthTestCase):
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


class SoftDeleteUniciteTest(APIAuthTestCase):
    """
    Régression : la contrainte d'unicité ne doit porter que sur les lignes
    non soft-deletées. Supprimer un budget/template puis le recréer sur la
    même (catégorie, mois) doit fonctionner (avant : IntegrityError 500).
    """

    def setUp(self):
        self.categorie = Categorie.objects.create(code="UNIC_SD", nom="Loisirs SD")
        self.payload_budget = {
            "categorie": str(self.categorie.id),
            "mois": "2024-03-01",
            "montant_prevu": "120.00",
        }

    def test_recreation_budget_apres_suppression(self):
        create = self.client.post(reverse("budget-list"), self.payload_budget, format="json")
        self.assertEqual(create.status_code, drf_status.HTTP_201_CREATED)
        delete = self.client.delete(reverse("budget-detail", args=[create.data["id"]]))
        self.assertEqual(delete.status_code, drf_status.HTTP_204_NO_CONTENT)

        recreate = self.client.post(reverse("budget-list"), self.payload_budget, format="json")
        self.assertEqual(recreate.status_code, drf_status.HTTP_201_CREATED)

    def test_reconduction_apres_suppression_budget(self):
        """Supprimer le budget du mois puis reconduire doit le recréer."""
        BudgetTemplate.objects.create(
            categorie=self.categorie, montant_defaut=Decimal("120.00")
        )
        reconduire_vers_mois(datetime.date(2024, 5, 1))
        budget = Budget.objects.get(categorie=self.categorie, mois=datetime.date(2024, 5, 1))
        budget.delete()

        result = reconduire_vers_mois(datetime.date(2024, 5, 1))
        self.assertEqual(result["crees"], 1)
        self.assertTrue(
            Budget.objects.filter(
                categorie=self.categorie, mois=datetime.date(2024, 5, 1)
            ).exists()
        )

    def test_recreation_template_apres_suppression(self):
        payload = {"categorie": str(self.categorie.id), "montant_defaut": "120.00"}
        create = self.client.post(reverse("budget-template-list"), payload, format="json")
        self.assertEqual(create.status_code, drf_status.HTTP_201_CREATED)
        delete = self.client.delete(
            reverse("budget-template-detail", args=[create.data["id"]])
        )
        self.assertEqual(delete.status_code, drf_status.HTTP_204_NO_CONTENT)

        recreate = self.client.post(reverse("budget-template-list"), payload, format="json")
        self.assertEqual(recreate.status_code, drf_status.HTTP_201_CREATED)


class CategoriesInclusesValidationTest(APIAuthTestCase):
    """Les categories_incluses doivent être des sous-catégories de la majeure."""

    def setUp(self):
        self.majeure_a = Categorie.objects.create(code="MAJ_A", nom="Maison")
        self.mineure_a = Categorie.objects.create(
            code="MIN_A", nom="Entretien", parent=self.majeure_a
        )
        self.majeure_b = Categorie.objects.create(code="MAJ_B", nom="Transport B")
        self.mineure_b = Categorie.objects.create(
            code="MIN_B", nom="Carburant", parent=self.majeure_b
        )

    def test_budget_mineure_etrangere_refusee(self):
        """Inclure une mineure d'une autre majeure dans un budget → 400."""
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(self.majeure_a.id),
            "mois": "2024-03-01",
            "montant_prevu": "300.00",
            "categories_incluses": [str(self.mineure_b.id)],
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categories_incluses", response.data)

    def test_template_mineure_etrangere_refusee(self):
        """Inclure une mineure d'une autre majeure dans un template → 400."""
        response = self.client.post(reverse("budget-template-list"), {
            "categorie": str(self.majeure_a.id),
            "montant_defaut": "300.00",
            "categories_incluses": [str(self.mineure_b.id)],
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categories_incluses", response.data)

    def test_budget_non_majeur_ignore_categories_incluses(self):
        """Sur une catégorie sans mineures, categories_incluses est forcé à vide."""
        cat_simple = Categorie.objects.create(code="SIMPLE_CI", nom="Divers CI")
        response = self.client.post(reverse("budget-list"), {
            "categorie": str(cat_simple.id),
            "mois": "2024-03-01",
            "montant_prevu": "100.00",
            "categories_incluses": [str(self.mineure_b.id)],
        }, format="json")
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertEqual(response.data["categories_incluses"], [])


class AlerteBudgetMajeurTest(TestCase):
    """Un flux sur une mineure incluse doit déclencher l'alerte du budget majeur."""

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="COURANT_AM", libelle="Courant")
        titulaire = Titulaire.objects.create(code="PIERRE_AM", libelle="Pierre")
        etablissement = Etablissement.objects.create(code="BNP_AM", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR_AM", libelle="Euro", symbole="€", est_defaut=False
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT_AM", libelle="Débit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE_AM", libelle="Validé", est_definitif=True
        )
        self.compte = Compte.objects.create(
            code="CPT-AM01",
            nom="Compte alertes majeures",
            type_compte=type_compte,
            titulaire=titulaire,
            etablissement=etablissement,
            devise=self.devise,
            solde_initial=Decimal("1000.00"),
        )
        self.majeure = Categorie.objects.create(code="ALIM_AM", nom="Alimentation AM")
        self.mineure = Categorie.objects.create(
            code="COURSES_AM", nom="Courses AM", parent=self.majeure
        )
        self.budget_majeur = Budget.objects.create(
            categorie=self.majeure,
            mois=datetime.date(2024, 3, 1),
            montant_prevu=Decimal("100.00"),
            est_budget_majeur=True,
        )
        self.budget_majeur.categories_incluses.set([self.mineure])

    def test_alerte_creee_pour_budget_majeur(self):
        """Flux mineure à 90 % du budget majeur → alerte BUDGET_ALERTE créée."""
        from alertes.models import Alerte, TypeAlerte

        Flux.objects.create(
            compte=self.compte,
            categorie=self.mineure,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal("-90.00"),
            date_flux=datetime.date(2024, 3, 10),
        )
        self.budget_majeur.refresh_from_db()
        self.assertEqual(self.budget_majeur.montant_consomme, Decimal("90.00"))
        self.assertTrue(
            Alerte.objects.filter(
                type_alerte=TypeAlerte.BUDGET_ALERTE,
                budget=self.budget_majeur,
            ).exists()
        )


class BudgetThematiqueAPITest(APIAuthTestCase):
    """
    Budgets thématiques (phase 11b-3) : enveloppe regroupant des feuilles
    appartenant à des arbres différents (ex. Assurances = santé + habitation).
    """

    def setUp(self):
        # Trois arbres distincts, une feuille dans chacun.
        self.sante = Categorie.objects.create(code="SANTE_TH", nom="Santé")
        self.mnh = Categorie.objects.create(
            code="MNH_TH", nom="Mutuelle MNH", parent=self.sante
        )
        self.logement = Categorie.objects.create(code="LOG_TH", nom="Logement")
        self.assur_hab = Categorie.objects.create(
            code="AHAB_TH", nom="Assurance habitation", parent=self.logement
        )
        self.animaux = Categorie.objects.create(code="ANIM_TH", nom="Animaux")
        self.assur_anim = Categorie.objects.create(
            code="AANIM_TH", nom="Assurance animaux", parent=self.animaux
        )

    def _payload(self, **over):
        base = {
            "nom": "Assurances",
            "mois": "2026-07-01",
            "montant_prevu": "180.00",
            "categories_incluses": [
                str(self.mnh.id), str(self.assur_hab.id), str(self.assur_anim.id)
            ],
        }
        base.update(over)
        return base

    def test_creation_thematique(self):
        """Budget thématique sans catégorie ancre → 201, feuilles multi-arbres."""
        response = self.client.post(
            reverse("budget-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertIsNone(response.data["categorie"])
        self.assertEqual(response.data["libelle"], "Assurances")
        self.assertFalse(response.data["est_budget_majeur"])
        ids = {d["id"] for d in response.data["categories_incluses_detail"]}
        self.assertEqual(
            ids,
            {str(self.mnh.id), str(self.assur_hab.id), str(self.assur_anim.id)},
        )

    def test_thematique_sans_nom_refuse(self):
        response = self.client.post(
            reverse("budget-list"), self._payload(nom=""), format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("nom", response.data)

    def test_thematique_sans_categorie_refuse(self):
        response = self.client.post(
            reverse("budget-list"),
            self._payload(categories_incluses=[]),
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categories_incluses", response.data)

    def test_thematique_refuse_categorie_majeure(self):
        """Inclure une majeure (non-feuille) dans un thématique → 400."""
        response = self.client.post(
            reverse("budget-list"),
            self._payload(categories_incluses=[str(self.sante.id)]),
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("categories_incluses", response.data)

    def test_exclusivite_feuille_deja_dans_budget_simple(self):
        """Une feuille déjà couverte par un budget simple ce mois → 400."""
        Budget.objects.create(
            categorie=self.mnh,
            mois=datetime.date(2026, 7, 1),
            montant_prevu=Decimal("50.00"),
        )
        response = self.client.post(
            reverse("budget-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_exclusivite_budget_simple_apres_thematique(self):
        """Après un thématique, un budget simple sur une feuille couverte → 400."""
        self.client.post(reverse("budget-list"), self._payload(), format="json")
        response = self.client.post(
            reverse("budget-list"),
            {
                "categorie": str(self.assur_hab.id),
                "mois": "2026-07-01",
                "montant_prevu": "60.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_meme_feuilles_mois_different_ok(self):
        """Les enveloppes exclusives sont par mois : un autre mois est libre."""
        self.client.post(reverse("budget-list"), self._payload(), format="json")
        response = self.client.post(
            reverse("budget-list"),
            self._payload(mois="2026-08-01"),
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)


class BudgetThematiqueConsommationTest(TestCase):
    """La consommation d'un thématique agrège les flux de ses feuilles libres."""

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="CPT_THC", libelle="Courant")
        titulaire = Titulaire.objects.create(code="TIT_THC", libelle="Pierre")
        etablissement = Etablissement.objects.create(code="ETA_THC", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR_THC", libelle="Euro", symbole="€", est_defaut=False
        )
        self.type_flux = TypeFlux.objects.create(code="DEB_THC", libelle="Débit")
        self.statut = StatutFlux.objects.create(
            code="VAL_THC", libelle="Validé", est_definitif=True
        )
        self.compte = Compte.objects.create(
            code="CPT-THC01",
            nom="Compte thématique",
            type_compte=type_compte,
            titulaire=titulaire,
            etablissement=etablissement,
            devise=self.devise,
            solde_initial=Decimal("3000.00"),
        )
        sante = Categorie.objects.create(code="SANTE_C", nom="Santé")
        self.mnh = Categorie.objects.create(code="MNH_C", nom="MNH", parent=sante)
        log = Categorie.objects.create(code="LOG_C", nom="Logement")
        self.assur_hab = Categorie.objects.create(
            code="AHAB_C", nom="Assur habitation", parent=log
        )
        self.autre = Categorie.objects.create(code="AUTRE_C", nom="Autre", parent=log)
        self.budget = Budget.objects.create(
            nom="Assurances",
            mois=datetime.date(2026, 7, 1),
            montant_prevu=Decimal("200.00"),
        )
        self.budget.categories_incluses.set([self.mnh, self.assur_hab])

    def _flux(self, categorie, montant):
        return Flux.objects.create(
            compte=self.compte,
            categorie=categorie,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal(str(montant)),
            date_flux=datetime.date(2026, 7, 10),
        )

    def test_consommation_agrege_feuilles(self):
        self._flux(self.mnh, "-40.00")
        self._flux(self.assur_hab, "-120.00")
        self._flux(self.autre, "-500.00")  # hors enveloppe → ignoré
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.montant_consomme, Decimal("160.00"))


class BudgetTemplateThematiqueTest(APIAuthTestCase):
    """Modèle thématique + reconduction vers un mois."""

    def setUp(self):
        sante = Categorie.objects.create(code="SANTE_TT", nom="Santé")
        self.mnh = Categorie.objects.create(code="MNH_TT", nom="MNH", parent=sante)
        log = Categorie.objects.create(code="LOG_TT", nom="Logement")
        self.assur_hab = Categorie.objects.create(
            code="AHAB_TT", nom="Assur habitation", parent=log
        )

    def test_creation_et_reconduction_template_thematique(self):
        response = self.client.post(
            reverse("budget-template-list"),
            {
                "nom": "Assurances",
                "montant_defaut": "180.00",
                "categories_incluses": [str(self.mnh.id), str(self.assur_hab.id)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertIsNone(response.data["categorie"])
        self.assertEqual(response.data["libelle"], "Assurances")

        result = reconduire_vers_mois(datetime.date(2026, 7, 1))
        self.assertEqual(result["crees"], 1)
        budget = Budget.objects.get(nom="Assurances", mois=datetime.date(2026, 7, 1))
        self.assertIsNone(budget.categorie_id)
        self.assertEqual(
            {c.id for c in budget.categories_incluses.all()},
            {self.mnh.id, self.assur_hab.id},
        )
        # Idempotence : deuxième reconduction ne recrée pas.
        result2 = reconduire_vers_mois(datetime.date(2026, 7, 1))
        self.assertEqual(result2["crees"], 0)
        self.assertEqual(result2["ignores"], 1)


class PointsServiceTest(TestCase):
    """
    Mécanique B — système de points (socle 12-B-1, lecture seule).
    valeur_point = 10 € par défaut ; arrondi magnitude vers le haut.
    """

    def setUp(self):
        from referentiels.models import ParametresBudget
        self.params = ParametresBudget.get_solo()
        self.params.valeur_point = Decimal("10.00")
        self.params.save()
        self.cat = Categorie.objects.create(code="PTS_CAT", nom="Courses PTS")

    def _budget(self, mois, prevu, consomme, en_jeu=True, categorie=None):
        return Budget.objects.create(
            categorie=categorie or self.cat,
            mois=mois,
            montant_prevu=Decimal(str(prevu)),
            montant_consomme=Decimal(str(consomme)),
            en_jeu=en_jeu,
        )

    def test_points_gain_sous_consomme(self):
        from budgets.services.points import points_enveloppe
        b = self._budget(datetime.date(2026, 6, 1), 300, 270)
        self.assertEqual(points_enveloppe(b, Decimal("10")), 3)

    def test_points_perte_depassement(self):
        from budgets.services.points import points_enveloppe
        b = self._budget(datetime.date(2026, 6, 1), 300, 330)
        self.assertEqual(points_enveloppe(b, Decimal("10")), -3)

    def test_arrondi_magnitude_vers_le_haut(self):
        from budgets.services.points import points_enveloppe
        # +25 € → 2,5 pts → arrondi magnitude à 3
        b_gain = self._budget(datetime.date(2026, 6, 1), 300, 275)
        self.assertEqual(points_enveloppe(b_gain, Decimal("10")), 3)
        # −25 € → −3 (magnitude vers le haut aussi)
        b_perte = self._budget(
            datetime.date(2026, 6, 1), 300, 325,
            categorie=Categorie.objects.create(code="PTS_C2", nom="C2"),
        )
        self.assertEqual(points_enveloppe(b_perte, Decimal("10")), -3)

    def test_valeur_point_parametrable(self):
        from budgets.services.points import points_enveloppe
        b = self._budget(datetime.date(2026, 6, 1), 300, 250)  # écart +50
        self.assertEqual(points_enveloppe(b, Decimal("10")), 5)
        self.assertEqual(points_enveloppe(b, Decimal("25")), 2)  # 50/25 = 2

    def test_delta_mois_ignore_hors_jeu(self):
        from budgets.services.points import delta_mois
        self._budget(datetime.date(2026, 6, 1), 300, 270)  # +3, en jeu
        self._budget(
            datetime.date(2026, 6, 1), 100, 200, en_jeu=False,
            categorie=Categorie.objects.create(code="PTS_C3", nom="C3"),
        )  # hors jeu → ignoré
        self.assertEqual(delta_mois(datetime.date(2026, 6, 1), Decimal("10")), 3)

    def test_solde_disponible_exclut_mois_courant(self):
        from budgets.services.points import solde_disponible
        aujourd = datetime.date(2026, 7, 15)  # mois comptable courant = juillet
        self._budget(datetime.date(2026, 6, 1), 300, 270)  # clôturé → +3
        self._budget(
            datetime.date(2026, 7, 1), 300, 200,  # courant → +10 mais PROVISOIRE
            categorie=Categorie.objects.create(code="PTS_C4", nom="C4"),
        )
        # Seul juin (clôturé) compte dans la réserve disponible.
        self.assertEqual(solde_disponible(aujourd_hui=aujourd), 3)

    def test_tableau_points_historique_et_provisoire(self):
        from budgets.services.points import calculer_tableau_points
        aujourd = datetime.date(2026, 7, 15)
        self._budget(datetime.date(2026, 6, 1), 300, 270)  # +3 clôturé
        self._budget(
            datetime.date(2026, 7, 1), 300, 330,  # −3 provisoire
            categorie=Categorie.objects.create(code="PTS_C5", nom="C5"),
        )
        data = calculer_tableau_points(nb_mois=3, aujourd_hui=aujourd)
        self.assertEqual(data["solde_disponible"], 3)
        self.assertEqual(data["solde_disponible_euros"], Decimal("30.00"))
        # dernier point = mois courant, provisoire
        courant = data["historique"][-1]
        self.assertEqual(str(courant["mois"]), "2026-07-01")
        self.assertTrue(courant["provisoire"])
        self.assertEqual(courant["delta"], -3)
        # cumul de fin = 3 (juin) − 3 (juillet provisoire) = 0
        self.assertEqual(courant["cumul"], 0)
        self.assertEqual(len(data["enveloppes_courantes"]), 1)


class BudgetPrevuEffectifTest(TestCase):
    """Le taux se calcule contre le prévu effectif (base + points × valeur_point)."""

    def test_taux_contre_prevu_effectif(self):
        from budgets.services.consommation import _calculer_consommation_avec_model
        cat = Categorie.objects.create(code="EFF_CAT", nom="Eff")
        b = Budget.objects.create(
            categorie=cat, mois=datetime.date(2026, 7, 1),
            montant_prevu=Decimal("300.00"), en_jeu=True, points_alloues=5,
        )  # valeur_point défaut 10 → prévu effectif = 350
        MockFlux = MagicMock()
        MockFlux.objects.filter.return_value.aggregate.return_value = {
            "total": Decimal("-350.00")
        }
        _calculer_consommation_avec_model(b, MockFlux)
        self.assertEqual(b.montant_consomme, Decimal("350.00"))
        self.assertEqual(b.taux_consommation, Decimal("100.00"))


class PointsAllocationTest(TestCase):
    """Distribution manuelle de points (mécanique B, 12-B-2)."""

    def setUp(self):
        from referentiels.models import ParametresBudget
        p = ParametresBudget.get_solo()
        p.valeur_point = Decimal("10.00")
        p.save()
        self.aujourd = datetime.date(2026, 7, 15)  # mois comptable courant = juillet
        # Mois clôturé (juin) : +10 points → réserve disponible = 10.
        Budget.objects.create(
            categorie=Categorie.objects.create(code="AL_JUIN", nom="Juin"),
            mois=datetime.date(2026, 6, 1),
            montant_prevu=Decimal("300.00"), montant_consomme=Decimal("200.00"),
            en_jeu=True,
        )
        self.courant = Budget.objects.create(
            categorie=Categorie.objects.create(code="AL_COUR", nom="Courant"),
            mois=datetime.date(2026, 7, 1),
            montant_prevu=Decimal("200.00"), en_jeu=True,
        )

    def test_allocation_reduit_reserve(self):
        from budgets.services.points import allouer, solde_disponible
        allouer(self.courant, 5, aujourd_hui=self.aujourd)
        self.courant.refresh_from_db()
        self.assertEqual(self.courant.points_alloues, 5)
        self.assertEqual(solde_disponible(aujourd_hui=self.aujourd), 5)  # 10 − 5

    def test_allocation_plafonnee(self):
        from budgets.services.points import AllocationInvalide, allouer
        with self.assertRaises(AllocationInvalide):
            allouer(self.courant, 15, aujourd_hui=self.aujourd)  # > 10 disponibles

    def test_desallocation_rend_reserve(self):
        from budgets.services.points import allouer, solde_disponible
        allouer(self.courant, 5, aujourd_hui=self.aujourd)
        allouer(self.courant, 0, aujourd_hui=self.aujourd)
        self.courant.refresh_from_db()
        self.assertEqual(self.courant.points_alloues, 0)
        self.assertEqual(solde_disponible(aujourd_hui=self.aujourd), 10)

    def test_allocation_hors_jeu_refusee(self):
        from budgets.services.points import AllocationInvalide, allouer
        hors = Budget.objects.create(
            categorie=Categorie.objects.create(code="AL_HJ", nom="HorsJeu"),
            mois=datetime.date(2026, 7, 1),
            montant_prevu=Decimal("100.00"), en_jeu=False,
        )
        with self.assertRaises(AllocationInvalide):
            allouer(hors, 1, aujourd_hui=self.aujourd)

    def test_allocation_mois_non_courant_refusee(self):
        from budgets.services.points import AllocationInvalide, allouer
        juin = Budget.objects.get(mois=datetime.date(2026, 6, 1))
        with self.assertRaises(AllocationInvalide):
            allouer(juin, 1, aujourd_hui=self.aujourd)


class PointsAllocationAPITest(APIAuthTestCase):
    """Endpoint POST /budgets/{id}/allouer/."""

    def test_allouer_endpoint(self):
        from dateutil.relativedelta import relativedelta

        from core.services.periode import mois_comptable_courant
        from referentiels.models import ParametresBudget
        p = ParametresBudget.get_solo()
        p.valeur_point = Decimal("10.00")
        p.save()

        courant = mois_comptable_courant()
        prev = courant - relativedelta(months=1)
        # Mois clôturé → +10 de réserve.
        Budget.objects.create(
            categorie=Categorie.objects.create(code="API_PREV", nom="Prev"),
            mois=prev,
            montant_prevu=Decimal("300.00"), montant_consomme=Decimal("200.00"),
            en_jeu=True,
        )
        b = Budget.objects.create(
            categorie=Categorie.objects.create(code="API_COUR", nom="Cour"),
            mois=courant,
            montant_prevu=Decimal("200.00"), en_jeu=True,
        )
        resp = self.client.post(reverse("budget-allouer", args=[b.id]), {"points": 3}, format="json")
        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(resp.data["points_alloues"], 3)
        # 200 base + 3 × 10 = 230 effectif
        self.assertEqual(Decimal(resp.data["montant_prevu_effectif"]), Decimal("230.00"))

        # Au-delà de la réserve → 400
        resp2 = self.client.post(reverse("budget-allouer", args=[b.id]), {"points": 999}, format="json")
        self.assertEqual(resp2.status_code, drf_status.HTTP_400_BAD_REQUEST)


class PointsAPITest(APIAuthTestCase):
    """L'endpoint /analytics/points/ répond avec la structure attendue."""

    def test_endpoint_points(self):
        cat = Categorie.objects.create(code="PTS_API", nom="Courses API")
        Budget.objects.create(
            categorie=cat,
            mois=datetime.date(2026, 6, 1),
            montant_prevu=Decimal("300.00"),
            montant_consomme=Decimal("280.00"),
            en_jeu=True,
        )
        response = self.client.get(reverse("points"), {"nb_mois": 6})
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        for key in ("valeur_point", "solde_disponible", "historique", "enveloppes_courantes"):
            self.assertIn(key, response.data)
