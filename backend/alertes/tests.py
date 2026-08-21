import datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from alertes.models import Alerte, NiveauAlerte, TypeAlerte
from comptes.models import Compte
from referentiels.models import Devise, Etablissement, Titulaire, TypeCompte


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

from django.test import TestCase

from abonnements.models import Abonnement
from alertes.services import (
    detecter_alerte_abonnement_en_retard,
    detecter_alerte_divergence_abonnement,
    detecter_alerte_ecart_solde,
    detecter_alerte_solde_bas,
    detecter_alertes_budget,
)
from budgets.models import Budget
from categories.models import Categorie
from referentiels.models import Frequence, TypeFlux


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
from rest_framework import status as drf_status

from core.tests_base import APIAuthTestCase


class AlerteAPITest(APIAuthTestCase):

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


# ---------------------------------------------------------------------------
# Formatage français des phrases d'alerte (D02 de la revue UI/UX 2026-08-20)
# ---------------------------------------------------------------------------

class FormatageAlerteTest(TestCase):
    """
    Une alerte est lue par un humain : elle s'écrit comme le reste de
    l'interface. Ces tests verrouillent la forme, pas le fond.
    """

    def test_euros_espace_insecable_et_virgule(self):
        from alertes.services.formatage import euros
        self.assertEqual(euros(Decimal("5636.49")), "5 636,49 €")
        self.assertEqual(euros(Decimal("139.81")), "139,81 €")
        self.assertEqual(euros(None), "—")

    def test_pourcent_virgule_decimale(self):
        from alertes.services.formatage import pourcent
        self.assertEqual(pourcent(Decimal("93.21")), "93,21 %")

    def test_mois_en_francais(self):
        from alertes.services.formatage import mois_annee
        self.assertEqual(mois_annee(datetime.date(2026, 7, 1)), "juillet 2026")

    def test_date_courte_en_francais(self):
        from alertes.services.formatage import date_courte
        self.assertEqual(date_courte(datetime.date(2026, 7, 18)), "18 juillet 2026")


class PhraseAlerteBudgetTest(TestCase):

    def setUp(self):
        self.categorie = Categorie.objects.create(code="COURSES2", nom="Courses")
        self.budget = Budget.objects.create(
            categorie=self.categorie,
            mois=datetime.date(2026, 7, 1),
            montant_prevu=Decimal("150.00"),
        )

    def _declencher(self, taux, consomme):
        self.budget.taux_consommation = Decimal(taux)
        self.budget.montant_consomme = Decimal(consomme)
        self.budget.save(update_fields=["taux_consommation", "montant_consomme"])
        return detecter_alertes_budget(self.budget)[0]

    def test_phrase_entierement_en_francais(self):
        """Le cas exact relevé par la revue : « July 2026 », « 93.21 », « 139.81 »."""
        alerte = self._declencher("93.21", "139.81")
        self.assertIn("juillet 2026", alerte.explication)
        self.assertIn("93,21 %", alerte.explication)
        self.assertIn("139,81 €", alerte.explication)
        self.assertNotIn("July", alerte.explication)
        self.assertNotIn("93.21", alerte.explication)
        self.assertNotIn("139.81", alerte.explication)

    def test_budget_thematique_ne_plante_pas(self):
        """
        Un budget thématique n'a pas de catégorie. `budget.categorie.nom`
        levait AttributeError — dans un signal post_save de Flux, donc en 500
        sur la création du flux.
        """
        thematique = Budget.objects.create(
            categorie=None,
            nom="Vacances d'été",
            mois=datetime.date(2026, 7, 1),
            montant_prevu=Decimal("500.00"),
            taux_consommation=Decimal("85.00"),
            montant_consomme=Decimal("425.00"),
        )
        alertes = detecter_alertes_budget(thematique)
        self.assertEqual(len(alertes), 1)
        self.assertIn("Vacances d'été", alertes[0].explication)


# ---------------------------------------------------------------------------
# Refermeture des alertes périmées (D01 de la revue UI/UX 2026-08-20)
# ---------------------------------------------------------------------------

