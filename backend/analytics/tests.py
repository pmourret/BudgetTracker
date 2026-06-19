import datetime
from decimal import Decimal
from django.test import TestCase

from referentiels.models import (
    TypeCompte, Etablissement, Titulaire, Devise, TypeFlux, StatutFlux,
    Frequence
)
from comptes.models import Compte
from categories.models import Categorie
from flux.models import Flux
from budgets.models import Budget, BudgetTemplate
from abonnements.models import Abonnement
from analytics.services.dashboard import calculer_dashboard
from analytics.services.compte_dashboard import calculer_compte_dashboard
from analytics.services.projection import (
    calculer_solde_projete, calculer_capacite_restante
)
from analytics.services.trajectoire import calculer_trajectoire


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


class _PrevisionnelTestMixin:
    """
    Données communes aux tests du prévisionnel (phase 10-A).

    Date de référence injectée (les services acceptent `aujourd_hui`) :
    les tests sont déterministes quel que soit le jour d'exécution.
    """

    AUJOURD_HUI = datetime.date(2026, 6, 10)
    MOIS = datetime.date(2026, 6, 1)

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
        self.frequence_mensuelle = Frequence.objects.create(
            code="MENSUEL", libelle="Mensuel", nb_jours=30
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
        # Initialise solde_theorique (objects.create ne passe pas par le ViewSet)
        from comptes.services.solde import calculer_solde
        calculer_solde(self.compte)

    def _make_flux(self, montant, date_flux, **kwargs):
        return Flux.objects.create(
            compte=self.compte,
            categorie=kwargs.pop("categorie", self.categorie),
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal(str(montant)),
            date_flux=date_flux,
            **kwargs,
        )

    def _make_abonnement(self, montant, categorie=None, jour_echeance=20,
                         date_debut=None, frequence=None):
        return Abonnement.objects.create(
            nom="Abo test",
            compte=self.compte,
            categorie=categorie,
            type_flux=self.type_flux,
            frequence=frequence or self.frequence_mensuelle,
            montant_attendu=Decimal(str(montant)),
            date_debut=date_debut or datetime.date(2026, 1, 20),
            jour_echeance=jour_echeance,
        )


class SoldeProjeteServiceTest(_PrevisionnelTestMixin, TestCase):

    def test_solde_projete_sans_futur_ni_abonnement(self):
        """Sans flux futur ni abonnement, le solde projeté = solde théorique."""
        self._make_flux("-200.00", date_flux=datetime.date(2026, 6, 5))
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["composantes"]["solde_actuel"], Decimal("800.00"))
        self.assertEqual(data["composantes"]["flux_futurs_mois"], Decimal("0.00"))
        self.assertEqual(
            data["composantes"]["abonnements_a_echoir_non_budgetes"], Decimal("0.00")
        )
        self.assertEqual(
            data["composantes"]["reste_a_depenser_budgete"], Decimal("0.00")
        )
        self.assertEqual(data["solde_projete"], Decimal("800.00"))

    def test_flux_futur_depense_compte_une_fois(self):
        """Un flux futur daté du mois est compté UNE fois (pas via solde_actuel)."""
        self._make_flux("-150.00", date_flux=datetime.date(2026, 6, 25))
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["composantes"]["solde_actuel"], Decimal("1000.00"))
        self.assertEqual(data["composantes"]["flux_futurs_mois"], Decimal("-150.00"))
        self.assertEqual(data["solde_projete"], Decimal("850.00"))

    def test_flux_futur_recette(self):
        """Une recette future datée augmente le solde projeté du montant signé."""
        self._make_flux("500.00", date_flux=datetime.date(2026, 6, 28))
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["solde_projete"], Decimal("1500.00"))

    def test_transferts_et_ajustements_futurs_exclus(self):
        """Transferts et ajustements futurs n'affectent pas la projection."""
        self._make_flux("-300.00", date_flux=datetime.date(2026, 6, 20),
                        est_transfert=True, categorie=None)
        self._make_flux("-80.00", date_flux=datetime.date(2026, 6, 22),
                        est_ajustement=True, categorie=None)
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["composantes"]["flux_futurs_mois"], Decimal("0.00"))
        self.assertEqual(data["solde_projete"], Decimal("1000.00"))

    def test_abonnement_a_echoir_compte_une_fois(self):
        """Un abonnement à échoir dans le mois, non budgété, est déduit une fois."""
        self._make_abonnement("-25.00", categorie=self.categorie)
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(
            data["composantes"]["abonnements_a_echoir_non_budgetes"],
            Decimal("-25.00"),
        )
        self.assertEqual(data["solde_projete"], Decimal("975.00"))

    def test_abonnement_deja_saisi_en_flux_futur_non_double_compte(self):
        """Un abonnement déjà matérialisé en flux futur daté n'est pas recompté."""
        self._make_abonnement("-25.00", categorie=self.categorie)
        self._make_flux("-25.00", date_flux=datetime.date(2026, 6, 20))
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(
            data["composantes"]["abonnements_a_echoir_non_budgetes"],
            Decimal("0.00"),
        )
        self.assertEqual(data["composantes"]["flux_futurs_mois"], Decimal("-25.00"))
        self.assertEqual(data["solde_projete"], Decimal("975.00"))

    def test_abonnement_budgete_non_double_compte(self):
        """Un abonnement couvert par un budget est inclus dans le reste, pas recompté."""
        Budget.objects.create(
            categorie=self.categorie, mois=self.MOIS,
            montant_prevu=Decimal("100.00"),
        )
        self._make_abonnement("-25.00", categorie=self.categorie)
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(
            data["composantes"]["abonnements_a_echoir_non_budgetes"],
            Decimal("0.00"),
        )
        self.assertEqual(
            data["composantes"]["reste_a_depenser_budgete"], Decimal("100.00")
        )
        self.assertEqual(data["solde_projete"], Decimal("900.00"))

    def test_abonnement_couvert_par_budget_majeur(self):
        """Un abonnement sur une mineure incluse d'un budget majeur est couvert."""
        parent = Categorie.objects.create(code="LOISIRS", nom="Loisirs")
        mineure = Categorie.objects.create(
            code="STREAMING", nom="Streaming", parent=parent
        )
        budget = Budget.objects.create(
            categorie=parent, mois=self.MOIS,
            montant_prevu=Decimal("100.00"), est_budget_majeur=True,
        )
        budget.categories_incluses.add(mineure)
        self._make_abonnement("-25.00", categorie=mineure)
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(
            data["composantes"]["abonnements_a_echoir_non_budgetes"],
            Decimal("0.00"),
        )

    def test_reste_a_depenser_budgete(self):
        """Le reste à dépenser (prévu − consommé) est déduit du solde projeté."""
        Budget.objects.create(
            categorie=self.categorie, mois=self.MOIS,
            montant_prevu=Decimal("400.00"),
        )
        self._make_flux("-150.00", date_flux=datetime.date(2026, 6, 5))
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(
            data["composantes"]["reste_a_depenser_budgete"], Decimal("250.00")
        )
        # 1000 - 150 (réalisé) - 250 (reste) = 600
        self.assertEqual(data["solde_projete"], Decimal("600.00"))

    def test_fiabilite_et_definition_presentes(self):
        """Le bloc est explicitement étiqueté projeté, jamais vérité comptable."""
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["fiabilite"], "elevee")
        self.assertIn("definition", data)


