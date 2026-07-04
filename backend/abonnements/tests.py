import datetime
from decimal import Decimal
from django.test import TestCase

from referentiels.models import (
    TypeFlux, ModePaiement, Frequence,
    TypeCompte, Etablissement, Titulaire, Devise
)
from comptes.models import Compte
from categories.models import Categorie
from abonnements.models import Abonnement


class AbonnementModelTest(TestCase):

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
        self.frequence_mensuelle = Frequence.objects.create(
            code="MENSUEL", libelle="Mensuel", nb_jours=30
        )
        self.frequence_ponctuelle = Frequence.objects.create(
            code="PONCTUEL", libelle="Ponctuel", nb_jours=None
        )
        self.categorie = Categorie.objects.create(
            code="ABONNEMENTS", nom="Abonnements"
        )
        self.compte = Compte.objects.create(
            code="CPT-0001",
            nom="Compte principal",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
            solde_initial=Decimal("2000.00"),
            solde_reel=Decimal("2000.00"),
        )

    def _make_abonnement(self, **kwargs):
        defaults = {
            "nom": "Netflix",
            "compte": self.compte,
            "categorie": self.categorie,
            "type_flux": self.type_flux,
            "frequence": self.frequence_mensuelle,
            "montant_attendu": Decimal("-15.99"),
            "date_debut": datetime.date(2024, 1, 1),
        }
        defaults.update(kwargs)
        return Abonnement.objects.create(**defaults)

    def test_str(self):
        ab = self._make_abonnement()
        self.assertIn("Netflix", str(ab))
        self.assertIn("-15.99", str(ab))

    def test_est_en_retard_false_si_recent(self):
        """Pas en retard si derniere_occurrence < 30 jours."""
        ab = self._make_abonnement()
        ab.derniere_occurrence = datetime.date.today() - datetime.timedelta(days=15)
        ab.save(update_fields=["derniere_occurrence"])
        self.assertFalse(ab.est_en_retard)

    def test_est_en_retard_true_si_depasse(self):
        """En retard si derniere_occurrence > 30 jours."""
        ab = self._make_abonnement()
        ab.derniere_occurrence = datetime.date.today() - datetime.timedelta(days=45)
        ab.save(update_fields=["derniere_occurrence"])
        self.assertTrue(ab.est_en_retard)

    def test_est_en_retard_false_si_inactif(self):
        """Jamais en retard si abonnement inactif."""
        ab = self._make_abonnement(actif=False)
        ab.derniere_occurrence = datetime.date.today() - datetime.timedelta(days=60)
        ab.save(update_fields=["derniere_occurrence"])
        self.assertFalse(ab.est_en_retard)

    def test_est_en_retard_false_si_frequence_ponctuelle(self):
        """Pas de retard calculable si fréquence sans nb_jours."""
        ab = self._make_abonnement(frequence=self.frequence_ponctuelle)
        ab.derniere_occurrence = datetime.date.today() - datetime.timedelta(days=90)
        ab.save(update_fields=["derniere_occurrence"])
        self.assertFalse(ab.est_en_retard)

    def test_est_en_retard_false_si_aucune_occurrence(self):
        """Sans derniere_occurrence, pas de retard détectable."""
        ab = self._make_abonnement()
        self.assertFalse(ab.est_en_retard)

    def test_soft_delete(self):
        ab = self._make_abonnement()
        ab_id = ab.id
        ab.delete()
        self.assertFalse(Abonnement.objects.filter(id=ab_id).exists())
        self.assertTrue(
            Abonnement.objects.all_with_deleted().filter(id=ab_id).exists()
        )

    def test_materialise_ce_mois(self):
        """Vrai dès qu'un flux lié tombe dans le mois comptable courant."""
        from flux.models import Flux
        from referentiels.models import StatutFlux

        statut = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True
        )
        ab = self._make_abonnement()
        self.assertFalse(ab.materialise_ce_mois)

        Flux.objects.create(
            compte=self.compte,
            categorie=self.categorie,
            type_flux=self.type_flux,
            statut=statut,
            devise=self.devise,
            montant=Decimal("-15.99"),
            date_flux=datetime.date.today(),
            abonnement=ab,
        )
        self.assertTrue(ab.materialise_ce_mois)

