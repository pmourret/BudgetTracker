import datetime
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from alertes.models import Alerte, TypeAlerte, NiveauAlerte
from referentiels.models import (
    TypeCompte, Etablissement, Titulaire, Devise
)
from comptes.models import Compte


class AlerteModelTest(TestCase):

    def setUp(self):
        self.compte = Compte.objects.create(
            code="CPT-0001",
            nom="Compte test",
            type_compte=TypeCompte.objects.create(
                code="COURANT", libelle="Courant"
            ),
            titulaire=Titulaire.objects.create(
                code="PIERRE", libelle="Pierre"
            ),
            etablissement=Etablissement.objects.create(
                code="BNP", libelle="BNP"
            ),
            devise=Devise.objects.create(
                code="EUR", libelle="Euro", symbole="€", est_defaut=True
            ),
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("1000.00"),
        )

    def _make_alerte(self, **kwargs):
        defaults = {
            "type_alerte": TypeAlerte.SOLDE_BAS,
            "niveau": NiveauAlerte.AVERTISSEMENT,
            "explication": "Le solde du compte est inférieur au seuil configuré.",
            "compte": self.compte,
            "valeur_constatee": Decimal("50.00"),
            "valeur_seuil": Decimal("100.00"),
        }
        defaults.update(kwargs)
        return Alerte.objects.create(**defaults)

    def test_str(self):
        alerte = self._make_alerte()
        self.assertIn("Solde bas", str(alerte))
        self.assertIn("AVERTISSEMENT", str(alerte))

    def test_acquitter(self):
        """Acquitter une alerte met à jour acquittee et acquittee_le."""
        alerte = self._make_alerte()
        self.assertFalse(alerte.acquittee)
        self.assertIsNone(alerte.acquittee_le)

        alerte.acquitter()
        alerte.refresh_from_db()

        self.assertTrue(alerte.acquittee)
        self.assertIsNotNone(alerte.acquittee_le)

    def test_soft_delete(self):
        """Une alerte acquittée reste en base après soft delete."""
        alerte = self._make_alerte()
        alerte_id = alerte.id
        alerte.delete()
        self.assertFalse(Alerte.objects.filter(id=alerte_id).exists())
        self.assertTrue(
            Alerte.objects.all_with_deleted().filter(id=alerte_id).exists()
        )

    def test_niveaux_disponibles(self):
        """Vérifie que les trois niveaux sont accessibles."""
        self.assertIn("INFO", NiveauAlerte.values)
        self.assertIn("AVERTISSEMENT", NiveauAlerte.values)
        self.assertIn("CRITIQUE", NiveauAlerte.values)

    def test_types_disponibles(self):
        """Vérifie que tous les types sont accessibles."""
        self.assertIn("BUDGET_DEPASSE", TypeAlerte.values)
        self.assertIn("SOLDE_BAS", TypeAlerte.values)
        self.assertIn("ABONNEMENT_EN_RETARD", TypeAlerte.values)
        self.assertIn("ABONNEMENT_DIVERGENCE", TypeAlerte.values)
        self.assertIn("ECART_SOLDE", TypeAlerte.values)

import datetime
from decimal import Decimal
from django.test import TestCase

from alertes.models import Alerte, TypeAlerte, NiveauAlerte
from alertes.services import (
    detecter_alertes_budget,
    detecter_alerte_solde_bas,
    detecter_alerte_abonnement_en_retard,
    detecter_alerte_divergence_abonnement,
    detecter_alerte_ecart_solde,
)
from referentiels.models import (
    TypeCompte, Etablissement, Titulaire, Devise,
    TypeFlux, Frequence
)
from comptes.models import Compte
from categories.models import Categorie
from budgets.models import Budget
from abonnements.models import Abonnement