class CapaciteRestanteServiceTest(_PrevisionnelTestMixin, TestCase):

    def test_capacite_nominale(self):
        """capacité = budgets − consommé − abonnements restants non budgétés."""
        autre = Categorie.objects.create(code="TRANSPORT", nom="Transport")
        Budget.objects.create(
            categorie=self.categorie, mois=self.MOIS,
            montant_prevu=Decimal("400.00"),
        )
        Budget.objects.create(
            categorie=autre, mois=self.MOIS,
            montant_prevu=Decimal("200.00"),
        )
        self._make_flux("-150.00", date_flux=datetime.date(2026, 6, 5))
        self._make_abonnement("-30.00", categorie=None)  # non budgété
        data = calculer_capacite_restante(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["composantes"]["total_budgets"], Decimal("600.00"))
        self.assertEqual(data["composantes"]["total_consomme"], Decimal("150.00"))
        self.assertEqual(
            data["composantes"]["abonnements_restants"], Decimal("30.00")
        )
        self.assertEqual(data["capacite"], Decimal("420.00"))

    def test_capacite_budget_a_zero(self):
        """Un budget à 0 déjà consommé donne une capacité négative (dépassement)."""
        Budget.objects.create(
            categorie=self.categorie, mois=self.MOIS,
            montant_prevu=Decimal("0.00"),
        )
        self._make_flux("-50.00", date_flux=datetime.date(2026, 6, 5))
        data = calculer_capacite_restante(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["capacite"], Decimal("-50.00"))

    def test_capacite_sans_budget(self):
        """Sans budget ni abonnement, la capacité est nulle."""
        data = calculer_capacite_restante(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["capacite"], Decimal("0.00"))
        self.assertEqual(data["fiabilite"], "moyenne")