class RefermetureAlerteBudgetTest(TestCase):
    """
    Le cas relevé par la revue : le budget retombe, l'alerte reste et continue
    d'annoncer l'ancien chiffre à côté du nouveau.
    """

    def setUp(self):
        self.categorie = Categorie.objects.create(code="COURSES3", nom="Courses")
        self.budget = Budget.objects.create(
            categorie=self.categorie,
            mois=datetime.date(2026, 7, 1),
            montant_prevu=Decimal("150.00"),
        )

    def _taux(self, taux, consomme):
        self.budget.taux_consommation = Decimal(taux)
        self.budget.montant_consomme = Decimal(consomme)
        self.budget.save(update_fields=["taux_consommation", "montant_consomme"])

    def test_alerte_refermee_quand_le_taux_retombe(self):
        self._taux("93.21", "139.81")
        alerte = detecter_alertes_budget(self.budget)[0]
        self.assertFalse(alerte.acquittee)

        self._taux("60.00", "90.00")          # exactement le cas de la revue
        detecter_alertes_budget(self.budget)

        alerte.refresh_from_db()
        self.assertTrue(alerte.acquittee)
        self.assertIsNotNone(alerte.acquittee_le)

    def test_seul_le_seuil_franchi_reste_ouvert(self):
        """À 110 % les deux alertes existent ; à 85 % seule celle de 80 % tient."""
        self._taux("110.00", "165.00")
        detecter_alertes_budget(self.budget)
        self._taux("85.00", "127.50")
        detecter_alertes_budget(self.budget)

        ouvertes = Alerte.objects.filter(budget=self.budget, acquittee=False)
        types = sorted(a.type_alerte for a in ouvertes)
        self.assertEqual(types, [TypeAlerte.BUDGET_ALERTE])

    def test_rien_ne_se_referme_si_le_seuil_tient_toujours(self):
        self._taux("93.21", "139.81")
        alerte = detecter_alertes_budget(self.budget)[0]
        self._taux("88.00", "132.00")
        detecter_alertes_budget(self.budget)
        alerte.refresh_from_db()
        self.assertFalse(alerte.acquittee)

    def test_une_alerte_juste_peut_reprendre_apres_refermeture(self):
        """Le dédoublonnage ne doit pas bloquer une alerte légitime ensuite."""
        self._taux("93.21", "139.81")
        detecter_alertes_budget(self.budget)
        self._taux("40.00", "60.00")
        detecter_alertes_budget(self.budget)
        self._taux("95.00", "142.50")
        nouvelles = detecter_alertes_budget(self.budget)

        self.assertEqual(len(nouvelles), 1)
        self.assertIn("95,00 %", nouvelles[0].explication)


class AlerteSurBudgetSupprimeTest(TestCase):
    """
    Second déclencheur d'ADR-0067 : la cause ne baisse pas, elle **disparaît**.

    Constaté le 2026-08-21 en vérifiant la passe 4 : un budget de juin
    soft-deleté n'existait plus dans l'application, mais son alerte s'affichait
    toujours dans « Alertes récentes », datée et affirmative, à côté d'un
    tableau où le budget était absent.
    """

    def setUp(self):
        self.categorie = Categorie.objects.create(code="COURSES4", nom="Courses")
        self.budget = Budget.objects.create(
            categorie=self.categorie,
            mois=datetime.date(2026, 6, 1),
            montant_prevu=Decimal("100.00"),
            montant_consomme=Decimal("90.00"),
            taux_consommation=Decimal("90.00"),
        )

    def test_supprimer_le_budget_referme_ses_alertes(self):
        alerte = detecter_alertes_budget(self.budget)[0]
        self.assertFalse(alerte.acquittee)

        self.budget.delete()

        alerte.refresh_from_db()
        self.assertTrue(alerte.acquittee)
        self.assertIsNotNone(alerte.acquittee_le)

    def test_l_alerte_reste_lisible_apres_coup(self):
        """On referme, on ne supprime pas : le journal garde la trace."""
        alerte = detecter_alertes_budget(self.budget)[0]
        texte = alerte.explication
        self.budget.delete()

        alerte.refresh_from_db()
        self.assertEqual(alerte.explication, texte)
        self.assertFalse(alerte.is_deleted)


# ---------------------------------------------------------------------------
# Unicité d'une alerte ouverte (D27 de la revue UI/UX du 2026-08-20)
# ---------------------------------------------------------------------------

