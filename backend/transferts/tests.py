import datetime
from decimal import Decimal
from django.test import TestCase

from referentiels.models import (
    TypeFlux, StatutFlux, Devise, TypeCompte, Etablissement, Titulaire
)
from comptes.models import Compte
from flux.models import Flux
from transferts.models import Transfert
from transferts.services import creer_transfert
from core.tests_base import APIAuthTestCase


class TransfertServiceTest(TestCase):

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
        self.type_flux_debit = TypeFlux.objects.create(
            code="DEBIT", libelle="Débit"
        )
        self.type_flux_credit = TypeFlux.objects.create(
            code="CREDIT", libelle="Crédit"
        )
        self.statut = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True
        )
        self.compte_source = Compte.objects.create(
            code="CPT-SRC",
            nom="Compte source",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
            solde_initial=Decimal("2000.00"),
            solde_reel=Decimal("2000.00"),
        )
        self.compte_destination = Compte.objects.create(
            code="CPT-DST",
            nom="Compte destination",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
            solde_initial=Decimal("500.00"),
            solde_reel=Decimal("500.00"),
        )

    def _creer(self, montant="300.00"):
        return creer_transfert(
            compte_source=self.compte_source,
            compte_destination=self.compte_destination,
            montant=Decimal(montant),
            date_flux=datetime.date(2024, 3, 15),
            type_flux_debit=self.type_flux_debit,
            type_flux_credit=self.type_flux_credit,
            statut=self.statut,
            devise=self.devise,
        )

    def test_creation_transfert(self):
        """Un transfert crée bien deux flux liés."""
        transfert = self._creer("300.00")
        self.assertIsInstance(transfert, Transfert)
        self.assertEqual(transfert.montant, Decimal("300.00"))

    def test_flux_debit_negatif(self):
        """Le flux débit est toujours négatif."""
        transfert = self._creer("300.00")
        self.assertEqual(transfert.flux_debit.montant, Decimal("-300.00"))

    def test_flux_credit_positif(self):
        """Le flux crédit est toujours positif."""
        transfert = self._creer("300.00")
        self.assertEqual(transfert.flux_credit.montant, Decimal("300.00"))

    def test_flux_marqués_est_transfert(self):
        """Les deux flux ont est_transfert=True."""
        transfert = self._creer("300.00")
        self.assertTrue(transfert.flux_debit.est_transfert)
        self.assertTrue(transfert.flux_credit.est_transfert)

    def test_soldes_recalcules_apres_transfert(self):
        """Les soldes théoriques des deux comptes sont recalculés."""
        self._creer("300.00")
        self.compte_source.refresh_from_db()
        self.compte_destination.refresh_from_db()
        self.assertEqual(self.compte_source.solde_theorique, Decimal("1700.00"))
        self.assertEqual(self.compte_destination.solde_theorique, Decimal("800.00"))

    def test_erreur_source_egale_destination(self):
        """Impossible de transférer vers le même compte."""
        with self.assertRaises(ValueError):
            creer_transfert(
                compte_source=self.compte_source,
                compte_destination=self.compte_source,
                montant=Decimal("100.00"),
                date_flux=datetime.date(2024, 3, 15),
                type_flux_debit=self.type_flux_debit,
                type_flux_credit=self.type_flux_credit,
                statut=self.statut,
                devise=self.devise,
            )

    def test_erreur_montant_negatif(self):
        """Le montant d'un transfert doit être strictement positif."""
        with self.assertRaises(ValueError):
            self._creer("-100.00")

    def test_erreur_montant_zero(self):
        """Le montant nul est refusé."""
        with self.assertRaises(ValueError):
            self._creer("0.00")

    def test_soft_delete_transfert(self):
        """Soft delete du transfert → soft delete des deux flux → soldes recalculés."""
        transfert = self._creer("300.00")
        self.compte_source.refresh_from_db()
        self.assertEqual(self.compte_source.solde_theorique, Decimal("1700.00"))

        transfert.delete()

        self.compte_source.refresh_from_db()
        self.compte_destination.refresh_from_db()
        self.assertEqual(self.compte_source.solde_theorique, Decimal("2000.00"))
        self.assertEqual(self.compte_destination.solde_theorique, Decimal("500.00"))

        # Les deux flux sont soft-deletés
        self.assertFalse(Flux.objects.filter(id=transfert.flux_debit.id).exists())
        self.assertFalse(Flux.objects.filter(id=transfert.flux_credit.id).exists())


