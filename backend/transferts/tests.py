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