class AlerteOuverteUniqueTest(TestCase):
    """
    Le dédoublonnage n'était qu'un `exists()` suivi d'un `create()`. Ce qui
    garantit désormais l'unicité est la contrainte, pas le test — et ces
    tests-ci s'adressent à la contrainte.
    """

    def setUp(self):
        self.categorie = Categorie.objects.create(code="COURSES5", nom="Courses")
        self.budget = Budget.objects.create(
            categorie=self.categorie,
            mois=datetime.date(2026, 9, 1),
            montant_prevu=Decimal("100.00"),
            montant_consomme=Decimal("90.00"),
            taux_consommation=Decimal("90.00"),
        )

    def _creer(self):
        """Contourne le service : on vise la contrainte, pas son garde-fou."""
        return Alerte.objects.create(
            type_alerte=TypeAlerte.BUDGET_ALERTE,
            niveau=NiveauAlerte.AVERTISSEMENT,
            budget=self.budget,
            explication="x",
            valeur_seuil=Decimal("80.00"),
        )

    def test_deux_alertes_ouvertes_sur_la_meme_cible_sont_refusees(self):
        self._creer()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._creer()

    def test_la_contrainte_compare_bien_les_cibles_nulles(self):
        """
        ⚠️ Le cœur du correctif. Une seule des quatre cibles est renseignée ;
        sans `nulls_distinct=False`, PostgreSQL tient deux `NULL` pour distincts
        et la contrainte ne mordrait **jamais**. Ce test échoue si on le retire.
        """
        Alerte.objects.create(
            type_alerte=TypeAlerte.ABONNEMENT_EN_RETARD,
            niveau=NiveauAlerte.AVERTISSEMENT,
            explication="sans cible",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Alerte.objects.create(
                    type_alerte=TypeAlerte.ABONNEMENT_EN_RETARD,
                    niveau=NiveauAlerte.AVERTISSEMENT,
                    explication="sans cible",
                )

    def test_une_alerte_acquittee_laisse_la_place(self):
        premiere = self._creer()
        premiere.acquitter()
        self.assertIsNotNone(self._creer())

    def test_une_alerte_supprimee_laisse_la_place(self):
        """
        ⚠️ `condition` porte `is_deleted=False`. Sans lui, une ligne
        soft-deletée occuperait encore la place et bloquerait une recréation
        légitime — piège du §7, déjà payé ailleurs.
        """
        premiere = self._creer()
        premiere.delete()
        self.assertIsNotNone(self._creer())

    def test_le_service_rend_None_plutot_que_de_lever(self):
        """Perdre la course n'est pas une erreur : c'est le résultat attendu."""
        from alertes.services import creer_si_absente

        premier = creer_si_absente(
            type_alerte=TypeAlerte.SOLDE_BAS,
            cible={"budget": self.budget},
            niveau=NiveauAlerte.AVERTISSEMENT,
            explication="x",
        )
        self.assertIsNotNone(premier)
        # Le chemin rapide (`exists`) écarte le second.
        self.assertIsNone(
            creer_si_absente(
                type_alerte=TypeAlerte.SOLDE_BAS,
                cible={"budget": self.budget},
                niveau=NiveauAlerte.AVERTISSEMENT,
                explication="x",
            )
        )

    def test_la_transaction_survit_a_une_course_perdue(self):
        """
        ⚠️ Sans `transaction.atomic()` autour du `create`, l'`IntegrityError`
        marquerait la transaction courante comme à annuler et **la requête
        suivante lèverait** `TransactionManagementError`. Le signal de Flux
        s'effondrerait après la première course perdue.
        """
        from alertes.services import creer_si_absente

        self._creer()
        # On force le chemin lent : le test rapide est court-circuité par un
        # type différent, mais la contrainte, elle, verra le doublon.
        perdue = creer_si_absente(
            type_alerte=TypeAlerte.BUDGET_ALERTE,
            cible={"budget": self.budget},
            niveau=NiveauAlerte.AVERTISSEMENT,
            explication="x",
        )
        self.assertIsNone(perdue)
        # La transaction est toujours utilisable — c'est tout l'objet du test.
        self.assertEqual(Alerte.objects.filter(budget=self.budget).count(), 1)
