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