class TrajectoireServiceTest(_PrevisionnelTestMixin, TestCase):

    def test_nb_points_et_mois(self):
        """La trajectoire renvoie un point par mois, à partir du mois courant."""
        data = calculer_trajectoire(nb_mois=6, aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["nb_mois"], 6)
        self.assertEqual(len(data["points"]), 6)
        self.assertEqual(data["points"][0]["mois"], "2026-06-01")
        self.assertEqual(data["points"][5]["mois"], "2026-11-01")

    def test_fiabilite_degressive(self):
        """M0 = elevee, M+1 à M+3 = moyenne, M+4 et au-delà = faible."""
        data = calculer_trajectoire(nb_mois=6, aujourd_hui=self.AUJOURD_HUI)
        fiabilites = [p["fiabilite"] for p in data["points"]]
        self.assertEqual(
            fiabilites,
            ["elevee", "moyenne", "moyenne", "moyenne", "faible", "faible"],
        )
        # Le bloc porte la fiabilité du point le plus lointain
        self.assertEqual(data["fiabilite"], "faible")

    def test_cumul_avec_revenu_recurrent(self):
        """Un salaire récurrent alimente chaque mois ; le cumul s'additionne."""
        self._make_abonnement(
            "1000.00", categorie=None, jour_echeance=25,
            date_debut=datetime.date(2026, 1, 25),
        )
        data = calculer_trajectoire(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        for point in data["points"]:
            self.assertEqual(point["revenus_attendus"], Decimal("1000.00"))
            self.assertEqual(point["epargne_mois"], Decimal("1000.00"))
        self.assertEqual(data["points"][0]["cumul"], Decimal("1000.00"))
        self.assertEqual(data["points"][1]["cumul"], Decimal("2000.00"))
        self.assertEqual(data["points"][2]["cumul"], Decimal("3000.00"))

    def test_template_estime_les_mois_futurs(self):
        """Les templates actifs estiment les dépenses variables des mois futurs."""
        BudgetTemplate.objects.create(
            categorie=self.categorie, montant_defaut=Decimal("300.00")
        )
        data = calculer_trajectoire(nb_mois=2, aujourd_hui=self.AUJOURD_HUI)
        # M0 : pas de budget créé ce mois → aucune dépense estimée
        self.assertEqual(data["points"][0]["depenses_attendues"], Decimal("0.00"))
        # M+1 : l'enveloppe du template est comptée
        self.assertEqual(data["points"][1]["depenses_attendues"], Decimal("300.00"))

    def test_abonnement_couvert_par_template_non_double_compte(self):
        """Mois futur : un abonnement couvert par un template reste dans l'enveloppe."""
        BudgetTemplate.objects.create(
            categorie=self.categorie, montant_defaut=Decimal("300.00")
        )
        self._make_abonnement("-50.00", categorie=self.categorie)
        data = calculer_trajectoire(nb_mois=2, aujourd_hui=self.AUJOURD_HUI)
        # M+1 : 50 (abonnement) + 250 (complément d'enveloppe) = 300, pas 350
        self.assertEqual(data["points"][1]["depenses_attendues"], Decimal("300.00"))

    def test_abonnement_non_couvert_ajoute_aux_mois_futurs(self):
        """Mois futur : un abonnement sans template est ajouté en dépense autonome."""
        self._make_abonnement("-50.00", categorie=self.categorie)
        data = calculer_trajectoire(nb_mois=2, aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["points"][1]["depenses_attendues"], Decimal("50.00"))


class PrevisionnelAPITest(TestCase):
    """Teste l'endpoint HTTP du prévisionnel."""

    def test_endpoint_renvoie_les_trois_blocs(self):
        from django.urls import reverse
        url = reverse("previsionnel")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        for bloc in ("solde_projete", "capacite_restante", "trajectoire"):
            self.assertIn(bloc, response.data)
            self.assertIn("fiabilite", response.data[bloc])
            self.assertIn("definition", response.data[bloc])

    def test_nb_mois_parametrable(self):
        from django.urls import reverse
        url = reverse("previsionnel")
        response = self.client.get(url, {"nb_mois": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["trajectoire"]["nb_mois"], 3)
        self.assertEqual(len(response.data["trajectoire"]["points"]), 3)

class CompteDashboardServiceTest(TestCase):
    """Dashboard scopé à un compte unique (agrégats du mois courant)."""

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
        # Catégorie majeure + mineure pour tester le regroupement
        self.cat_majeure = Categorie.objects.create(code="ALIM", nom="Alimentation")
        self.cat_mineure = Categorie.objects.create(
            code="COURSES", nom="Courses", parent=self.cat_majeure
        )
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Compte A",
            type_compte=self.type_compte, titulaire=self.titulaire,
            etablissement=self.etablissement, devise=self.devise,
            solde_initial=Decimal("1000.00"), solde_reel=Decimal("1000.00"),
        )
        self.autre_compte = Compte.objects.create(
            code="CPT-0002", nom="Compte B",
            type_compte=self.type_compte, titulaire=self.titulaire,
            etablissement=self.etablissement, devise=self.devise,
            solde_initial=Decimal("500.00"), solde_reel=Decimal("500.00"),
        )
        self.mois_courant = datetime.date.today().replace(day=1)

    def _flux(self, compte, montant, categorie=None, est_transfert=False,
              est_ajustement=False, libelle="", date_flux=None):
        return Flux.objects.create(
            compte=compte, categorie=categorie,
            type_flux=self.type_flux, statut=self.statut, devise=self.devise,
            montant=Decimal(str(montant)),
            date_flux=date_flux or self.mois_courant,
            est_transfert=est_transfert, est_ajustement=est_ajustement,
            libelle=libelle,
        )

    def test_autre_compte_exclu(self):
        """Les flux d'un autre compte n'entrent dans aucun agrégat."""
        self._flux(self.compte, "-100.00", self.cat_mineure)
        self._flux(self.autre_compte, "-999.00", self.cat_mineure)
        data = calculer_compte_dashboard(self.compte.id)
        self.assertEqual(data["metriques"]["depenses_mois"], Decimal("100.00"))
        self.assertEqual(data["metriques"]["nb_flux"], 1)

    def test_transferts_et_ajustements_exclus(self):
        """Transferts et ajustements ignorés dans dépenses/revenus/ventilation."""
        self._flux(self.compte, "-100.00", self.cat_mineure)
        self._flux(self.compte, "-300.00", est_transfert=True)
        self._flux(self.compte, "-50.00", self.cat_mineure, est_ajustement=True)
        data = calculer_compte_dashboard(self.compte.id)
        self.assertEqual(data["metriques"]["depenses_mois"], Decimal("100.00"))
        # Une seule majeure, total 100 (l'ajustement n'y figure pas)
        self.assertEqual(len(data["depenses_par_categorie"]), 1)
        self.assertEqual(data["depenses_par_categorie"][0]["total"], Decimal("100.00"))

    def test_revenus_et_epargne(self):
        """Revenus positifs + épargne nette = revenus + dépenses signées."""
        self._flux(self.compte, "2000.00", self.cat_mineure)
        self._flux(self.compte, "-500.00", self.cat_mineure)
        data = calculer_compte_dashboard(self.compte.id)
        self.assertEqual(data["metriques"]["revenus_mois"], Decimal("2000.00"))
        self.assertEqual(data["metriques"]["epargne_nette"], Decimal("1500.00"))

    def test_ventilation_regroupee_sous_la_majeure(self):
        """La mineure est regroupée sous sa catégorie majeure."""
        self._flux(self.compte, "-80.00", self.cat_mineure)
        data = calculer_compte_dashboard(self.compte.id)
        majeure = data["depenses_par_categorie"][0]
        self.assertEqual(majeure["nom"], "Alimentation")
        self.assertEqual(majeure["total"], Decimal("80.00"))
        self.assertEqual(len(majeure["sous_categories"]), 1)
        self.assertEqual(majeure["sous_categories"][0]["nom"], "Courses")

    def test_top_depenses_triees_et_limitees(self):
        """Top dépenses : la plus négative d'abord, max 5."""
        for m in ("-10", "-60", "-20", "-90", "-30", "-5"):
            self._flux(self.compte, m, self.cat_mineure, libelle=f"D{m}")
        data = calculer_compte_dashboard(self.compte.id)
        top = data["top_depenses"]
        self.assertEqual(len(top), 5)
        self.assertEqual(top[0]["montant"], Decimal("-90.00"))
        montants = [t["montant"] for t in top]
        self.assertEqual(montants, sorted(montants))

    def test_soldes_du_compte_exposes(self):
        """Les soldes du compte sont lus tels quels, jamais recalculés ici."""
        self._flux(self.compte, "-100.00", self.cat_mineure)
        self.compte.refresh_from_db()
        data = calculer_compte_dashboard(self.compte.id)
        self.assertEqual(
            data["compte"]["solde_theorique"], self.compte.solde_theorique
        )
        self.assertEqual(data["compte"]["nom"], "Compte A")

    def test_compte_inexistant_leve_does_not_exist(self):
        import uuid
        with self.assertRaises(Compte.DoesNotExist):
            calculer_compte_dashboard(uuid.uuid4())


class CompteDashboardAPITest(TestCase):
    """Teste l'endpoint HTTP du dashboard compte."""

    def setUp(self):
        self.type_compte = TypeCompte.objects.create(code="COURANT", libelle="Courant")
        self.titulaire = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        self.etablissement = Etablissement.objects.create(code="BNP", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True
        )
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Compte A",
            type_compte=self.type_compte, titulaire=self.titulaire,
            etablissement=self.etablissement, devise=self.devise,
            solde_initial=Decimal("1000.00"), solde_reel=Decimal("1000.00"),
        )

    def test_endpoint_ok(self):
        from django.urls import reverse
        url = reverse("compte-dashboard", args=[self.compte.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        for bloc in ("compte", "metriques", "depenses_par_categorie", "top_depenses"):
            self.assertIn(bloc, response.data)

    def test_endpoint_404_si_compte_inconnu(self):
        import uuid
        from django.urls import reverse
        url = reverse("compte-dashboard", args=[uuid.uuid4()])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
