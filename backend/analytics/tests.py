import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.test import TestCase

from referentiels.models import (
    TypeCompte, Etablissement, Titulaire, Devise, TypeFlux, StatutFlux,
    Frequence
)
from comptes.models import Compte
from categories.models import Categorie
from flux.models import Flux
from budgets.models import Budget, BudgetTemplate
from analytics.services.dashboard import calculer_dashboard
from analytics.services.compte_dashboard import calculer_compte_dashboard
from analytics.services.projection import (
    calculer_solde_projete, calculer_capacite_restante
)
from analytics.services.trajectoire import calculer_trajectoire
from analytics.services.analyse import calculer_analyse


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

    def test_depenses_par_jour_agregees(self):
        """Les dépenses sont ventilées par jour, en valeur absolue, triées."""
        j5 = self.mois_courant.replace(day=5)
        j12 = self.mois_courant.replace(day=12)
        self._make_flux("-30.00", date_flux=j12)
        self._make_flux("-20.00", date_flux=j5)
        self._make_flux("-10.00", date_flux=j5)
        data = calculer_dashboard()
        jours = data["depenses_par_jour"]
        self.assertEqual(jours, [
            {"date": j5.isoformat(), "total": Decimal("30.00")},
            {"date": j12.isoformat(), "total": Decimal("30.00")},
        ])

    def test_depenses_par_jour_exclut_transferts(self):
        """Transferts et revenus ne comptent pas dans la heatmap des dépenses."""
        self._make_flux("-40.00")
        self._make_flux("-200.00", est_transfert=True)
        self._make_flux("2800.00")
        data = calculer_dashboard()
        jours = data["depenses_par_jour"]
        self.assertEqual(len(jours), 1)
        self.assertEqual(jours[0]["total"], Decimal("40.00"))

    def test_navigation_mois_scope_les_metriques(self):
        """Sélectionner un mois passé renvoie les métriques de CE mois."""
        mois_passe = self.mois_courant - relativedelta(months=2)
        self._make_flux("-100.00")  # mois courant
        self._make_flux("-30.00", date_flux=mois_passe)  # mois passé
        data = calculer_dashboard(mois=mois_passe)
        self.assertEqual(data["mois_courant"], mois_passe.isoformat())
        self.assertEqual(data["metriques"]["depenses_mois"], Decimal("30.00"))

    def test_navigation_bornee_au_premier_et_dernier_mois(self):
        """mois_min = premier mois avec flux ; mois_max = mois courant."""
        mois_passe = self.mois_courant - relativedelta(months=2)
        self._make_flux("-50.00", date_flux=mois_passe)
        data = calculer_dashboard()
        self.assertEqual(data["mois_min"], mois_passe.isoformat())
        self.assertEqual(data["mois_max"], self.mois_courant.isoformat())

    def test_navigation_futur_ramenee_au_mois_courant(self):
        """Un mois au-delà du mois courant est borné au mois courant (réel)."""
        futur = self.mois_courant + relativedelta(months=3)
        self._make_flux("-100.00")
        data = calculer_dashboard(mois=futur)
        self.assertEqual(data["mois_courant"], self.mois_courant.isoformat())

    def test_solde_total_fin_de_mois_passe(self):
        """Le solde total reflète la fin du mois sélectionné (cumul des flux)."""
        mois_passe = self.mois_courant - relativedelta(months=1)
        self._make_flux("-200.00", date_flux=mois_passe)
        self._make_flux("-500.00")  # mois courant : exclu de la fin du mois passé
        data = calculer_dashboard(mois=mois_passe)
        # solde_initial 1000 - 200 (mois passé), le -500 du mois courant exclu
        self.assertEqual(data["metriques"]["solde_total"], Decimal("800.00"))


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


