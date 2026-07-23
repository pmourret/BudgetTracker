import datetime
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from referentiels.models import (
    TypeFlux, Titulaire, ModePaiement, StatutFlux, Devise,
    TypeCompte, Etablissement
)
from comptes.models import Compte
from categories.models import Categorie
from flux.models import Flux


class FluxModelTest(TestCase):

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
        self.type_flux = TypeFlux.objects.create(
            code="DEBIT", libelle="Débit"
        )
        self.statut = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True
        )
        self.categorie = Categorie.objects.create(
            code="ALIMENTATION", nom="Alimentation"
        )
        self.compte = Compte.objects.create(
            code="CPT-0001",
            nom="Compte principal",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
            solde_initial=Decimal("4196.49"),
            solde_reel=Decimal("4196.49"),
        )

    def _make_flux(self, montant, date_flux=None, **kwargs):
        return Flux.objects.create(
            compte=self.compte,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            categorie=self.categorie,
            montant=Decimal(str(montant)),
            date_flux=date_flux or datetime.date(2024, 3, 15),
            **kwargs
        )

    def test_mois_calcule_automatiquement(self):
        """Le champ mois est toujours le 1er du mois de date_flux."""
        flux = self._make_flux("-215.00", date_flux=datetime.date(2024, 3, 15))
        self.assertEqual(flux.mois, datetime.date(2024, 3, 1))

    def test_mois_recalcule_si_date_change(self):
        """Mois mis à jour si date_flux change."""
        flux = self._make_flux("-215.00", date_flux=datetime.date(2024, 3, 15))
        flux.date_flux = datetime.date(2024, 6, 20)
        flux.save()
        self.assertEqual(flux.mois, datetime.date(2024, 6, 1))

    def test_montant_negatif_depense(self):
        flux = self._make_flux("-215.00")
        self.assertLess(flux.montant, 0)

    def test_montant_positif_recette(self):
        flux = self._make_flux("2500.00")
        self.assertGreater(flux.montant, 0)

    def test_est_transfert_defaut_false(self):
        flux = self._make_flux("-50.00")
        self.assertFalse(flux.est_transfert)

    def test_str_depense(self):
        flux = self._make_flux("-215.00", libelle="Courses Leclerc")
        self.assertIn("-215.00", str(flux))
        self.assertIn("Courses Leclerc", str(flux))

    def test_str_recette(self):
        flux = self._make_flux("2500.00", libelle="Salaire")
        self.assertIn("+", str(flux))
        self.assertIn("Salaire", str(flux))

    def test_soft_delete(self):
        flux = self._make_flux("-100.00")
        flux_id = flux.id
        flux.delete()
        self.assertFalse(Flux.objects.filter(id=flux_id).exists())
        self.assertTrue(Flux.objects.all_with_deleted().filter(id=flux_id).exists())

from comptes.services.solde import calculer_solde