class TransfertFiltresAPITest(APIAuthTestCase):
    """Filtres et tri de la liste des transferts (volet lisibilité)."""

    def setUp(self):
        base = TransfertServiceTest.setUp
        base(self)  # réutilise le décor (comptes, référentiels)
        # Un 3e compte pour croiser les filtres source/destination.
        self.compte_c = Compte.objects.create(
            code="CPT-C", nom="Livret", type_compte=self.type_compte,
            titulaire=self.titulaire, etablissement=self.etablissement,
            devise=self.devise, solde_initial=Decimal("0.00"), solde_reel=Decimal("0.00"),
        )

    def _creer(self, src, dst, montant, date):
        return creer_transfert(
            compte_source=src, compte_destination=dst, montant=Decimal(montant),
            date_flux=date, type_flux_debit=self.type_flux_debit,
            type_flux_credit=self.type_flux_credit, statut=self.statut, devise=self.devise,
        )

    def test_filtre_compte_source(self):
        self._creer(self.compte_source, self.compte_destination, "100.00", datetime.date(2026, 6, 10))
        self._creer(self.compte_destination, self.compte_c, "50.00", datetime.date(2026, 6, 12))
        res = self.client.get("/api/v1/transferts/", {"compte_source": str(self.compte_source.id)})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)

    def test_filtre_compte_les_deux_cotes(self):
        """`compte` matche source OU destination."""
        self._creer(self.compte_source, self.compte_destination, "100.00", datetime.date(2026, 6, 10))
        self._creer(self.compte_destination, self.compte_c, "50.00", datetime.date(2026, 6, 12))
        res = self.client.get("/api/v1/transferts/", {"compte": str(self.compte_destination.id)})
        self.assertEqual(res.data["count"], 2)

    def test_filtre_plage_dates(self):
        self._creer(self.compte_source, self.compte_destination, "100.00", datetime.date(2026, 5, 1))
        self._creer(self.compte_source, self.compte_destination, "100.00", datetime.date(2026, 6, 20))
        res = self.client.get(
            "/api/v1/transferts/", {"date_min": "2026-06-01", "date_max": "2026-06-30"}
        )
        self.assertEqual(res.data["count"], 1)

    def test_serializer_expose_ids_et_etablissement(self):
        self._creer(self.compte_source, self.compte_destination, "100.00", datetime.date(2026, 6, 10))
        res = self.client.get("/api/v1/transferts/")
        ligne = res.data["results"][0]
        self.assertEqual(ligne["compte_source_id"], str(self.compte_source.id))
        self.assertEqual(ligne["compte_destination_id"], str(self.compte_destination.id))
        self.assertEqual(ligne["compte_source_etablissement"], "BoursoBank")
        self.assertTrue(ligne["est_definitif"])


class AnalyseTransfertsTest(APIAuthTestCase):
    """Agrégation du graphe nœud-lien des transferts (analytics)."""

    def setUp(self):
        TransfertServiceTest.setUp(self)
        self.compte_c = Compte.objects.create(
            code="CPT-C", nom="Livret", type_compte=self.type_compte,
            titulaire=self.titulaire, etablissement=self.etablissement,
            devise=self.devise, solde_initial=Decimal("0.00"), solde_reel=Decimal("0.00"),
            est_epargne=True,
        )
        self.aujourd_hui = datetime.date(2026, 6, 20)

    def _creer(self, src, dst, montant, date):
        return creer_transfert(
            compte_source=src, compte_destination=dst, montant=Decimal(montant),
            date_flux=date, type_flux_debit=self.type_flux_debit,
            type_flux_credit=self.type_flux_credit, statut=self.statut, devise=self.devise,
        )

    def test_liens_agreges_par_paire(self):
        from analytics.services.transferts import calculer_transferts
        self._creer(self.compte_source, self.compte_c, "100.00", datetime.date(2026, 6, 1))
        self._creer(self.compte_source, self.compte_c, "50.00", datetime.date(2026, 6, 5))
        self._creer(self.compte_destination, self.compte_c, "30.00", datetime.date(2026, 6, 8))
        d = calculer_transferts(nb_mois=6, aujourd_hui=self.aujourd_hui)
        liens = {(l["source"], l["destination"]): l for l in d["liens"]}
        cle = (str(self.compte_source.id), str(self.compte_c.id))
        self.assertEqual(liens[cle]["total"], Decimal("150.00"))
        self.assertEqual(liens[cle]["nb"], 2)
        self.assertEqual(len(d["liens"]), 2)

    def test_noeuds_entrant_sortant(self):
        from analytics.services.transferts import calculer_transferts
        self._creer(self.compte_source, self.compte_c, "100.00", datetime.date(2026, 6, 1))
        self._creer(self.compte_source, self.compte_destination, "40.00", datetime.date(2026, 6, 5))
        d = calculer_transferts(nb_mois=6, aujourd_hui=self.aujourd_hui)
        noeuds = {n["id"]: n for n in d["noeuds"]}
        src = noeuds[str(self.compte_source.id)]
        self.assertEqual(src["sortant"], Decimal("140.00"))
        self.assertEqual(src["entrant"], Decimal("0.00"))
        self.assertEqual(src["solde_net"], Decimal("-140.00"))
        livret = noeuds[str(self.compte_c.id)]
        self.assertEqual(livret["entrant"], Decimal("100.00"))
        self.assertTrue(livret["est_epargne"])

    def test_synthese_et_par_mois(self):
        from analytics.services.transferts import calculer_transferts
        self._creer(self.compte_source, self.compte_c, "100.00", datetime.date(2026, 5, 10))
        self._creer(self.compte_source, self.compte_c, "60.00", datetime.date(2026, 6, 10))
        d = calculer_transferts(nb_mois=6, aujourd_hui=self.aujourd_hui)
        self.assertEqual(d["synthese"]["total"], Decimal("160.00"))
        self.assertEqual(d["synthese"]["nb"], 2)
        par_mois = {m["mois"]: m for m in d["par_mois"]}
        self.assertEqual(par_mois["2026-05-01"]["total"], Decimal("100.00"))
        self.assertEqual(par_mois["2026-06-01"]["total"], Decimal("60.00"))
        self.assertEqual(len(d["par_mois"]), 6)

    def test_hors_fenetre_exclus(self):
        from analytics.services.transferts import calculer_transferts
        # Janvier hors fenêtre de 3 mois (avril-juin).
        self._creer(self.compte_source, self.compte_c, "999.00", datetime.date(2026, 1, 10))
        d = calculer_transferts(nb_mois=3, aujourd_hui=self.aujourd_hui)
        self.assertEqual(d["synthese"]["total"], Decimal("0.00"))
        self.assertEqual(d["liens"], [])

    def test_api_endpoint(self):
        self._creer(self.compte_source, self.compte_c, "100.00", datetime.date(2026, 6, 1))
        res = self.client.get("/api/v1/analytics/transferts/", {"nb_mois": 6})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["fiabilite"], "reelle")
        self.assertIn("liens", res.data)
        self.assertIn("noeuds", res.data)
