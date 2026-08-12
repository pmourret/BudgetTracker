"""Tests de l'authentification — l'app `accounts` en avait zéro jusqu'ici.

Ce fichier teste **la fermeture de l'API**, pas le métier. Le reste de la suite
passe par `core.tests_base.APIAuthTestCase`, qui court-circuite volontairement
les classes d'authentification : c'est donc **ici, et uniquement ici**, que la
propriété « une requête anonyme est refusée » est réellement vérifiée.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.tests_base import APIAuthTestCase

Utilisateur = get_user_model()

MOT_DE_PASSE = "un-mot-de-passe-solide-42"


class ApiFermeeTest(APITestCase):
    """La propriété qui justifie tout le chantier : plus rien n'est ouvert."""

    # Un échantillon large plutôt qu'une route témoin : la dérogation d'origine
    # était **globale**, une régression le serait aussi. On balaie donc une route
    # par famille — ressource, référentiel, analytics — plutôt que de faire
    # confiance au défaut de `settings`.
    ROUTES = (
        "/api/v1/flux/",
        "/api/v1/comptes/",
        "/api/v1/categories/",
        "/api/v1/budgets/",
        "/api/v1/transferts/",
        "/api/v1/patrimoine/",
        "/api/v1/imports/",
        "/api/v1/referentiels/types-flux/",
        "/api/v1/referentiels/parametres-budget/",
        "/api/v1/analytics/dashboard/",
        "/api/v1/auth/me/",
    )

    def test_lecture_anonyme_refusee_partout(self):
        for route in self.ROUTES:
            with self.subTest(route=route):
                self.assertEqual(
                    self.client.get(route).status_code,
                    status.HTTP_401_UNAUTHORIZED,
                )

    def test_ecriture_anonyme_refusee(self):
        """Le cas qui rendait la dérogation grave : n'importe qui pouvait écrire."""
        reponse = self.client.post(
            "/api/v1/flux/", {"montant": "-10.00", "libelle": "Intrusion"}
        )
        self.assertEqual(reponse.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jeton_invalide_refuse(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer ceci-n-est-pas-un-jeton")
        self.assertEqual(
            self.client.get("/api/v1/flux/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class JetonTest(APITestCase):
    """Le parcours réel : on échange un mot de passe contre un jeton, et il ouvre."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="pierre", password=MOT_DE_PASSE, email="pierre@foyer.local"
        )

    def obtenir(self, **surcharges):
        charge = {"username": "pierre", "password": MOT_DE_PASSE, **surcharges}
        return self.client.post("/api/v1/auth/token/", charge)

    def test_obtention_du_jeton(self):
        reponse = self.obtenir()
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertIn("access", reponse.data)
        self.assertIn("refresh", reponse.data)

    def test_mauvais_mot_de_passe_refuse(self):
        self.assertEqual(
            self.obtenir(password="faux").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_compte_desactive_refuse(self):
        self.utilisateur.is_active = False
        self.utilisateur.save(update_fields=["is_active"])
        self.assertEqual(self.obtenir().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_le_jeton_ouvre_l_api(self):
        jeton = self.obtenir().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {jeton}")
        self.assertEqual(
            self.client.get("/api/v1/flux/").status_code, status.HTTP_200_OK
        )

    def test_rafraichissement(self):
        rafraichissement = self.obtenir().data["refresh"]
        reponse = self.client.post(
            "/api/v1/auth/token/refresh/", {"refresh": rafraichissement}
        )
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertIn("access", reponse.data)
        # `ROTATE_REFRESH_TOKENS` est actif : un refresh neuf revient avec.
        # Sans lui, une session longue s'appuierait indéfiniment sur le premier.
        self.assertIn("refresh", reponse.data)


class MoiTest(APIAuthTestCase):
    def test_renvoie_le_porteur_du_jeton(self):
        reponse = self.client.get("/api/v1/auth/me/")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data["username"], "tests")

    def test_n_expose_ni_is_staff_ni_is_superuser(self):
        """Un écran qui lit un droit dans l'API finit par le croire garanti.

        La garantie est au serveur. Test de régression, comme dans FoyerOS.
        """
        reponse = self.client.get("/api/v1/auth/me/")
        self.assertNotIn("is_staff", reponse.data)
        self.assertNotIn("is_superuser", reponse.data)
        self.assertNotIn("password", reponse.data)


class ContexteTest(APITestCase):
    """`/auth/contexte/` — l'écran de connexion doit savoir qui authentifie.

    Sinon il continue de demander un « identifiant » et laisse croire que le
    mot de passe se gère ici, alors que sous autorité de l'annuaire il ne peut
    ni être changé ni être réinitialisé dans BudgetTracker.
    """

    def test_lisible_sans_jeton(self):
        """Elle est lue **avant** la connexion : l'exiger authentifiée la rendrait
        inutilisable au seul moment où elle sert."""
        reponse = self.client.get("/api/v1/auth/contexte/")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertIn("autorite_externe", reponse.data)

    @override_settings(IDENTITE_AUTORITE=True)
    def test_signale_l_autorite_externe(self):
        reponse = self.client.get("/api/v1/auth/contexte/")
        self.assertIs(reponse.data["autorite_externe"], True)

    @override_settings(IDENTITE_AUTORITE=False)
    def test_signale_la_signature_locale(self):
        reponse = self.client.get("/api/v1/auth/contexte/")
        self.assertIs(reponse.data["autorite_externe"], False)

    @override_settings(IDENTITE_AUTORITE=True, IDENTITE_URL="http://interne:8003")
    def test_ne_divulgue_rien_d_autre(self):
        """Anonyme : elle dit quelle porte signe, jamais où elle est.

        Le navigateur ne parle jamais à l'annuaire (c'est l'intérêt du relais),
        il n'a donc aucun usage de son adresse — la publier dessinerait la
        topologie interne à un appelant non authentifié, pour rien.
        """
        reponse = self.client.get("/api/v1/auth/contexte/")
        self.assertEqual(set(reponse.data), {"autorite_externe"})


class CreerUtilisateurCommandeTest(APITestCase):
    """La porte d'entrée du déploiement : sans elle, l'app se verrouille dehors."""

    def test_cree_un_compte_utilisable(self):
        call_command("creer_utilisateur", nom="pierre", mot_de_passe=MOT_DE_PASSE)
        utilisateur = Utilisateur.objects.get(username="pierre")
        self.assertTrue(utilisateur.check_password(MOT_DE_PASSE))
        self.assertFalse(utilisateur.is_superuser)

    def test_relancer_repose_le_mot_de_passe(self):
        """Idempotente — c'est aussi la porte de secours si on l'a perdu."""
        call_command("creer_utilisateur", nom="pierre", mot_de_passe=MOT_DE_PASSE)
        call_command("creer_utilisateur", nom="pierre", mot_de_passe="un-autre-mdp-99")

        self.assertEqual(Utilisateur.objects.filter(username="pierre").count(), 1)
        self.assertTrue(
            Utilisateur.objects.get(username="pierre").check_password("un-autre-mdp-99")
        )

    def test_option_admin(self):
        call_command(
            "creer_utilisateur", nom="chef", mot_de_passe=MOT_DE_PASSE, admin=True
        )
        utilisateur = Utilisateur.objects.get(username="chef")
        self.assertTrue(utilisateur.is_staff)
        self.assertTrue(utilisateur.is_superuser)

    def test_mot_de_passe_faible_refuse(self):
        """`AUTH_PASSWORD_VALIDATORS` était réglé mais jamais appelé : rien ne
        créait de compte. Le court-circuiter rendrait le réglage décoratif."""
        with self.assertRaises(CommandError):
            call_command("creer_utilisateur", nom="pierre", mot_de_passe="1234")
        self.assertFalse(Utilisateur.objects.filter(username="pierre").exists())

    def test_mot_de_passe_semblable_a_l_identifiant_refuse(self):
        """Le validateur de similarité ne se déclenche **que** si on lui passe
        un utilisateur. Sans `user=`, il s'abstient en silence et « pmourret_adm »
        passait comme mot de passe du compte « pmourret_adm » — la moitié du
        réglage était inopérante sans que rien ne le signale.
        """
        with self.assertRaises(CommandError):
            call_command(
                "creer_utilisateur",
                nom="pmourret_adm",
                mot_de_passe="pmourret_adm",
            )
        self.assertFalse(Utilisateur.objects.filter(username="pmourret_adm").exists())

    def test_email_deja_pris_refuse(self):
        """Un email identifie **un** compte, sinon la connexion serait ambiguë."""
        call_command(
            "creer_utilisateur",
            nom="pierre",
            mot_de_passe=MOT_DE_PASSE,
            email="commun@foyer.local",
        )
        with self.assertRaises(CommandError):
            call_command(
                "creer_utilisateur",
                nom="camille",
                mot_de_passe=MOT_DE_PASSE,
                email="COMMUN@foyer.local",  # la casse ne contourne pas
            )
        self.assertFalse(Utilisateur.objects.filter(username="camille").exists())


class ConnexionParEmailTest(APITestCase):
    """Le cas qui a bloqué la première mise en service : on tape son email."""

    def setUp(self):
        call_command(
            "creer_utilisateur",
            nom="pmourret_adm",
            mot_de_passe=MOT_DE_PASSE,
            email="pmourret_adm@foyer.local",
        )

    def connecter(self, identifiant):
        return self.client.post(
            "/api/v1/auth/token/",
            {"username": identifiant, "password": MOT_DE_PASSE},
        )

    def test_connexion_par_email(self):
        self.assertEqual(
            self.connecter("pmourret_adm@foyer.local").status_code,
            status.HTTP_200_OK,
        )

    def test_connexion_par_identifiant_toujours_valable(self):
        """Ajouter une voie n'en ferme pas une autre."""
        self.assertEqual(
            self.connecter("pmourret_adm").status_code, status.HTTP_200_OK
        )

    def test_email_insensible_a_la_casse(self):
        self.assertEqual(
            self.connecter("PMourret_Adm@Foyer.Local").status_code,
            status.HTTP_200_OK,
        )

    def test_email_inconnu_refuse_sans_rien_dire(self):
        """401 comme pour un mot de passe faux : on ne révèle aucune existence."""
        reponse = self.connecter("inconnu@foyer.local")
        self.assertEqual(reponse.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("inconnu", str(reponse.data))

    def test_mauvais_mot_de_passe_par_email_refuse(self):
        reponse = self.client.post(
            "/api/v1/auth/token/",
            {"username": "pmourret_adm@foyer.local", "password": "faux"},
        )
        self.assertEqual(reponse.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_un_identifiant_contenant_un_arobase_reste_utilisable(self):
        """On ne devine pas à la présence d'un « @ ».

        C'est exactement le compte qu'on avait tenté de créer au départ : son
        identifiant *ressemble* à une adresse. Une résolution qui traiterait
        tout « @ » comme un email le rendrait inaccessible.
        """
        call_command(
            "creer_utilisateur",
            nom="bizarre@interne",
            mot_de_passe=MOT_DE_PASSE,
        )
        self.assertEqual(
            self.connecter("bizarre@interne").status_code, status.HTTP_200_OK
        )

    def test_l_unicite_de_l_email_est_garantie_en_base(self):
        """La contrainte tient même si personne ne passe par la commande.

        C'est le point de la migration : un email posé par l'admin Django ou par
        un shell ne doit pas pouvoir rendre la connexion ambiguë.
        """
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Utilisateur.objects.create_user(
                    username="doublon", password=MOT_DE_PASSE,
                    email="PMOURRET_ADM@foyer.local",
                )

    def test_plusieurs_comptes_sans_email_restent_possibles(self):
        """L'index est partiel : l'email est facultatif, `''` n'est pas une clé."""
        Utilisateur.objects.create_user(username="a", password=MOT_DE_PASSE)
        Utilisateur.objects.create_user(username="b", password=MOT_DE_PASSE)
        self.assertEqual(Utilisateur.objects.filter(email="").count(), 2)