class DetectionAlerteBudgetTest(TestCase):

    def setUp(self):
        self.categorie = Categorie.objects.create(
            code="COURSES", nom="Courses"
        )
        self.budget = Budget.objects.create(
            categorie=self.categorie,
            mois=datetime.date(2024, 3, 1),
            montant_prevu=Decimal("400.00"),
        )

    def _set_taux(self, taux):
        self.budget.taux_consommation = Decimal(str(taux))
        self.budget.montant_consomme = (
            self.budget.montant_prevu * Decimal(str(taux)) / 100
        )
        self.budget.save(update_fields=[
            "taux_consommation", "montant_consomme"
        ])

    def test_pas_alerte_sous_80(self):
        self._set_taux("50.00")
        alertes = detecter_alertes_budget(self.budget)
        self.assertEqual(len(alertes), 0)

    def test_alerte_avertissement_entre_80_et_100(self):
        self._set_taux("85.00")
        alertes = detecter_alertes_budget(self.budget)
        self.assertEqual(len(alertes), 1)
        self.assertEqual(alertes[0].type_alerte, TypeAlerte.BUDGET_ALERTE)
        self.assertEqual(alertes[0].niveau, NiveauAlerte.AVERTISSEMENT)

    def test_alerte_critique_a_100(self):
        self._set_taux("110.00")
        alertes = detecter_alertes_budget(self.budget)
        self.assertEqual(len(alertes), 1)
        self.assertEqual(alertes[0].type_alerte, TypeAlerte.BUDGET_DEPASSE)
        self.assertEqual(alertes[0].niveau, NiveauAlerte.CRITIQUE)

    def test_pas_doublon_si_alerte_non_acquittee(self):
        self._set_taux("110.00")
        detecter_alertes_budget(self.budget)
        alertes = detecter_alertes_budget(self.budget)
        self.assertEqual(len(alertes), 0)
        self.assertEqual(
            Alerte.objects.filter(budget=self.budget).count(), 1
        )

    def test_nouvelle_alerte_si_acquittee(self):
        self._set_taux("110.00")
        detecter_alertes_budget(self.budget)
        Alerte.objects.filter(budget=self.budget).update(acquittee=True)
        alertes = detecter_alertes_budget(self.budget)
        self.assertEqual(len(alertes), 1)


class DetectionAlerteSoldeBasTest(TestCase):

    def setUp(self):
        self.compte = Compte.objects.create(
            code="CPT-0001",
            nom="Compte test",
            type_compte=TypeCompte.objects.create(
                code="COURANT", libelle="Courant"
            ),
            titulaire=Titulaire.objects.create(
                code="PIERRE", libelle="Pierre"
            ),
            etablissement=Etablissement.objects.create(
                code="BNP", libelle="BNP"
            ),
            devise=Devise.objects.create(
                code="EUR", libelle="Euro", symbole="€", est_defaut=True
            ),
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("50.00"),
            solde_theorique=Decimal("50.00"),
        )

    def test_alerte_si_solde_sous_seuil(self):
        alerte = detecter_alerte_solde_bas(self.compte, Decimal("100.00"))
        self.assertIsNotNone(alerte)
        self.assertEqual(alerte.type_alerte, TypeAlerte.SOLDE_BAS)
        self.assertEqual(alerte.valeur_constatee, Decimal("50.00"))
        self.assertEqual(alerte.valeur_seuil, Decimal("100.00"))

    def test_pas_alerte_si_solde_ok(self):
        alerte = detecter_alerte_solde_bas(self.compte, Decimal("30.00"))
        self.assertIsNone(alerte)

    def test_pas_doublon(self):
        detecter_alerte_solde_bas(self.compte, Decimal("100.00"))
        alerte = detecter_alerte_solde_bas(self.compte, Decimal("100.00"))
        self.assertIsNone(alerte)
        self.assertEqual(
            Alerte.objects.filter(compte=self.compte).count(), 1
        )


class DetectionAlerteEcartSoldeTest(TestCase):

    def setUp(self):
        self.compte = Compte.objects.create(
            code="CPT-0002",
            nom="Compte écart",
            type_compte=TypeCompte.objects.create(
                code="COURANT2", libelle="Courant"
            ),
            titulaire=Titulaire.objects.create(
                code="PIERRE2", libelle="Pierre"
            ),
            etablissement=Etablissement.objects.create(
                code="BNP2", libelle="BNP"
            ),
            devise=Devise.objects.create(
                code="EUR2", libelle="Euro", symbole="€", est_defaut=False
            ),
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("1200.00"),
            solde_theorique=Decimal("1000.00"),
            ecart_solde=Decimal("200.00"),
        )

    def test_alerte_si_ecart_depasse_seuil(self):
        alerte = detecter_alerte_ecart_solde(self.compte, Decimal("100.00"))
        self.assertIsNotNone(alerte)
        self.assertEqual(alerte.type_alerte, TypeAlerte.ECART_SOLDE)

    def test_pas_alerte_si_ecart_ok(self):
        alerte = detecter_alerte_ecart_solde(self.compte, Decimal("500.00"))
        self.assertIsNone(alerte)