class SoldeProjeteServiceTest(_PrevisionnelTestMixin, TestCase):

    def test_solde_projete_sans_futur(self):
        """Sans flux futur, le solde projeté = solde théorique."""
        self._make_flux("-200.00", date_flux=datetime.date(2026, 6, 5))
        data = calculer_solde_projete(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["composantes"]["solde_actuel"], Decimal("800.00"))
        self.assertEqual(data["composantes"]["flux_futurs_mois"], Decimal("0.00"))
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
        """capacité = budgets − consommé."""
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
        data = calculer_capacite_restante(aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["composantes"]["total_budgets"], Decimal("600.00"))
        self.assertEqual(data["composantes"]["total_consomme"], Decimal("150.00"))
        self.assertEqual(data["capacite"], Decimal("450.00"))

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
        """Sans budget, la capacité est nulle."""
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

    def test_cumul_avec_revenu_futur(self):
        """Un revenu futur daté alimente le cumul du mois où il tombe."""
        self._make_flux("2000.00", date_flux=datetime.date(2026, 7, 5))
        data = calculer_trajectoire(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        # M0 (juin) : aucun flux → 0 ; M+1 (juillet) : +2000 daté
        self.assertEqual(data["points"][0]["revenus_attendus"], Decimal("0.00"))
        self.assertEqual(data["points"][1]["revenus_attendus"], Decimal("2000.00"))
        self.assertEqual(data["points"][1]["cumul"], Decimal("2000.00"))
        self.assertEqual(data["points"][2]["cumul"], Decimal("2000.00"))

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

    def test_flux_futur_deduit_de_l_enveloppe_template(self):
        """Mois futur : un flux daté couvre une part de l'enveloppe du template."""
        BudgetTemplate.objects.create(
            categorie=self.categorie, montant_defaut=Decimal("300.00")
        )
        self._make_flux("-50.00", date_flux=datetime.date(2026, 7, 15))
        data = calculer_trajectoire(nb_mois=2, aujourd_hui=self.AUJOURD_HUI)
        # M+1 : 50 (flux daté) + 250 (complément d'enveloppe) = 300, pas 350
        self.assertEqual(data["points"][1]["depenses_attendues"], Decimal("300.00"))


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


class _AnalyseTestMixin:
    """
    Données communes aux tests de l'analyse rétrospective (Phase 13).

    Date de référence injectée (le service accepte `aujourd_hui`) : les
    tests sont déterministes. Avec jour de bascule 1 (défaut), le mois
    comptable d'un flux = date_flux.replace(day=1).
    """

    AUJOURD_HUI = datetime.date(2026, 6, 10)  # mois comptable courant : 2026-06

    def setUp(self):
        self.type_compte = TypeCompte.objects.create(code="COURANT", libelle="Courant")
        self.titulaire = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        self.etablissement = Etablissement.objects.create(code="BNP", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="EUR", est_defaut=True
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Debit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE", libelle="Valide", est_definitif=True
        )
        self.titulaire2 = Titulaire.objects.create(code="CONJOINT", libelle="Conjoint")
        self.parent = Categorie.objects.create(code="ALIM", nom="Alimentation")
        self.enfant = Categorie.objects.create(
            code="COURSES", nom="Courses", parent=self.parent
        )
        self.autre = Categorie.objects.create(code="TRANSPORT", nom="Transport")
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Compte A",
            type_compte=self.type_compte, titulaire=self.titulaire,
            etablissement=self.etablissement, devise=self.devise,
            solde_initial=Decimal("1000.00"), solde_reel=Decimal("1000.00"),
        )
        # Compte perso du second titulaire + compte commun du foyer.
        self.compte2 = Compte.objects.create(
            code="CPT-0002", nom="Compte B",
            type_compte=self.type_compte, titulaire=self.titulaire2,
            etablissement=self.etablissement, devise=self.devise,
        )
        self.compte_commun = Compte.objects.create(
            code="CPT-0003", nom="Compte joint", est_commun=True,
            type_compte=self.type_compte, titulaire=self.titulaire,
            etablissement=self.etablissement, devise=self.devise,
        )
        # Comptes d'épargne (est_epargne) avec taux, alimentés par transferts.
        self.epargne = Compte.objects.create(
            code="CPT-0004", nom="Livret A", est_epargne=True,
            taux_annuel=Decimal("3.00"),
            type_compte=self.type_compte, titulaire=self.titulaire,
            etablissement=self.etablissement, devise=self.devise,
            solde_initial=Decimal("500.00"), solde_reel=Decimal("500.00"),
        )
        self.epargne2 = Compte.objects.create(
            code="CPT-0005", nom="LDD", est_epargne=True,
            taux_annuel=Decimal("2.50"),
            type_compte=self.type_compte, titulaire=self.titulaire,
            etablissement=self.etablissement, devise=self.devise,
        )

    def _flux(self, montant, date_flux, categorie=None, libelle="Flux",
              est_transfert=False, est_ajustement=False, compte=None):
        return Flux.objects.create(
            compte=compte or self.compte,
            categorie=categorie,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal(str(montant)),
            date_flux=date_flux,
            libelle=libelle,
            est_transfert=est_transfert,
            est_ajustement=est_ajustement,
        )