from abonnements.services import (
    calculer_divergence_pct,
    verifier_divergence,
    mettre_a_jour_derniere_occurrence,
)


class CalculDivergenceTest(TestCase):
    """Teste la logique pure du calcul de divergence."""

    def test_sans_divergence(self):
        """Montant identique → divergence 0%."""
        result = calculer_divergence_pct(
            Decimal("-15.99"), Decimal("-15.99")
        )
        self.assertEqual(result, Decimal("0.00"))

    def test_divergence_positive(self):
        """Montant supérieur au attendu."""
        result = calculer_divergence_pct(
            Decimal("-100.00"), Decimal("-110.00")
        )
        self.assertEqual(result, Decimal("10.00"))

    def test_divergence_negative(self):
        """Montant inférieur à l'attendu."""
        result = calculer_divergence_pct(
            Decimal("-100.00"), Decimal("-90.00")
        )
        self.assertEqual(result, Decimal("10.00"))

    def test_pas_division_par_zero(self):
        """Montant attendu = 0 → divergence = 0."""
        result = calculer_divergence_pct(Decimal("0"), Decimal("-50.00"))
        self.assertEqual(result, Decimal("0.00"))

    def test_divergence_arrondie(self):
        """Résultat arrondi à 2 décimales."""
        result = calculer_divergence_pct(
            Decimal("-15.99"), Decimal("-17.00")
        )
        self.assertEqual(result, Decimal("6.32"))


class VerifierDivergenceTest(TestCase):

    def setUp(self):
        type_compte = TypeCompte.objects.create(
            code="COURANT", libelle="Courant"
        )
        titulaire = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        etablissement = Etablissement.objects.create(
            code="BNP", libelle="BNP"
        )
        devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True
        )
        type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        frequence = Frequence.objects.create(
            code="MENSUEL", libelle="Mensuel", nb_jours=30
        )
        categorie = Categorie.objects.create(
            code="ABONNEMENTS", nom="Abonnements"
        )
        compte = Compte.objects.create(
            code="CPT-0001",
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
            frequence=frequence,
            montant_attendu=Decimal("-15.99"),
            seuil_divergence_pct=Decimal("10.00"),
            date_debut=datetime.date(2024, 1, 1),
        )

    def test_pas_en_divergence(self):
        result = verifier_divergence(self.abonnement, Decimal("-15.99"))
        self.assertFalse(result["en_divergence"])
        self.assertEqual(result["divergence_pct"], Decimal("0.00"))

    def test_en_divergence_au_dessus_seuil(self):
        """Écart > 10% → en divergence."""
        result = verifier_divergence(self.abonnement, Decimal("-18.00"))
        self.assertTrue(result["en_divergence"])

    def test_pas_en_divergence_sous_seuil(self):
        """Écart < 10% → pas de divergence."""
        result = verifier_divergence(self.abonnement, Decimal("-16.50"))
        self.assertFalse(result["en_divergence"])

    def test_retour_complet(self):
        """Le dict de retour contient tous les champs attendus."""
        result = verifier_divergence(self.abonnement, Decimal("-20.00"))
        self.assertIn("divergence_pct", result)
        self.assertIn("en_divergence", result)
        self.assertIn("montant_attendu", result)
        self.assertIn("montant_reel", result)
        self.assertIn("seuil_pct", result)