class SignalRecalculSoldeTest(TestCase):
    """
    Vérifie que le signal déclenche bien le recalcul du solde
    après chaque opération sur un Flux.
    """

    def setUp(self):
        # Réutilise le même setUp que FluxModelTest
        self.type_compte = TypeCompte.objects.create(
            code="COURANT2", libelle="Compte courant"
        )
        self.titulaire = Titulaire.objects.create(
            code="PIERRE2", libelle="Pierre"
        )
        self.etablissement = Etablissement.objects.create(
            code="BOURSOBANK2", libelle="BoursoBank"
        )
        self.devise = Devise.objects.create(
            code="EUR2", libelle="Euro", symbole="€", est_defaut=False
        )
        self.type_flux = TypeFlux.objects.create(
            code="DEBIT2", libelle="Débit"
        )
        self.statut = StatutFlux.objects.create(
            code="VALIDE2", libelle="Validé", est_definitif=True
        )
        self.categorie = Categorie.objects.create(
            code="TRANSPORT2", nom="Transport"
        )
        self.compte = Compte.objects.create(
            code="CPT-0002",
            nom="Compte signal test",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("1000.00"),
        )

    def _make_flux(self, montant, date_flux=None):
        return Flux.objects.create(
            compte=self.compte,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            categorie=self.categorie,
            montant=Decimal(str(montant)),
            date_flux=date_flux or datetime.date(2024, 3, 15),
        )

    def test_solde_recalcule_apres_creation(self):
        """Création d'un flux → solde_theorique mis à jour."""
        self._make_flux("-200.00")
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_theorique, Decimal("800.00"))

    def test_solde_recalcule_apres_plusieurs_flux(self):
        """Plusieurs flux → solde_theorique cumulé correctement."""
        self._make_flux("-200.00")
        self._make_flux("-150.00")
        self._make_flux("500.00")
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_theorique, Decimal("1150.00"))

    def test_solde_recalcule_apres_soft_delete(self):
        """Soft delete d'un flux → solde_theorique recalculé sans ce flux."""
        flux = self._make_flux("-300.00")
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_theorique, Decimal("700.00"))

        flux.delete()
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_theorique, Decimal("1000.00"))

    def test_ecart_solde_recalcule(self):
        """L'écart de solde est recalculé après un flux prévisionnel."""
        from referentiels.models import StatutFlux
        statut_prev = StatutFlux.objects.create(
            code="PREV_TEST", libelle="Prévisionnel", est_definitif=False
        )
        Flux.objects.create(
            compte=self.compte,
            type_flux=self.type_flux,
            statut=statut_prev,
            devise=self.devise,
            categorie=self.categorie,
            montant=Decimal("-100.00"),
            date_flux=datetime.date(2024, 3, 15),
        )
        self.compte.refresh_from_db()
        # solde_reel=1000 (flux non définitif ignoré), solde_theorique=900 → ecart=100
        self.assertEqual(self.compte.ecart_solde, Decimal("100.00"))

    def test_solde_recalcule_apres_modification(self):
        """Modification du montant d'un flux → solde_theorique recalculé."""
        flux = self._make_flux("-100.00")
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_theorique, Decimal("900.00"))

        flux.montant = Decimal("-250.00")
        flux.save()
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_theorique, Decimal("750.00"))

from rest_framework.test import APITestCase
from django.urls import reverse