class AnalyseServiceTest(_AnalyseTestMixin, TestCase):

    def test_structure_et_fiabilite(self):
        """Trois blocs présents, tout étiqueté réel, fenêtre bornée."""
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["fiabilite"], "reel")
        self.assertEqual(data["mois_debut"], "2026-04-01")
        self.assertEqual(data["mois_fin"], "2026-06-01")
        for bloc in ("tendances", "epargne", "titulaires", "categories", "rythme", "saisonnalite"):
            self.assertIn(bloc, data)
            self.assertEqual(data[bloc]["fiabilite"], "reel")

    def test_serie_mensuelle_un_point_par_mois(self):
        """La série tendances a un point par mois de la fenêtre."""
        self._flux("-100.00", datetime.date(2026, 4, 15), self.enfant)
        self._flux("-200.00", datetime.date(2026, 5, 15), self.enfant)
        self._flux("2800.00", datetime.date(2026, 6, 5))
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        series = data["tendances"]["series"]
        self.assertEqual([p["mois"] for p in series],
                         ["2026-04-01", "2026-05-01", "2026-06-01"])
        self.assertEqual(series[0]["depenses"], Decimal("100.00"))
        self.assertEqual(series[2]["revenus"], Decimal("2800.00"))

    def test_totaux_et_moyennes(self):
        """Totaux et moyennes mensuelles sur la fenêtre."""
        self._flux("-300.00", datetime.date(2026, 4, 10), self.enfant)
        self._flux("-300.00", datetime.date(2026, 6, 10), self.enfant)
        self._flux("3000.00", datetime.date(2026, 5, 1))
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        tend = data["tendances"]
        self.assertEqual(tend["totaux_periode"]["depenses"], Decimal("600.00"))
        self.assertEqual(tend["totaux_periode"]["revenus"], Decimal("3000.00"))
        self.assertEqual(tend["totaux_periode"]["epargne_nette"], Decimal("2400.00"))
        self.assertEqual(tend["moyennes_mensuelles"]["depenses"], Decimal("200.00"))

    def test_comparaison_periode_precedente(self):
        """La comparaison oppose la fenêtre à la fenêtre précédente."""
        # Période précédente (jan-mar) : 100 de dépenses
        self._flux("-100.00", datetime.date(2026, 2, 10), self.enfant)
        # Période courante (avr-juin) : 200 de dépenses
        self._flux("-200.00", datetime.date(2026, 5, 10), self.enfant)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        cmp = data["tendances"]["comparaison_periode_precedente"]["depenses"]
        self.assertEqual(cmp["actuel"], Decimal("200.00"))
        self.assertEqual(cmp["precedent"], Decimal("100.00"))
        self.assertEqual(cmp["variation_pct"], Decimal("100.0"))

    def test_comparaison_sans_base_precedente(self):
        """variation_pct = None si la période précédente est nulle."""
        self._flux("-200.00", datetime.date(2026, 5, 10), self.enfant)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        cmp = data["tendances"]["comparaison_periode_precedente"]["depenses"]
        self.assertIsNone(cmp["variation_pct"])

    def test_transferts_et_ajustements_exclus(self):
        """Transferts et ajustements ne comptent nulle part."""
        self._flux("-500.00", datetime.date(2026, 5, 10), self.enfant, est_transfert=True)
        self._flux("-400.00", datetime.date(2026, 5, 11), self.enfant, est_ajustement=True)
        self._flux("-100.00", datetime.date(2026, 5, 12), self.enfant)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["tendances"]["totaux_periode"]["depenses"], Decimal("100.00"))
        self.assertEqual(data["categories"]["total_periode"], Decimal("100.00"))

    def test_categories_mineure_regroupee_sous_majeure(self):
        """La dépense d'une mineure remonte sous sa catégorie majeure."""
        self._flux("-150.00", datetime.date(2026, 5, 10), self.enfant)
        self._flux("-50.00", datetime.date(2026, 6, 10), self.autre)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        cats = data["categories"]["par_categorie"]
        # Triées par total décroissant : Alimentation (150) avant Transport (50)
        self.assertEqual(cats[0]["nom"], "Alimentation")
        self.assertEqual(cats[0]["total_periode"], Decimal("150.00"))
        self.assertEqual(cats[0]["part_pct"], Decimal("75.0"))
        self.assertEqual(len(cats[0]["serie"]), 3)

    def test_titulaires_bucket_commun_separe(self):
        """Comptes perso ventilés par titulaire ; les communs dans « Commun »."""
        self._flux("-100.00", datetime.date(2026, 5, 10), self.enfant, compte=self.compte)
        self._flux("-200.00", datetime.date(2026, 5, 11), self.enfant, compte=self.compte2)
        self._flux("-300.00", datetime.date(2026, 5, 12), self.enfant, compte=self.compte_commun)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        bloc = data["titulaires"]
        self.assertEqual(bloc["total_depenses"], Decimal("600.00"))
        # Trié par dépenses décroissantes : Commun (300) devant les persos.
        commun = next(b for b in bloc["par_titulaire"] if b["est_commun"])
        self.assertEqual(commun["nom"], "Commun")
        self.assertEqual(commun["depenses"], Decimal("300.00"))
        self.assertEqual(commun["part_depenses_pct"], Decimal("50.0"))
        noms = {b["nom"] for b in bloc["par_titulaire"]}
        self.assertEqual(noms, {"Commun", "Pierre", "Conjoint"})

    def test_titulaires_compte_commun_jamais_attribue_au_proprietaire(self):
        """Le compte joint (propriétaire Pierre) va dans Commun, pas chez Pierre."""
        self._flux("-100.00", datetime.date(2026, 5, 10), self.enfant, compte=self.compte)
        self._flux("-300.00", datetime.date(2026, 5, 12), self.enfant, compte=self.compte_commun)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        pierre = next(b for b in data["titulaires"]["par_titulaire"] if b["nom"] == "Pierre")
        self.assertEqual(pierre["depenses"], Decimal("100.00"))  # sans le compte joint
        self.assertFalse(pierre["est_commun"])

    def test_titulaires_commun_vs_perso_et_revenus(self):
        """Résumé commun/perso et revenus par titulaire."""
        self._flux("2000.00", datetime.date(2026, 5, 1), compte=self.compte)  # revenu Pierre
        self._flux("-100.00", datetime.date(2026, 5, 10), self.enfant, compte=self.compte2)
        self._flux("-300.00", datetime.date(2026, 5, 12), self.enfant, compte=self.compte_commun)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        cvp = data["titulaires"]["commun_vs_perso"]
        self.assertEqual(cvp["commun"]["depenses"], Decimal("300.00"))
        self.assertEqual(cvp["perso"]["depenses"], Decimal("100.00"))
        self.assertEqual(cvp["perso"]["revenus"], Decimal("2000.00"))
        pierre = next(b for b in data["titulaires"]["par_titulaire"] if b["nom"] == "Pierre")
        self.assertEqual(pierre["revenus"], Decimal("2000.00"))
        self.assertEqual(pierre["epargne_nette"], Decimal("2000.00"))

    def test_epargne_versements_nets_et_cumul(self):
        """Versements nets (transferts) vers l'épargne, mois par mois + cumul."""
        self._flux("300.00", datetime.date(2026, 5, 5), compte=self.epargne, est_transfert=True)
        self._flux("200.00", datetime.date(2026, 6, 5), compte=self.epargne, est_transfert=True)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        vpm = {v["mois"]: v for v in data["epargne"]["versements_par_mois"]}
        self.assertEqual(vpm["2026-05-01"]["versement_net"], Decimal("300.00"))
        self.assertEqual(vpm["2026-06-01"]["versement_net"], Decimal("200.00"))
        self.assertEqual(vpm["2026-06-01"]["cumul"], Decimal("500.00"))

    def test_epargne_retrait_compte_en_negatif(self):
        """Un retrait de l'épargne (transfert sortant) apparaît en négatif."""
        self._flux("-100.00", datetime.date(2026, 6, 5), compte=self.epargne, est_transfert=True)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        vpm = {v["mois"]: v for v in data["epargne"]["versements_par_mois"]}
        self.assertEqual(vpm["2026-06-01"]["versement_net"], Decimal("-100.00"))

    def test_epargne_encours_total(self):
        """Encours = solde actuel cumulé des comptes d'épargne."""
        # Livret A : 500 initial + 300 transféré ; LDD : 0.
        self._flux("300.00", datetime.date(2026, 6, 5), compte=self.epargne, est_transfert=True)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["epargne"]["encours_total"], Decimal("800.00"))

    def test_epargne_ecart_budgetaire_vs_reel(self):
        """Écart entre épargne budgétaire (rev−dép) et versement réel."""
        self._flux("2000.00", datetime.date(2026, 6, 1), compte=self.compte)   # revenu
        self._flux("-500.00", datetime.date(2026, 6, 3), self.enfant, compte=self.compte)  # dépense
        self._flux("400.00", datetime.date(2026, 6, 5), compte=self.epargne, est_transfert=True)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        juin = next(e for e in data["epargne"]["ecart_budgetaire"] if e["mois"] == "2026-06-01")
        self.assertEqual(juin["epargne_budgetaire"], Decimal("1500.00"))
        self.assertEqual(juin["versement_reel"], Decimal("400.00"))

    def test_epargne_par_compte_avec_taux(self):
        """Répartition par livret : encours, versements période, taux."""
        self._flux("300.00", datetime.date(2026, 5, 5), compte=self.epargne, est_transfert=True)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        par_compte = {c["nom"]: c for c in data["epargne"]["par_compte"]}
        self.assertEqual(set(par_compte), {"Livret A", "LDD"})
        self.assertEqual(par_compte["Livret A"]["taux_annuel"], Decimal("3.00"))
        self.assertEqual(par_compte["Livret A"]["versements_nets"], Decimal("300.00"))
        self.assertEqual(par_compte["Livret A"]["encours"], Decimal("800.00"))

    def test_epargne_ignore_comptes_non_epargne(self):
        """Un transfert vers un compte non-épargne n'est pas un versement d'épargne."""
        self._flux("300.00", datetime.date(2026, 6, 5), compte=self.compte, est_transfert=True)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        totaux = sum(v["versement_net"] for v in data["epargne"]["versements_par_mois"])
        self.assertEqual(totaux, Decimal("0.00"))

    def test_saisonnalite_yoy_de_base(self):
        """Chaque mois clôturé est comparé au même mois un an avant."""
        self._flux("-100.00", datetime.date(2025, 5, 10), self.enfant)
        self._flux("-200.00", datetime.date(2026, 5, 10), self.enfant)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        comps = data["saisonnalite"]["comparaisons"]
        mai = next(c for c in comps if c["mois"] == "2026-05-01")
        self.assertEqual(mai["depenses"], Decimal("200.00"))
        self.assertEqual(mai["depenses_an_precedent"], Decimal("100.00"))
        self.assertEqual(mai["variation_pct"], Decimal("100.0"))

    def test_saisonnalite_exclut_mois_courant(self):
        """Le mois courant (partiel) n'apparaît pas dans le YoY."""
        self._flux("-100.00", datetime.date(2025, 6, 10), self.enfant)
        self._flux("-300.00", datetime.date(2026, 6, 10), self.enfant)  # mois courant
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        mois_compares = [c["mois"] for c in data["saisonnalite"]["comparaisons"]]
        self.assertNotIn("2026-06-01", mois_compares)

    def test_saisonnalite_variation_none_sans_annee_precedente(self):
        """variation_pct = None si le même mois un an avant est à zéro."""
        self._flux("-50.00", datetime.date(2025, 4, 10), self.enfant)   # fixe le 1er mois
        self._flux("-200.00", datetime.date(2026, 5, 10), self.enfant)  # an-1 (2025-05) = 0
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        mai = next(c for c in data["saisonnalite"]["comparaisons"] if c["mois"] == "2026-05-01")
        self.assertEqual(mai["depenses_an_precedent"], Decimal("0.00"))
        self.assertIsNone(mai["variation_pct"])

    def test_saisonnalite_vide_sans_annee_complete(self):
        """Moins de 13 mois d'historique → aucune comparaison possible."""
        self._flux("-100.00", datetime.date(2026, 5, 10), self.enfant)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        self.assertEqual(data["saisonnalite"]["comparaisons"], [])

    def test_rythme_par_jour_semaine(self):
        """Les dépenses sont ventilées par jour de semaine (1=lundi)."""
        jour = datetime.date(2026, 5, 11)  # lundi
        self.assertEqual(jour.isoweekday(), 1)
        self._flux("-40.00", jour, self.enfant)
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        lundi = next(j for j in data["rythme"]["par_jour_semaine"] if j["jour"] == 1)
        self.assertEqual(lundi["total"], Decimal("40.00"))
        self.assertEqual(lundi["nb"], 1)

    def test_rythme_libelles_recurrents(self):
        """Un libellé revenant >= 2 fois est récurrent ; un unique est ignoré."""
        self._flux("-30.00", datetime.date(2026, 5, 1), self.enfant, libelle="Netflix")
        self._flux("-30.00", datetime.date(2026, 6, 1), self.enfant, libelle="netflix")
        self._flux("-10.00", datetime.date(2026, 6, 2), self.enfant, libelle="Boulangerie unique")
        data = calculer_analyse(nb_mois=3, aujourd_hui=self.AUJOURD_HUI)
        recurrents = data["rythme"]["libelles_recurrents"]
        self.assertEqual(len(recurrents), 1)
        self.assertEqual(recurrents[0]["occurrences"], 2)
        self.assertEqual(recurrents[0]["total"], Decimal("60.00"))
        self.assertEqual(recurrents[0]["moyenne"], Decimal("30.00"))