class DetectionAlerteAbonnementTest(TestCase):

    def setUp(self):
        type_compte = TypeCompte.objects.create(
            code="COURANT3", libelle="Courant"
        )
        titulaire = Titulaire.objects.create(code="PIERRE3", libelle="Pierre")
        etablissement = Etablissement.objects.create(
            code="BNP3", libelle="BNP"
        )
        devise = Devise.objects.create(
            code="EUR3", libelle="Euro", symbole="€", est_defaut=False
        )
        type_flux = TypeFlux.objects.create(code="DEBIT3", libelle="Débit")
        self.frequence = Frequence.objects.create(
            code="MENSUEL3", libelle="Mensuel", nb_jours=30
        )
        categorie = Categorie.objects.create(
            code="STREAMING3", nom="Streaming"
        )
        compte = Compte.objects.create(
            code="CPT-0003",
            nom="Compte test",
            type_compte=type_compte,
            titulaire=titulaire,
            etablissement=etablissement,
            devise=devise,
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("1000.00"),
        )
        self.abonnement = Abonnement.objects.create(
            nom="Netflix",
            compte=compte,
            categorie=categorie,
            type_flux=type_flux,
            frequence=self.frequence,
            montant_attendu=Decimal("-15.99"),
            seuil_divergence_pct=Decimal("10.00"),
            date_debut=datetime.date(2024, 1, 1),
        )

    def test_alerte_abonnement_en_retard(self):
        self.abonnement.derniere_occurrence = (
            datetime.date.today() - datetime.timedelta(days=45)
        )
        self.abonnement.save(update_fields=["derniere_occurrence"])
        alerte = detecter_alerte_abonnement_en_retard(self.abonnement)
        self.assertIsNotNone(alerte)
        self.assertEqual(alerte.type_alerte, TypeAlerte.ABONNEMENT_EN_RETARD)

    def test_pas_alerte_abonnement_a_jour(self):
        self.abonnement.derniere_occurrence = (
            datetime.date.today() - datetime.timedelta(days=10)
        )
        self.abonnement.save(update_fields=["derniere_occurrence"])
        alerte = detecter_alerte_abonnement_en_retard(self.abonnement)
        self.assertIsNone(alerte)

    def test_alerte_divergence(self):
        alerte = detecter_alerte_divergence_abonnement(
            self.abonnement, Decimal("-25.00")
        )
        self.assertIsNotNone(alerte)
        self.assertEqual(
            alerte.type_alerte, TypeAlerte.ABONNEMENT_DIVERGENCE
        )

    def test_pas_alerte_divergence_dans_seuil(self):
        alerte = detecter_alerte_divergence_abonnement(
            self.abonnement, Decimal("-16.00")
        )
        self.assertIsNone(alerte)

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status as drf_status


class AlerteAPITest(APITestCase):

    def setUp(self):
        self.compte = Compte.objects.create(
            code="CPT-API",
            nom="Compte API",
            type_compte=TypeCompte.objects.create(
                code="COURANT4", libelle="Courant"
            ),
            titulaire=Titulaire.objects.create(
                code="PIERRE4", libelle="Pierre"
            ),
            etablissement=Etablissement.objects.create(
                code="BNP4", libelle="BNP"
            ),
            devise=Devise.objects.create(
                code="EUR4", libelle="Euro", symbole="€", est_defaut=False
            ),
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("50.00"),
            solde_theorique=Decimal("50.00"),
        )
        self.alerte = Alerte.objects.create(
            type_alerte=TypeAlerte.SOLDE_BAS,
            niveau=NiveauAlerte.AVERTISSEMENT,
            compte=self.compte,
            explication="Solde bas détecté.",
            valeur_constatee=Decimal("50.00"),
            valeur_seuil=Decimal("100.00"),
        )

    def test_liste_alertes(self):
        response = self.client.get(reverse("alerte-list"))
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_detail_alerte(self):
        response = self.client.get(
            reverse("alerte-detail", args=[self.alerte.id])
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(
            response.data["type_alerte"], TypeAlerte.SOLDE_BAS
        )

    def test_alerte_read_only(self):
        """Les alertes ne peuvent pas être créées via l'API."""
        response = self.client.post(
            reverse("alerte-list"),
            {"type_alerte": "SOLDE_BAS", "explication": "Test"},
            format="json"
        )
        self.assertEqual(
            response.status_code, drf_status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_acquitter(self):
        response = self.client.post(
            reverse("alerte-acquitter", args=[self.alerte.id])
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertTrue(response.data["acquittee"])
        self.assertIsNotNone(response.data["acquittee_le"])

    def test_acquitter_deux_fois_refuse(self):
        self.alerte.acquitter()
        response = self.client.post(
            reverse("alerte-acquitter", args=[self.alerte.id])
        )
        self.assertEqual(
            response.status_code, drf_status.HTTP_400_BAD_REQUEST
        )

    def test_acquitter_tout(self):
        Alerte.objects.create(
            type_alerte=TypeAlerte.BUDGET_ALERTE,
            niveau=NiveauAlerte.AVERTISSEMENT,
            explication="Budget en alerte.",
        )
        response = self.client.post(
            reverse("alerte-acquitter-tout")
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertIn("2", response.data["detail"])

    def test_filtre_par_acquittee(self):
        self.alerte.acquitter()
        response = self.client.get(
            reverse("alerte-list"), {"acquittee": False}
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_filtre_par_type(self):
        response = self.client.get(
            reverse("alerte-list"),
            {"type_alerte": TypeAlerte.SOLDE_BAS}
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)