class MiseAJourDerniereOccurrenceTest(TestCase):

    def setUp(self):
        type_compte = TypeCompte.objects.create(
            code="COURANT2", libelle="Courant"
        )
        titulaire = Titulaire.objects.create(code="PIERRE2", libelle="Pierre")
        etablissement = Etablissement.objects.create(
            code="BNP2", libelle="BNP"
        )
        devise = Devise.objects.create(
            code="EUR2", libelle="Euro", symbole="€", est_defaut=False
        )
        type_flux = TypeFlux.objects.create(code="DEBIT2", libelle="Débit")
        frequence = Frequence.objects.create(
            code="MENSUEL2", libelle="Mensuel", nb_jours=30
        )
        categorie = Categorie.objects.create(
            code="STREAMING", nom="Streaming"
        )
        compte = Compte.objects.create(
            code="CPT-0002",
            nom="Compte test 2",
            type_compte=type_compte,
            titulaire=titulaire,
            etablissement=etablissement,
            devise=devise,
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("1000.00"),
        )
        self.abonnement = Abonnement.objects.create(
            nom="Spotify",
            compte=compte,
            categorie=categorie,
            type_flux=type_flux,
            frequence=frequence,
            montant_attendu=Decimal("-9.99"),
            date_debut=datetime.date(2024, 1, 1),
        )

    def test_mise_a_jour_si_date_plus_recente(self):
        self.abonnement.derniere_occurrence = datetime.date(2024, 2, 1)
        self.abonnement.save(update_fields=["derniere_occurrence"])

        mettre_a_jour_derniere_occurrence(
            self.abonnement, datetime.date(2024, 3, 1)
        )
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.derniere_occurrence, datetime.date(2024, 3, 1)
        )

    def test_pas_de_mise_a_jour_si_date_plus_ancienne(self):
        self.abonnement.derniere_occurrence = datetime.date(2024, 3, 1)
        self.abonnement.save(update_fields=["derniere_occurrence"])

        mettre_a_jour_derniere_occurrence(
            self.abonnement, datetime.date(2024, 2, 1)
        )
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.derniere_occurrence, datetime.date(2024, 3, 1)
        )

    def test_mise_a_jour_si_aucune_occurrence(self):
        """Sans occurrence précédente, toute date est acceptée."""
        self.assertIsNone(self.abonnement.derniere_occurrence)
        mettre_a_jour_derniere_occurrence(
            self.abonnement, datetime.date(2024, 1, 15)
        )
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.derniere_occurrence, datetime.date(2024, 1, 15)
        )

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status as drf_status