class AnalyseAPITest(_AnalyseTestMixin, TestCase):

    def test_endpoint_repond(self):
        from django.urls import reverse
        response = self.client.get(reverse("analyse"))
        self.assertEqual(response.status_code, 200)
        for bloc in ("tendances", "epargne", "titulaires", "categories", "rythme", "saisonnalite"):
            self.assertIn(bloc, response.data)

    def test_nb_mois_parametrable(self):
        from django.urls import reverse
        response = self.client.get(reverse("analyse"), {"nb_mois": 12})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["nb_mois"], 12)
        self.assertEqual(len(response.data["tendances"]["series"]), 12)


class _AbonnementsTestMixin:
    """
    Données communes aux tests de l'analyse des abonnements.

    Date de référence injectée pour le déterminisme. Fréquences avec nb_jours
    pour la normalisation ; une fréquence ponctuelle (nb_jours=None) sert à
    vérifier l'exclusion des non-récurrents.
    """

    AUJOURD_HUI = datetime.date(2026, 3, 15)  # mois comptable courant : 2026-03

    def setUp(self):
        self.type_compte = TypeCompte.objects.create(code="COURANT", libelle="Courant")
        self.pierre = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        self.marie = Titulaire.objects.create(code="MARIE", libelle="Marie")
        self.etablissement = Etablissement.objects.create(code="BNP", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="EUR", est_defaut=True
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Debit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE", libelle="Valide", est_definitif=True
        )
        self.mensuel = Frequence.objects.create(
            code="MENS", libelle="Mensuel", nb_jours=30
        )
        self.annuel = Frequence.objects.create(
            code="ANN", libelle="Annuel", nb_jours=365
        )
        self.ponctuel = Frequence.objects.create(
            code="PONCT", libelle="Ponctuel", nb_jours=None
        )
        # Catégories : une majeure avec mineure, une majeure feuille.
        self.loisirs = Categorie.objects.create(code="LOISIRS", nom="Loisirs")
        self.streaming = Categorie.objects.create(
            code="STREAM", nom="Streaming", parent=self.loisirs
        )
        self.telecoms = Categorie.objects.create(code="TEL", nom="Télécoms")
        # Comptes : perso (Pierre) + joint du foyer.
        self.compte_pierre = Compte.objects.create(
            code="CPT-0001", nom="Compte Pierre",
            type_compte=self.type_compte, titulaire=self.pierre,
            etablissement=self.etablissement, devise=self.devise,
        )
        self.compte_commun = Compte.objects.create(
            code="CPT-0002", nom="Compte joint", est_commun=True,
            type_compte=self.type_compte, titulaire=self.pierre,
            etablissement=self.etablissement, devise=self.devise,
        )

    def _abo(self, nom, montant, frequence, categorie, compte,
             actif=True, seuil=Decimal("10")):
        from abonnements.models import Abonnement
        return Abonnement.objects.create(
            nom=nom, compte=compte, categorie=categorie,
            type_flux=self.type_flux, frequence=frequence,
            montant_attendu=Decimal(str(montant)),
            seuil_divergence_pct=seuil,
            date_debut=datetime.date(2026, 1, 1), actif=actif,
        )

    def _flux(self, montant, date_flux, categorie=None, compte=None,
              abonnement=None, libelle="Flux"):
        return Flux.objects.create(
            compte=compte or self.compte_pierre,
            categorie=categorie, type_flux=self.type_flux, statut=self.statut,
            devise=self.devise, montant=Decimal(str(montant)),
            date_flux=date_flux, libelle=libelle, abonnement=abonnement,
        )

    def _calculer(self, nb_mois=6):
        from analytics.services.abonnements import calculer_abonnements
        return calculer_abonnements(nb_mois=nb_mois, aujourd_hui=self.AUJOURD_HUI)


