import datetime
from decimal import Decimal
from django.test import TestCase

from referentiels.models import (
    TypeCompte, Etablissement, Titulaire, Devise, TypeFlux, StatutFlux
)
from comptes.models import Compte
from categories.models import Categorie
from flux.models import Flux
from budgets.models import Budget
from analytics.services.dashboard import calculer_dashboard


class DashboardServiceTest(TestCase):

    def setUp(self):
        self.type_compte = TypeCompte.objects.create(code="COURANT", libelle="Courant")
        self.titulaire = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        self.etablissement = Etablissement.objects.create(code="BNP", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True
        )
        self.categorie = Categorie.objects.create(code="COURSES", nom="Courses")
        self.compte = Compte.objects.create(
            code="CPT-0001",
            nom="Compte test",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("1000.00"),
        )
        # Mois courant pour les flux
        self.mois_courant = datetime.date.today().replace(day=1)

    def _make_flux(self, montant, est_transfert=False, date_flux=None):
        return Flux.objects.create(
            compte=self.compte,
            categorie=self.categorie,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal(str(montant)),
            date_flux=date_flux or self.mois_courant,
            est_transfert=est_transfert,
        )

    def test_solde_total(self):
        """Le solde total = solde théorique des comptes actifs."""
        self._make_flux("-200.00")
        data = calculer_dashboard()
        # solde_initial 1000 - 200 = 800
        self.assertEqual(data["metriques"]["solde_total"], Decimal("800.00"))

    def test_depenses_du_mois(self):
        """Les dépenses = somme des montants négatifs, en valeur absolue."""
        self._make_flux("-200.00")
        self._make_flux("-50.00")
        data = calculer_dashboard()
        self.assertEqual(data["metriques"]["depenses_mois"], Decimal("250.00"))

    def test_revenus_du_mois(self):
        """Les revenus = somme des montants positifs."""
        self._make_flux("2800.00")
        data = calculer_dashboard()
        self.assertEqual(data["metriques"]["revenus_mois"], Decimal("2800.00"))

    def test_epargne_nette(self):
        """Épargne nette = revenus - dépenses."""
        self._make_flux("2800.00")
        self._make_flux("-1000.00")
        data = calculer_dashboard()
        self.assertEqual(data["metriques"]["epargne_nette"], Decimal("1800.00"))

    def test_taux_epargne(self):
        """Taux d'épargne = épargne / revenus * 100."""
        self._make_flux("1000.00")
        self._make_flux("-250.00")
        data = calculer_dashboard()
        # (1000 - 250) / 1000 * 100 = 75.0
        self.assertEqual(data["metriques"]["taux_epargne"], Decimal("75.0"))

    def test_transferts_exclus(self):
        """Les transferts ne comptent ni en dépense ni en revenu."""
        self._make_flux("-300.00", est_transfert=True)
        self._make_flux("-100.00", est_transfert=False)
        data = calculer_dashboard()
        # Seul le flux non-transfert compte
        self.assertEqual(data["metriques"]["depenses_mois"], Decimal("100.00"))

    def test_taux_epargne_sans_revenu(self):
        """Pas de division par zéro si aucun revenu."""
        self._make_flux("-100.00")
        data = calculer_dashboard()
        self.assertEqual(data["metriques"]["taux_epargne"], Decimal("0.0"))

    def test_derniers_flux_limite_5(self):
        """Le dashboard ne renvoie que les 5 flux les plus récents."""
        for i in range(7):
            self._make_flux("-10.00")
        data = calculer_dashboard()
        self.assertEqual(len(data["derniers_flux"]), 5)

    def test_budgets_inclus(self):
        """Les budgets du mois courant sont inclus."""
        Budget.objects.create(
            categorie=self.categorie,
            mois=self.mois_courant,
            montant_prevu=Decimal("400.00"),
        )
        data = calculer_dashboard()
        self.assertEqual(len(data["budgets"]), 1)
        self.assertEqual(data["budgets"][0]["categorie_nom"], "Courses")

    def test_evolution_solde_nb_points(self):
        """L'évolution renvoie un point par mois demandé."""
        data = calculer_dashboard(nb_mois=6)
        self.assertEqual(len(data["evolution_solde"]), 6)

    def test_patrimoine_separe_et_estimatif(self):
        """Le bloc patrimoine est séparé et étiqueté estimatif."""
        data = calculer_dashboard()
        self.assertIn("patrimoine", data)
        self.assertEqual(data["patrimoine"]["fiabilite"], "estimative")

    def test_metriques_fiabilite_reelle(self):
        """Les métriques financières sont de fiabilité réelle."""
        data = calculer_dashboard()
        self.assertEqual(data["metriques"]["fiabilite"], "reel")


class DashboardAPITest(TestCase):
    """Teste l'endpoint HTTP du dashboard."""

    def test_endpoint_repond(self):
        from django.urls import reverse
        url = reverse("dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("metriques", response.data)
        self.assertIn("evolution_solde", response.data)

    def test_nb_mois_parametrable(self):
        from django.urls import reverse
        url = reverse("dashboard")
        response = self.client.get(url, {"nb_mois": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["evolution_solde"]), 3)