class FluxAPITest(APITestCase):

    def setUp(self):
        self.type_compte = TypeCompte.objects.create(
            code="COURANT3", libelle="Compte courant"
        )
        self.titulaire = Titulaire.objects.create(
            code="PIERRE3", libelle="Pierre"
        )
        self.etablissement = Etablissement.objects.create(
            code="BOURSOBANK3", libelle="BoursoBank"
        )
        self.devise = Devise.objects.create(
            code="EUR3", libelle="Euro", symbole="€", est_defaut=False
        )
        self.type_flux = TypeFlux.objects.create(
            code="DEBIT3", libelle="Débit"
        )
        self.statut = StatutFlux.objects.create(
            code="VALIDE3", libelle="Validé", est_definitif=True
        )
        self.categorie = Categorie.objects.create(
            code="LOISIRS3", nom="Loisirs"
        )
        self.compte = Compte.objects.create(
            code="CPT-0003",
            nom="Compte API test",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("1000.00"),
        )
        self.payload_valide = {
            "compte": str(self.compte.id),
            "categorie": str(self.categorie.id),
            "type_flux": str(self.type_flux.id),
            "statut": str(self.statut.id),
            "devise": str(self.devise.id),
            "montant": "-150.00",
            "date_flux": "2024-03-15",
            "libelle": "Test achat",
        }

    def test_creation_flux(self):
        response = self.client.post(
            reverse("flux-list"), self.payload_valide, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["mois"], "2024-03-01")

    def test_mois_calcule_automatiquement(self):
        """Le mois est toujours le 1er du mois de date_flux."""
        response = self.client.post(
            reverse("flux-list"), self.payload_valide, format="json"
        )
        self.assertEqual(response.data["mois"], "2024-03-01")

    def test_montant_zero_refuse(self):
        payload = {**self.payload_valide, "montant": "0.00"}
        response = self.client.post(
            reverse("flux-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_categorie_obligatoire_si_non_transfert(self):
        payload = {**self.payload_valide, "categorie": None}
        response = self.client.post(
            reverse("flux-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_solde_mis_a_jour_apres_creation(self):
        self.client.post(reverse("flux-list"), self.payload_valide, format="json")
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_theorique, Decimal("850.00"))

    def test_soft_delete_flux(self):
        create = self.client.post(
            reverse("flux-list"), self.payload_valide, format="json"
        )
        flux_id = create.data["id"]
        response = self.client.delete(reverse("flux-detail", args=[flux_id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_theorique, Decimal("1000.00"))

    def test_filtre_par_compte(self):
        self.client.post(reverse("flux-list"), self.payload_valide, format="json")
        response = self.client.get(
            reverse("flux-list"), {"compte": str(self.compte.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class FluxRechercheFiltresAPITest(APITestCase):
    """Filtres de recherche de la FluxPage : libellé, propriétaire du compte,
    statut (prévisionnel/validé), sens (montant)."""

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="COURANT6", libelle="Courant")
        self.titA = Titulaire.objects.create(code="ALICE6", libelle="Alice")
        self.titB = Titulaire.objects.create(code="BOB6", libelle="Bob")
        etab = Etablissement.objects.create(code="BNP6", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR6", libelle="Euro", symbole="€", est_defaut=True
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT6", libelle="Débit")
        self.statut_valide = StatutFlux.objects.create(
            code="VAL6", libelle="Validé", est_definitif=True
        )
        self.statut_prev = StatutFlux.objects.create(
            code="PREV6", libelle="Prévisionnel", est_definitif=False
        )
        self.categorie = Categorie.objects.create(code="CAT6", nom="Courses")
        self.compte_a = Compte.objects.create(
            code="CPT-A6", nom="Compte Alice", type_compte=type_compte,
            titulaire=self.titA, etablissement=etab, devise=self.devise,
            solde_initial=Decimal("0.00"),
        )
        self.compte_b = Compte.objects.create(
            code="CPT-B6", nom="Compte Bob", type_compte=type_compte,
            titulaire=self.titB, etablissement=etab, devise=self.devise,
            solde_initial=Decimal("0.00"),
        )

    def _make(self, compte, statut, montant, libelle):
        return Flux.objects.create(
            compte=compte, categorie=self.categorie, type_flux=self.type_flux,
            statut=statut, devise=self.devise, montant=Decimal(montant),
            date_flux=datetime.date(2024, 3, 15), libelle=libelle,
        )

    def test_recherche_par_libelle(self):
        self._make(self.compte_a, self.statut_valide, "-50.00", "Boulangerie")
        self._make(self.compte_a, self.statut_valide, "-30.00", "Essence")
        r = self.client.get(reverse("flux-list"), {"search": "boulang"})
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["libelle"], "Boulangerie")

    def test_filtre_par_titulaire_compte(self):
        self._make(self.compte_a, self.statut_valide, "-50.00", "A")
        self._make(self.compte_b, self.statut_valide, "-30.00", "B")
        r = self.client.get(
            reverse("flux-list"), {"titulaire_compte": str(self.titA.id)}
        )
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["libelle"], "A")

    def test_filtre_est_definitif(self):
        self._make(self.compte_a, self.statut_valide, "-50.00", "Validé")
        self._make(self.compte_a, self.statut_prev, "-30.00", "Prévu")
        r_val = self.client.get(reverse("flux-list"), {"est_definitif": "true"})
        r_prev = self.client.get(reverse("flux-list"), {"est_definitif": "false"})
        self.assertEqual(r_val.data["count"], 1)
        self.assertEqual(r_val.data["results"][0]["libelle"], "Validé")
        self.assertEqual(r_prev.data["count"], 1)
        self.assertEqual(r_prev.data["results"][0]["libelle"], "Prévu")

    def test_filtre_sens_depense_recette(self):
        self._make(self.compte_a, self.statut_valide, "-50.00", "Dépense")
        self._make(self.compte_a, self.statut_valide, "1200.00", "Recette")
        r_dep = self.client.get(reverse("flux-list"), {"montant_max": "-0.01"})
        r_rec = self.client.get(reverse("flux-list"), {"montant_min": "0.01"})
        self.assertEqual(r_dep.data["count"], 1)
        self.assertEqual(r_dep.data["results"][0]["libelle"], "Dépense")
        self.assertEqual(r_rec.data["count"], 1)
        self.assertEqual(r_rec.data["results"][0]["libelle"], "Recette")

class FluxChangementRecalculTest(APITestCase):
    """
    Régression : quand un flux change de compte, de catégorie ou de mois,
    l'ANCIEN compte et les ANCIENS budgets doivent aussi être recalculés.
    """

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="COURANT4", libelle="Courant")
        titulaire = Titulaire.objects.create(code="PIERRE4", libelle="Pierre")
        etablissement = Etablissement.objects.create(code="BNP4", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR4", libelle="Euro", symbole="€", est_defaut=False
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT4", libelle="Débit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE4", libelle="Validé", est_definitif=True
        )
        self.compte1 = Compte.objects.create(
            code="CPT-CH01", nom="Compte 1",
            type_compte=type_compte, titulaire=titulaire,
            etablissement=etablissement, devise=self.devise,
            solde_initial=Decimal("1000.00"),
        )
        self.compte2 = Compte.objects.create(
            code="CPT-CH02", nom="Compte 2",
            type_compte=type_compte, titulaire=titulaire,
            etablissement=etablissement, devise=self.devise,
            solde_initial=Decimal("500.00"),
        )
        self.cat1 = Categorie.objects.create(code="CAT_CH1", nom="Courses CH")
        self.cat2 = Categorie.objects.create(code="CAT_CH2", nom="Loisirs CH")

        from budgets.models import Budget
        self.budget_cat1_mars = Budget.objects.create(
            categorie=self.cat1, mois=datetime.date(2024, 3, 1),
            montant_prevu=Decimal("400.00"),
        )
        self.budget_cat2_mars = Budget.objects.create(
            categorie=self.cat2, mois=datetime.date(2024, 3, 1),
            montant_prevu=Decimal("400.00"),
        )
        self.budget_cat1_avril = Budget.objects.create(
            categorie=self.cat1, mois=datetime.date(2024, 4, 1),
            montant_prevu=Decimal("400.00"),
        )
        self.flux = Flux.objects.create(
            compte=self.compte1,
            categorie=self.cat1,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal("-100.00"),
            date_flux=datetime.date(2024, 3, 15),
        )

    def test_changement_compte_recalcule_ancien_compte(self):
        """Déplacer un flux vers un autre compte recalcule les deux soldes."""
        self.compte1.refresh_from_db()
        self.assertEqual(self.compte1.solde_theorique, Decimal("900.00"))

        response = self.client.patch(
            reverse("flux-detail", args=[self.flux.id]),
            {"compte": str(self.compte2.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.compte1.refresh_from_db()
        self.compte2.refresh_from_db()
        self.assertEqual(self.compte1.solde_theorique, Decimal("1000.00"))
        self.assertEqual(self.compte2.solde_theorique, Decimal("400.00"))

    def test_changement_categorie_recalcule_ancien_budget(self):
        """Déplacer un flux vers une autre catégorie recalcule les deux budgets."""
        self.budget_cat1_mars.refresh_from_db()
        self.assertEqual(self.budget_cat1_mars.montant_consomme, Decimal("100.00"))

        response = self.client.patch(
            reverse("flux-detail", args=[self.flux.id]),
            {"categorie": str(self.cat2.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.budget_cat1_mars.refresh_from_db()
        self.budget_cat2_mars.refresh_from_db()
        self.assertEqual(self.budget_cat1_mars.montant_consomme, Decimal("0.00"))
        self.assertEqual(self.budget_cat2_mars.montant_consomme, Decimal("100.00"))

    def test_changement_mois_recalcule_ancien_budget(self):
        """Déplacer un flux sur un autre mois recalcule les budgets des deux mois."""
        response = self.client.patch(
            reverse("flux-detail", args=[self.flux.id]),
            {"date_flux": "2024-04-10"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.budget_cat1_mars.refresh_from_db()
        self.budget_cat1_avril.refresh_from_db()
        self.assertEqual(self.budget_cat1_mars.montant_consomme, Decimal("0.00"))
        self.assertEqual(self.budget_cat1_avril.montant_consomme, Decimal("100.00"))

    def test_patch_partiel_sans_categorie_accepte(self):
        """Un PATCH partiel (montant seul) ne doit pas exiger la catégorie."""
        response = self.client.patch(
            reverse("flux-detail", args=[self.flux.id]),
            {"montant": "-150.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.compte1.refresh_from_db()
        self.assertEqual(self.compte1.solde_theorique, Decimal("850.00"))


class FluxProtectionAPITest(APITestCase):
    """
    Les flux de transfert et d'ajustement sont protégés :
    pas de création directe, pas de modification, pas de suppression unitaire.
    """

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="COURANT5", libelle="Courant")
        titulaire = Titulaire.objects.create(code="PIERRE5", libelle="Pierre")
        etablissement = Etablissement.objects.create(code="BNP5", libelle="BNP")
        self.devise = Devise.objects.create(
            code="EUR5", libelle="Euro", symbole="€", est_defaut=False
        )
        self.type_flux = TypeFlux.objects.create(code="DEBIT5", libelle="Débit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE5", libelle="Validé", est_definitif=True
        )
        self.categorie = Categorie.objects.create(code="CAT_PR5", nom="Courses PR")
        self.compte = Compte.objects.create(
            code="CPT-PR01", nom="Compte protection",
            type_compte=type_compte, titulaire=titulaire,
            etablissement=etablissement, devise=self.devise,
            solde_initial=Decimal("1000.00"),
        )
        self.flux_transfert = Flux.objects.create(
            compte=self.compte,
            categorie=None,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal("-200.00"),
            date_flux=datetime.date(2024, 3, 15),
            est_transfert=True,
        )
        self.flux_ajustement = Flux.objects.create(
            compte=self.compte,
            categorie=None,
            type_flux=self.type_flux,
            statut=self.statut,
            devise=self.devise,
            montant=Decimal("-50.00"),
            date_flux=datetime.date(2024, 3, 15),
            est_ajustement=True,
        )

    def test_creation_directe_flux_transfert_refusee(self):
        """POST avec est_transfert=True → 400 (passer par /transferts/)."""
        response = self.client.post(reverse("flux-list"), {
            "compte": str(self.compte.id),
            "type_flux": str(self.type_flux.id),
            "statut": str(self.statut.id),
            "devise": str(self.devise.id),
            "montant": "-100.00",
            "date_flux": "2024-03-15",
            "est_transfert": True,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("est_transfert", response.data)

    def test_modification_flux_transfert_refusee(self):
        response = self.client.patch(
            reverse("flux-detail", args=[self.flux_transfert.id]),
            {"montant": "-999.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.flux_transfert.refresh_from_db()
        self.assertEqual(self.flux_transfert.montant, Decimal("-200.00"))

    def test_suppression_flux_transfert_refusee(self):
        response = self.client.delete(
            reverse("flux-detail", args=[self.flux_transfert.id])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Flux.objects.filter(id=self.flux_transfert.id).exists())

    def test_modification_flux_ajustement_refusee(self):
        response = self.client.patch(
            reverse("flux-detail", args=[self.flux_ajustement.id]),
            {"montant": "-999.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suppression_flux_ajustement_refusee(self):
        response = self.client.delete(
            reverse("flux-detail", args=[self.flux_ajustement.id])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Flux.objects.filter(id=self.flux_ajustement.id).exists())


class MoisComptableFluxTest(TestCase):
    """Le mois comptable des flux suit le paramètre jour_debut_mois_comptable."""

    def setUp(self):
        from referentiels.models import ParametresBudget

        self.type_compte = TypeCompte.objects.create(code="COURANT", libelle="Compte courant")
        self.titulaire = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        self.etablissement = Etablissement.objects.create(code="BOURSOBANK", libelle="BoursoBank")
        self.devise = Devise.objects.create(code="EUR", libelle="Euro", symbole="€", est_defaut=True)
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        self.statut = StatutFlux.objects.create(code="VALIDE", libelle="Validé", est_definitif=True)
        self.categorie = Categorie.objects.create(code="ALIMENTATION", nom="Alimentation")
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Compte principal",
            type_compte=self.type_compte, titulaire=self.titulaire,
            etablissement=self.etablissement, devise=self.devise,
            solde_initial=Decimal("0.00"), solde_reel=Decimal("0.00"),
        )
        self.params = ParametresBudget.get_solo()

    def _make_flux(self, date_flux):
        return Flux.objects.create(
            compte=self.compte, type_flux=self.type_flux, statut=self.statut,
            devise=self.devise, categorie=self.categorie,
            montant=Decimal("-50.00"), date_flux=date_flux,
        )

    def test_defaut_jour_1_reste_calendaire(self):
        self.assertEqual(self.params.jour_debut_mois_comptable, 1)
        flux = self._make_flux(datetime.date(2026, 6, 27))
        self.assertEqual(flux.mois, datetime.date(2026, 6, 1))

    def test_jour_25_bascule_fin_de_mois(self):
        self.params.jour_debut_mois_comptable = 25
        self.params.save()
        flux_tot = self._make_flux(datetime.date(2026, 6, 27))   # salaire/dépense fin juin
        flux_debut = self._make_flux(datetime.date(2026, 7, 10))  # début juillet
        flux_avant = self._make_flux(datetime.date(2026, 6, 20))  # avant bascule
        self.assertEqual(flux_tot.mois, datetime.date(2026, 7, 1))
        self.assertEqual(flux_debut.mois, datetime.date(2026, 7, 1))
        self.assertEqual(flux_avant.mois, datetime.date(2026, 6, 1))

    def test_recalculer_mois_remappe_les_flux_existants(self):
        from django.core.management import call_command

        # Flux créés AVANT changement de paramètre → mois calendaire.
        flux = self._make_flux(datetime.date(2026, 6, 27))
        self.assertEqual(flux.mois, datetime.date(2026, 6, 1))

        self.params.jour_debut_mois_comptable = 25
        self.params.save()
        call_command("recalculer_mois")

        flux.refresh_from_db()
        self.assertEqual(flux.mois, datetime.date(2026, 7, 1))


class RemboursementAPITest(APITestCase):
    """
    Remboursement d'une dépense = contre-flux recette lié (flux_rembourse).
    Gère partiels + annulation ; refuse les cas invalides ; n'impacte pas
    le rapprochement (annotation est_pointe conservée).
    """

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="COURANT_RB", libelle="Courant")
        titulaire = Titulaire.objects.create(code="PIERRE_RB", libelle="Pierre")
        etab = Etablissement.objects.create(code="BOURSO_RB", libelle="BoursoBank")
        self.devise = Devise.objects.create(
            code="EUR_RB", libelle="Euro", symbole="E", est_defaut=False
        )
        self.type_debit = TypeFlux.objects.create(code="DEBIT", libelle="Debit")
        self.type_credit = TypeFlux.objects.create(code="CREDIT", libelle="Credit")
        self.statut = StatutFlux.objects.create(
            code="VALIDE_RB", libelle="Valide", est_definitif=True
        )
        self.categorie = Categorie.objects.create(code="SANTE_RB", nom="Sante")
        self.compte = Compte.objects.create(
            code="CPT-RB01", nom="Compte remboursement",
            type_compte=type_compte, titulaire=titulaire,
            etablissement=etab, devise=self.devise,
            solde_initial=Decimal("1000.00"), solde_reel=Decimal("1000.00"),
        )
        self.depense = Flux.objects.create(
            compte=self.compte, categorie=self.categorie,
            type_flux=self.type_debit, statut=self.statut, devise=self.devise,
            montant=Decimal("-100.00"), date_flux=datetime.date(2024, 3, 15),
            libelle="Consultation medecin",
        )

    def _url(self, flux):
        return reverse("flux-rembourser", args=[flux.id])

    def test_remboursement_total_cree_contre_flux(self):
        response = self.client.post(
            self._url(self.depense),
            {"montant": "100.00", "date": "2024-03-20"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contre = response.data["contre_flux"]
        self.assertEqual(Decimal(contre["montant"]), Decimal("100.00"))
        self.assertEqual(str(contre["compte"]), str(self.compte.id))
        self.assertEqual(str(contre["categorie"]), str(self.categorie.id))
        self.assertEqual(str(contre["flux_rembourse"]), str(self.depense.id))
        self.assertEqual(contre["type_flux_code"], "CREDIT")
        self.assertIn("Remboursement", contre["libelle"])
        self.assertEqual(
            Decimal(response.data["flux"]["montant_rembourse"]), Decimal("100.00")
        )

    def test_remboursement_recalcule_solde(self):
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_reel, Decimal("900.00"))
        self.client.post(
            self._url(self.depense),
            {"montant": "100.00", "date": "2024-03-20"},
            format="json",
        )
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_reel, Decimal("1000.00"))

    def test_remboursement_partiel_puis_solde_du_reste(self):
        r1 = self.client.post(
            self._url(self.depense),
            {"montant": "40.00", "date": "2024-03-20"},
            format="json",
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Decimal(r1.data["flux"]["montant_rembourse"]), Decimal("40.00")
        )
        r2 = self.client.post(
            self._url(self.depense),
            {"montant": "60.00", "date": "2024-03-25"},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Decimal(r2.data["flux"]["montant_rembourse"]), Decimal("100.00")
        )
        self.assertEqual(self.depense.remboursements.count(), 2)

    def test_remboursement_depasse_le_reste_refuse(self):
        response = self.client.post(
            self._url(self.depense),
            {"montant": "150.00", "date": "2024-03-20"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.depense.remboursements.exists())

    def test_remboursement_partiel_puis_depassement_refuse(self):
        self.client.post(
            self._url(self.depense),
            {"montant": "70.00", "date": "2024-03-20"},
            format="json",
        )
        response = self.client.post(
            self._url(self.depense),
            {"montant": "40.00", "date": "2024-03-25"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.depense.remboursements.count(), 1)

    def test_remboursement_sur_recette_refuse(self):
        recette = Flux.objects.create(
            compte=self.compte, categorie=self.categorie,
            type_flux=self.type_credit, statut=self.statut, devise=self.devise,
            montant=Decimal("200.00"), date_flux=datetime.date(2024, 3, 1),
            libelle="Salaire",
        )
        response = self.client.post(
            self._url(recette),
            {"montant": "50.00", "date": "2024-03-20"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remboursement_sur_transfert_refuse(self):
        transfert = Flux.objects.create(
            compte=self.compte, categorie=None,
            type_flux=self.type_debit, statut=self.statut, devise=self.devise,
            montant=Decimal("-80.00"), date_flux=datetime.date(2024, 3, 5),
            est_transfert=True,
        )
        response = self.client.post(
            self._url(transfert),
            {"montant": "80.00", "date": "2024-03-20"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_annulation_remboursement_recalcule_et_retombe_le_badge(self):
        r = self.client.post(
            self._url(self.depense),
            {"montant": "100.00", "date": "2024-03-20"},
            format="json",
        )
        contre_id = r.data["contre_flux"]["id"]
        d = self.client.delete(reverse("flux-detail", args=[contre_id]))
        self.assertEqual(d.status_code, status.HTTP_204_NO_CONTENT)
        detail = self.client.get(reverse("flux-detail", args=[self.depense.id]))
        self.assertEqual(Decimal(detail.data["montant_rembourse"]), Decimal("0"))
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_reel, Decimal("900.00"))

    def test_montant_rembourse_expose_sur_la_liste(self):
        self.client.post(
            self._url(self.depense),
            {"montant": "30.00", "date": "2024-03-20"},
            format="json",
        )
        response = self.client.get(
            reverse("flux-list"), {"compte": str(self.compte.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        depense = next(
            f for f in response.data["results"] if f["id"] == str(self.depense.id)
        )
        self.assertEqual(Decimal(depense["montant_rembourse"]), Decimal("30.00"))
        self.assertIn("est_pointe", depense)
        self.assertFalse(depense["est_pointe"])