class AbonnementsServiceTest(_AbonnementsTestMixin, TestCase):

    def test_synthese_totaux(self):
        """Coûts normalisés au mois et à l'année, sommés sur les actifs."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        self._abo("Assurance", "-240.00", self.annuel, self.telecoms, self.compte_commun)
        synthese = self._calculer()["synthese"]

        # Netflix : 15.99 × 30.4375 / 30 = 16.22 ; Assurance : 240 × 30.4375 / 365 = 20.01
        self.assertEqual(synthese["nb_actifs"], 2)
        self.assertEqual(synthese["nb_recurrents"], 2)
        self.assertEqual(synthese["total_mensuel"], Decimal("36.23"))
        # Annuel : 194.68 + 240.16 = 434.84
        self.assertEqual(synthese["total_annuel"], Decimal("434.84"))

    def test_poids_sur_depenses_reelles(self):
        """Le poids rapporte le total mensuel aux dépenses réelles moyennes."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        # 600 € de dépenses réelles sur le mois courant → moyenne 100 €/mois sur 6 mois.
        self._flux("-600.00", datetime.date(2026, 3, 5), categorie=self.streaming)
        synthese = self._calculer()["synthese"]

        self.assertEqual(synthese["depenses_mensuelles_moy"], Decimal("100.00"))
        # 16.22 / 100 × 100 = 16.2 %
        self.assertEqual(synthese["poids_depenses_pct"], Decimal("16.2"))

    def test_revenus_recurrents_exclus(self):
        """Un abonnement de revenu (montant positif) n'entre pas dans les coûts."""
        self._abo("Salaire", "2800.00", self.mensuel, None, self.compte_pierre)
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        synthese = self._calculer()["synthese"]

        self.assertEqual(synthese["nb_actifs"], 1)

    def test_ponctuel_exclu_des_totaux(self):
        """Une fréquence sans nb_jours n'est pas normalisable → hors totaux."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        self._abo("Achat unique", "-50.00", self.ponctuel, self.telecoms, self.compte_pierre)
        synthese = self._calculer()["synthese"]

        self.assertEqual(synthese["nb_actifs"], 2)
        self.assertEqual(synthese["nb_recurrents"], 1)
        self.assertEqual(synthese["total_mensuel"], Decimal("16.22"))

    def test_inactif_exclu(self):
        """Un abonnement inactif n'est pas compté."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming,
                  self.compte_pierre, actif=False)
        synthese = self._calculer()["synthese"]

        self.assertEqual(synthese["nb_actifs"], 0)
        self.assertEqual(synthese["total_mensuel"], Decimal("0.00"))

    def test_par_categorie_regroupe_sous_parent(self):
        """La mineure Streaming est regroupée sous sa majeure Loisirs."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        self._abo("Spotify", "-9.99", self.mensuel, self.streaming, self.compte_pierre)
        par_cat = self._calculer()["par_categorie"]["par_categorie"]

        self.assertEqual(len(par_cat), 1)
        self.assertEqual(par_cat[0]["nom"], "Loisirs")
        self.assertEqual(par_cat[0]["nb"], 2)
        self.assertEqual(par_cat[0]["part_pct"], Decimal("100.0"))

    def test_par_categorie_sans_categorie(self):
        """Un abonnement sans catégorie tombe dans le bucket « Sans catégorie »."""
        self._abo("Mystère", "-12.00", self.mensuel, None, self.compte_pierre)
        par_cat = self._calculer()["par_categorie"]["par_categorie"]

        self.assertEqual(par_cat[0]["id"], "sans")
        self.assertEqual(par_cat[0]["nom"], "Sans catégorie")

    def test_par_titulaire_commun_separe(self):
        """Le compte joint forme un bucket « Commun », jamais rattaché à Pierre."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        self._abo("Assurance", "-240.00", self.annuel, self.telecoms, self.compte_commun)
        buckets = self._calculer()["par_titulaire"]["par_titulaire"]

        noms = {b["nom"]: b for b in buckets}
        self.assertIn("Pierre", noms)
        self.assertIn("Commun", noms)
        self.assertTrue(noms["Commun"]["est_commun"])
        self.assertFalse(noms["Pierre"]["est_commun"])
        self.assertEqual(noms["Pierre"]["nb"], 1)

    def test_par_titulaire_detail_abonnements(self):
        """Chaque bucket embarque le détail de ses abonnements (pour le modal)."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        self._abo("Spotify", "-9.99", self.mensuel, self.streaming, self.compte_pierre)
        buckets = self._calculer()["par_titulaire"]["par_titulaire"]

        pierre = next(b for b in buckets if b["nom"] == "Pierre")
        self.assertEqual(len(pierre["abonnements"]), 2)
        # Trié par coût mensuel décroissant → Netflix avant Spotify.
        self.assertEqual(pierre["abonnements"][0]["nom"], "Netflix")
        detail = pierre["abonnements"][0]
        self.assertEqual(detail["categorie_nom"], "Streaming")
        self.assertEqual(detail["compte_nom"], "Compte Pierre")
        self.assertFalse(detail["compte_est_commun"])

    def test_derive_prix_divergence(self):
        """Un dernier prélèvement au-delà du seuil est marqué en divergence."""
        abo = self._abo("Netflix", "-15.99", self.mensuel, self.streaming,
                        self.compte_pierre, seuil=Decimal("10"))
        self._flux("-20.00", datetime.date(2026, 3, 3),
                   categorie=self.streaming, abonnement=abo)
        par_abo = self._calculer()["derive_prix"]["par_abonnement"]

        self.assertEqual(len(par_abo), 1)
        # (20 - 15.99) / 15.99 × 100 = 25.1 %
        self.assertEqual(par_abo[0]["ecart_pct"], Decimal("25.1"))
        self.assertTrue(par_abo[0]["en_divergence"])

    def test_derive_prix_sans_flux_absent(self):
        """Un abonnement sans flux réel n'apparaît pas dans la dérive."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        par_abo = self._calculer()["derive_prix"]["par_abonnement"]

        self.assertEqual(par_abo, [])

    def test_a_risque_jamais_genere(self):
        """Un abonnement actif sans aucun flux est signalé « jamais_genere »."""
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        a_risque = self._calculer()["a_risque"]["a_risque"]

        self.assertEqual(len(a_risque), 1)
        self.assertIn("jamais_genere", a_risque[0]["raisons"])

    def test_a_risque_en_retard(self):
        """Un abonnement non prélevé depuis plus d'un cycle est « en_retard »."""
        abo = self._abo("Netflix", "-15.99", self.mensuel, self.streaming,
                        self.compte_pierre)
        # Dernier flux il y a plus de 30 jours (le signal pose derniere_occurrence).
        self._flux("-15.99", datetime.date(2026, 1, 10),
                   categorie=self.streaming, abonnement=abo)
        a_risque = self._calculer()["a_risque"]["a_risque"]

        motifs = a_risque[0]["raisons"]
        self.assertIn("en_retard", motifs)
        self.assertNotIn("jamais_genere", motifs)


class AbonnementsAnalyseAPITest(_AbonnementsTestMixin, TestCase):

    def test_endpoint_repond(self):
        from django.urls import reverse
        self._abo("Netflix", "-15.99", self.mensuel, self.streaming, self.compte_pierre)
        response = self.client.get(reverse("abonnements-analyse"))
        self.assertEqual(response.status_code, 200)
        for bloc in ("synthese", "par_categorie", "par_titulaire",
                     "derive_prix", "a_risque"):
            self.assertIn(bloc, response.data)

    def test_nb_mois_parametrable(self):
        from django.urls import reverse
        response = self.client.get(reverse("abonnements-analyse"), {"nb_mois": 12})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["nb_mois"], 12)
