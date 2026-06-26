from django.test import TestCase
from django.db.utils import IntegrityError
from referentiels.models import (
    TypeCompte, Devise, StatutFlux, Frequence
)


class ReferentielBaseTest(TestCase):

    def test_str(self):
        tc = TypeCompte.objects.create(code="COURANT", libelle="Compte courant")
        self.assertEqual(str(tc), "COURANT — Compte courant")

    def test_code_unique(self):
        TypeCompte.objects.create(code="COURANT", libelle="Compte courant")
        with self.assertRaises(IntegrityError):
            TypeCompte.objects.create(code="COURANT", libelle="Doublon")

    def test_soft_delete(self):
        tc = TypeCompte.objects.create(code="EPARGNE", libelle="Épargne")
        tc.delete()
        # N'apparaît plus dans le manager par défaut
        self.assertFalse(TypeCompte.objects.filter(code="EPARGNE").exists())
        # Mais existe toujours en base
        self.assertTrue(TypeCompte.objects.all_with_deleted().filter(code="EPARGNE").exists())

    def test_restore(self):
        tc = TypeCompte.objects.create(code="PEA", libelle="PEA")
        tc.delete()
        tc.restore()
        self.assertTrue(TypeCompte.objects.filter(code="PEA").exists())


class DeviseTest(TestCase):

    def test_devise_avec_symbole(self):
        eur = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True
        )
        self.assertEqual(eur.symbole, "€")
        self.assertTrue(eur.est_defaut)


class StatutFluxTest(TestCase):

    def test_statut_definitif(self):
        s = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True
        )
        self.assertTrue(s.est_definitif)


class FrequenceTest(TestCase):

    def test_frequence_mensuelle(self):
        f = Frequence.objects.create(
            code="MENSUEL", libelle="Mensuel", nb_jours=30
        )
        self.assertEqual(f.nb_jours, 30)

    def test_frequence_ponctuelle(self):
        f = Frequence.objects.create(
            code="PONCTUEL", libelle="Ponctuel", nb_jours=None
        )
        self.assertIsNone(f.nb_jours)

class ParametresBudgetAPITest(TestCase):
    """Endpoint singleton + remap automatique des flux au changement de jour."""

    def setUp(self):
        import datetime
        from decimal import Decimal
        from rest_framework.test import APIClient
        from referentiels.models import (
            Titulaire, Etablissement, TypeFlux, StatutFlux as SF,
        )
        from comptes.models import Compte
        from categories.models import Categorie
        from flux.models import Flux

        self.client = APIClient()
        self.url = "/api/v1/referentiels/parametres-budget/"

        tc = TypeCompte.objects.create(code="COURANT", libelle="Compte courant")
        tit = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        eta = Etablissement.objects.create(code="BOURSO", libelle="BoursoBank")
        dev = Devise.objects.create(code="EUR", libelle="Euro", symbole="€", est_defaut=True)
        tf = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        st = SF.objects.create(code="VALIDE", libelle="Validé", est_definitif=True)
        cat = Categorie.objects.create(code="ALIM", nom="Alimentation")
        compte = Compte.objects.create(
            code="CPT-1", nom="Principal", type_compte=tc, titulaire=tit,
            etablissement=eta, devise=dev,
            solde_initial=Decimal("0.00"), solde_reel=Decimal("0.00"),
        )
        self.flux = Flux.objects.create(
            compte=compte, type_flux=tf, statut=st, devise=dev, categorie=cat,
            montant=Decimal("-50.00"), date_flux=datetime.date(2026, 6, 27),
        )

    def test_get_renvoie_defaut(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["jour_debut_mois_comptable"], 1)

    def test_patch_invalide_rejete(self):
        res = self.client.patch(self.url, {"jour_debut_mois_comptable": 99}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_patch_remappe_les_flux(self):
        import datetime

        # Flux du 27 juin : mois calendaire = juin (jour défaut 1).
        self.assertEqual(self.flux.mois, datetime.date(2026, 6, 1))
        res = self.client.patch(self.url, {"jour_debut_mois_comptable": 25}, format="json")
        self.assertEqual(res.status_code, 200)
        # Le PATCH a déclenché le remap : 27 juin bascule sur juillet.
        self.flux.refresh_from_db()
        self.assertEqual(self.flux.mois, datetime.date(2026, 7, 1))