class AbonnementAPITest(APITestCase):

    def setUp(self):
        type_compte = TypeCompte.objects.create(
            code="COURANT3", libelle="Courant"
        )
        titulaire = Titulaire.objects.create(code="PIERRE3", libelle="Pierre")
        etablissement = Etablissement.objects.create(
            code="BNP3", libelle="BNP"
        )
        self.devise = Devise.objects.create(
            code="EUR3", libelle="Euro", symbole="€", est_defaut=False
        )
        self.type_flux = TypeFlux.objects.create(
            code="DEBIT3", libelle="Débit"
        )
        self.frequence = Frequence.objects.create(
            code="MENSUEL3", libelle="Mensuel", nb_jours=30
        )
        self.categorie = Categorie.objects.create(
            code="STREAMING3", nom="Streaming"
        )
        self.compte = Compte.objects.create(
            code="CPT-0003",
            nom="Compte API test",
            type_compte=type_compte,
            titulaire=titulaire,
            etablissement=etablissement,
            devise=self.devise,
            solde_initial=Decimal("1000.00"),
            solde_reel=Decimal("1000.00"),
        )
        self.payload_valide = {
            "nom": "Netflix",
            "compte": str(self.compte.id),
            "categorie": str(self.categorie.id),
            "type_flux": str(self.type_flux.id),
            "frequence": str(self.frequence.id),
            "montant_attendu": "-15.99",
            "date_debut": "2024-01-01",
        }

    def test_creation_abonnement(self):
        response = self.client.post(
            reverse("abonnement-list"), self.payload_valide, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_201_CREATED)
        self.assertEqual(response.data["nom"], "Netflix")

    def test_montant_nul_refuse(self):
        payload = {**self.payload_valide, "montant_attendu": "0.00"}
        response = self.client.post(
            reverse("abonnement-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("montant_attendu", response.data)

    def test_date_fin_anterieure_refuse(self):
        payload = {
            **self.payload_valide,
            "date_fin": "2023-12-31",
        }
        response = self.client.post(
            reverse("abonnement-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_fin", response.data)

    def test_jour_echeance_invalide(self):
        payload = {**self.payload_valide, "jour_echeance": 32}
        response = self.client.post(
            reverse("abonnement-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("jour_echeance", response.data)

    def test_action_verifier_divergence_ok(self):
        create = self.client.post(
            reverse("abonnement-list"), self.payload_valide, format="json"
        )
        ab_id = create.data["id"]
        response = self.client.post(
            reverse("abonnement-verifier-divergence-action", args=[ab_id]),
            {"montant_reel": "-15.99"},
            format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertFalse(response.data["en_divergence"])

    def test_action_verifier_divergence_alerte(self):
        create = self.client.post(
            reverse("abonnement-list"), self.payload_valide, format="json"
        )
        ab_id = create.data["id"]
        response = self.client.post(
            reverse("abonnement-verifier-divergence-action", args=[ab_id]),
            {"montant_reel": "-25.00"},
            format="json"
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertTrue(response.data["en_divergence"])

    def test_action_desactiver(self):
        create = self.client.post(
            reverse("abonnement-list"), self.payload_valide, format="json"
        )
        ab_id = create.data["id"]
        response = self.client.post(
            reverse("abonnement-desactiver", args=[ab_id])
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        detail = self.client.get(
            reverse("abonnement-detail", args=[ab_id])
        )
        self.assertFalse(detail.data["actif"])

    def test_filtre_par_actif(self):
        self.client.post(
            reverse("abonnement-list"), self.payload_valide, format="json"
        )
        response = self.client.get(
            reverse("abonnement-list"), {"actif": True}
        )
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_soft_delete(self):
        create = self.client.post(
            reverse("abonnement-list"), self.payload_valide, format="json"
        )
        ab_id = create.data["id"]
        response = self.client.delete(
            reverse("abonnement-detail", args=[ab_id])
        )
        self.assertEqual(response.status_code, drf_status.HTTP_204_NO_CONTENT)
        liste = self.client.get(reverse("abonnement-list"))
        self.assertEqual(liste.data["count"], 0)


class FluxAbonnementSignalTest(TestCase):
    """
    Génération d'un flux depuis un abonnement (FK) : le signal flux
    alimente derniere_occurrence et détecte la divergence automatiquement.
    """

    def setUp(self):
        from referentiels.models import StatutFlux

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
        self.frequence = Frequence.objects.create(
            code="MENSUEL", libelle="Mensuel", nb_jours=30
        )
        self.categorie = Categorie.objects.create(code="STREAMING", nom="Streaming")
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Compte test",
            type_compte=type_compte, titulaire=titulaire,
            etablissement=etablissement, devise=self.devise,
            solde_initial=Decimal("1000.00"), solde_reel=Decimal("1000.00"),
        )
        self.abonnement = Abonnement.objects.create(
            nom="Netflix", compte=self.compte, categorie=self.categorie,
            type_flux=self.type_flux, frequence=self.frequence,
            montant_attendu=Decimal("-15.99"),
            seuil_divergence_pct=Decimal("10.00"),
            date_debut=datetime.date(2024, 1, 1),
        )

    def _make_flux(self, montant, date_flux=None):
        from flux.models import Flux

        return Flux.objects.create(
            compte=self.compte, categorie=self.categorie,
            type_flux=self.type_flux, statut=self.statut, devise=self.devise,
            montant=Decimal(str(montant)),
            date_flux=date_flux or datetime.date.today(),
            abonnement=self.abonnement,
        )

    def test_flux_lie_met_a_jour_derniere_occurrence(self):
        d = datetime.date.today()
        self._make_flux("-15.99", date_flux=d)
        self.abonnement.refresh_from_db()
        self.assertEqual(self.abonnement.derniere_occurrence, d)

    def test_flux_conforme_ne_cree_pas_alerte(self):
        from alertes.models import Alerte, TypeAlerte

        self._make_flux("-15.99")
        self.assertFalse(
            Alerte.objects.filter(
                type_alerte=TypeAlerte.ABONNEMENT_DIVERGENCE,
                abonnement=self.abonnement,
            ).exists()
        )

    def test_flux_divergent_cree_alerte(self):
        from alertes.models import Alerte, TypeAlerte

        self._make_flux("-25.00")  # +56 % > seuil 10 %
        self.assertTrue(
            Alerte.objects.filter(
                type_alerte=TypeAlerte.ABONNEMENT_DIVERGENCE,
                abonnement=self.abonnement,
                acquittee=False,
            ).exists()
        )

    def test_flux_sans_abonnement_ignore_le_hook(self):
        from flux.models import Flux
        from alertes.models import Alerte

        Flux.objects.create(
            compte=self.compte, categorie=self.categorie,
            type_flux=self.type_flux, statut=self.statut, devise=self.devise,
            montant=Decimal("-25.00"), date_flux=datetime.date.today(),
        )
        self.abonnement.refresh_from_db()
        self.assertIsNone(self.abonnement.derniere_occurrence)
        self.assertEqual(Alerte.objects.count(), 0)


class VerifierEcheancesActionTest(APITestCase):
    """L'action verifier-echeances génère les alertes 'en retard'."""

    def setUp(self):
        type_compte = TypeCompte.objects.create(code="COURANT4", libelle="Courant")
        titulaire = Titulaire.objects.create(code="PIERRE4", libelle="Pierre")
        etablissement = Etablissement.objects.create(code="BNP4", libelle="BNP")
        devise = Devise.objects.create(
            code="EUR4", libelle="Euro", symbole="€", est_defaut=False
        )
        type_flux = TypeFlux.objects.create(code="DEBIT4", libelle="Débit")
        frequence = Frequence.objects.create(
            code="MENSUEL4", libelle="Mensuel", nb_jours=30
        )
        categorie = Categorie.objects.create(code="STREAMING4", nom="Streaming")
        compte = Compte.objects.create(
            code="CPT-0004", nom="Compte test",
            type_compte=type_compte, titulaire=titulaire,
            etablissement=etablissement, devise=devise,
            solde_initial=Decimal("1000.00"), solde_reel=Decimal("1000.00"),
        )
        self.abonnement = Abonnement.objects.create(
            nom="Netflix", compte=compte, categorie=categorie,
            type_flux=type_flux, frequence=frequence,
            montant_attendu=Decimal("-15.99"),
            date_debut=datetime.date(2024, 1, 1),
        )

    def test_verifier_echeances_cree_alerte_en_retard(self):
        from alertes.models import Alerte, TypeAlerte

        # En retard : dernière occurrence il y a plus d'un cycle.
        self.abonnement.derniere_occurrence = (
            datetime.date.today() - datetime.timedelta(days=45)
        )
        self.abonnement.save(update_fields=["derniere_occurrence"])

        response = self.client.post(reverse("abonnement-verifier-echeances"))
        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(response.data["crees"], 1)
        self.assertTrue(
            Alerte.objects.filter(
                type_alerte=TypeAlerte.ABONNEMENT_EN_RETARD,
                abonnement=self.abonnement,
            ).exists()
        )

    def test_verifier_echeances_idempotent(self):
        self.abonnement.derniere_occurrence = (
            datetime.date.today() - datetime.timedelta(days=45)
        )
        self.abonnement.save(update_fields=["derniere_occurrence"])

        self.client.post(reverse("abonnement-verifier-echeances"))
        second = self.client.post(reverse("abonnement-verifier-echeances"))
        self.assertEqual(second.data["crees"], 0)