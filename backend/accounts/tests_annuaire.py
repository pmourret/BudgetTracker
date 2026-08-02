"""Étape 4 — BudgetTracker vérifie les jetons du service d'identité.

Trois propriétés portent tout :

1. **l'étanchéité inter-foyers** — une instance par foyer, et le claim `foyers`
   est la seule chose qui permette de refuser un membre du foyer voisin ;
2. **le provisionnement retrouve, il ne duplique pas** — le rapprochement se
   fait sur l'email, seule clé commune entre un `sub` UUID et un `auth.User` à
   clé entière ;
3. **rien de l'existant ne casse** tant que l'autorité n'est pas basculée.
"""
from datetime import datetime, timedelta, timezone as tz
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from providers.identite import AnnuaireIndisponible, AnnuaireRefuse

User = get_user_model()

_CLE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVEE = _CLE.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
PUBLIQUE = _CLE.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

FOYER_ICI = "edaa8d5c-0a83-44c4-ba35-0dfa3b6f4f22"
FOYER_AILLEURS = "11111111-2222-3333-4444-555555555555"


def jeton(foyers=None, **surcharges):
    claims = {
        "sub": "7eb1cf72-1a01-4e1a-b2df-b7d1c08f9625",
        "email": "camille@foyer.local",
        "prenom": "Camille",
        "technique": False,
        "foyers": [{"id": FOYER_ICI, "nom": "Foyer A"}] if foyers is None else foyers,
        "exp": datetime.now(tz.utc) + timedelta(minutes=30),
        "iat": datetime.now(tz.utc),
    }
    claims.update(surcharges)
    return jwt.encode(claims, PRIVEE, algorithm="RS256")


@override_settings(IDENTITE_CLE_PUBLIQUE=PUBLIQUE, IDENTITE_FOYER=FOYER_ICI)
class VerificationTest(APITestCase):
    def porter(self, brut):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {brut}")

    def test_un_jeton_de_l_annuaire_ouvre_l_application(self):
        self.porter(jeton())
        reponse = self.client.get("/api/v1/auth/me/")
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data["email"], "camille@foyer.local")

    def test_le_compte_local_est_cree_a_la_volee(self):
        """Trivial ici, et il faut savoir pourquoi : **aucune FK vers `User`**
        dans tout BudgetTracker. Un compte n'y est qu'une porte."""
        self.porter(jeton())
        self.client.get("/api/v1/auth/me/")
        compte = User.objects.get(email="camille@foyer.local")
        self.assertEqual(compte.first_name, "Camille")
        self.assertFalse(compte.has_usable_password())

    def test_un_compte_local_existant_est_retrouve_pas_duplique(self):
        """Le rapprochement se fait sur **l'email**, seule clé commune entre un
        `sub` UUID et un `auth.User` à clé primaire entière."""
        existant = User.objects.create_user(
            username="pierre", email="camille@foyer.local", password="x"
        )
        self.porter(jeton())
        self.client.get("/api/v1/auth/me/")

        self.assertEqual(User.objects.filter(email="camille@foyer.local").count(), 1)
        self.assertEqual(User.objects.get(pk=existant.pk).username, "pierre")

    def test_le_jeton_ouvre_les_ressources_metier(self):
        self.porter(jeton())
        self.assertEqual(
            self.client.get("/api/v1/flux/").status_code, status.HTTP_200_OK
        )

    # ------------------------------------------------------------------ #
    # L'étanchéité inter-foyers — la raison d'être du claim
    # ------------------------------------------------------------------ #
    def test_un_membre_d_un_autre_foyer_est_refuse(self):
        """Une instance par foyer : le BudgetTracker du foyer A ne s'ouvre pas
        à un membre du foyer B, même muni d'un jeton parfaitement valide."""
        self.porter(jeton(foyers=[{"id": FOYER_AILLEURS, "nom": "Foyer B"}]))
        self.assertEqual(
            self.client.get("/api/v1/auth/me/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertFalse(User.objects.filter(email="camille@foyer.local").exists())

    def test_un_jeton_sans_foyer_est_refuse(self):
        self.porter(jeton(foyers=[]))
        self.assertEqual(
            self.client.get("/api/v1/auth/me/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @override_settings(IDENTITE_FOYER="")
    def test_sans_foyer_configure_aucun_jeton_d_annuaire_n_est_accepte(self):
        """**Fermé par défaut.** Ne pas savoir de quel foyer on est l'instance
        n'autorise pas à accepter tout le monde — ce serait ouvrir la seule
        frontière que ce contrôle existe pour protéger."""
        self.porter(jeton())
        self.assertEqual(
            self.client.get("/api/v1/auth/me/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # ------------------------------------------------------------------ #
    def test_signature_invalide_refusee(self):
        autre = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = autre.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        faux = jwt.encode(
            {"email": "x@y.z", "foyers": [{"id": FOYER_ICI}],
             "exp": datetime.now(tz.utc) + timedelta(minutes=5)},
            pem, algorithm="RS256",
        )
        self.porter(faux)
        self.assertEqual(
            self.client.get("/api/v1/auth/me/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_jeton_expire_refuse(self):
        self.porter(jeton(exp=datetime.now(tz.utc) - timedelta(minutes=1)))
        self.assertEqual(
            self.client.get("/api/v1/auth/me/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


@override_settings(IDENTITE_CLE_PUBLIQUE=PUBLIQUE, IDENTITE_FOYER=FOYER_ICI)
class RienNeCasseTest(APITestCase):
    """Tant que l'autorité n'est pas basculée, l'existant continue."""

    def setUp(self):
        self.pierre = User.objects.create_user(
            username="pierre", email="pierre@foyer.local", password="mot-de-passe-42"
        )

    def test_la_connexion_locale_fonctionne_toujours(self):
        reponse = self.client.post(
            "/api/v1/auth/token/", {"username": "pierre", "password": "mot-de-passe-42"}
        )
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)

    def test_un_jeton_local_ouvre_toujours_l_application(self):
        """La classe de l'annuaire doit **s'abstenir** sur un jeton HS256 : DRF
        s'arrête à la première classe qui lève."""
        acces = self.client.post(
            "/api/v1/auth/token/", {"username": "pierre", "password": "mot-de-passe-42"}
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {acces}")
        self.assertEqual(
            self.client.get("/api/v1/auth/me/").status_code, status.HTTP_200_OK
        )

    def test_le_mot_de_passe_local_survit_au_provisionnement(self):
        brut = jeton(email="pierre@foyer.local", prenom="Pierre")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {brut}")
        self.client.get("/api/v1/auth/me/")

        self.pierre.refresh_from_db()
        self.assertTrue(self.pierre.check_password("mot-de-passe-42"))


@override_settings(IDENTITE_AUTORITE=True)
class ConnexionRelayeeTest(APITestCase):
    def test_la_connexion_est_relayee(self):
        jetons = {"access": jeton(), "refresh": "r"}
        with patch("accounts.views.obtenir_jetons") as appel:
            appel.return_value = jetons
            reponse = self.client.post(
                "/api/v1/auth/token/",
                {"username": "camille@foyer.local", "password": "x"},
            )
        self.assertEqual(reponse.data, jetons)
        appel.assert_called_once_with(email="camille@foyer.local", mot_de_passe="x")

    def test_un_jeton_illisible_ne_bloque_pas_la_connexion(self):
        """Le contrôle de foyer est un **confort de message**, pas la garantie.

        Celle-ci est à l'authentification, qui vérifie la signature à chaque
        requête. Faire échouer la connexion sur une réponse inattendue
        transformerait une amélioration en panne.
        """
        with patch("accounts.views.obtenir_jetons") as appel:
            appel.return_value = {"access": "pas-un-jeton", "refresh": "r"}
            reponse = self.client.post(
                "/api/v1/auth/token/", {"username": "x@y.z", "password": "x"}
            )
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)

    def test_aucun_jeton_n_est_signe_localement(self):
        User.objects.create_user(username="pierre", password="mot-de-passe-42")
        with patch("accounts.views.obtenir_jetons") as appel:
            appel.side_effect = AnnuaireRefuse(401, {"detail": "non"})
            reponse = self.client.post(
                "/api/v1/auth/token/",
                {"username": "pierre", "password": "mot-de-passe-42"},
            )
        self.assertEqual(reponse.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_une_panne_n_est_pas_un_refus(self):
        """503, jamais 401 : sinon un redéploiement s'affiche comme un mot de
        passe incorrect, et fait retaper pour rien."""
        with patch("accounts.views.obtenir_jetons") as appel:
            appel.side_effect = AnnuaireIndisponible("connexion refusée")
            reponse = self.client.post(
                "/api/v1/auth/token/", {"username": "a", "password": "b"}
            )
        self.assertEqual(reponse.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_le_rafraichissement_part_au_meme_emetteur(self):
        with patch("accounts.views.rafraichir_jetons") as appel:
            appel.return_value = {"access": "a2"}
            reponse = self.client.post("/api/v1/auth/token/refresh/", {"refresh": "r"})
        self.assertEqual(reponse.data["access"], "a2")

    @override_settings(IDENTITE_FOYER=FOYER_ICI)
    def test_un_membre_d_un_autre_foyer_est_refuse_des_la_connexion(self):
        """⚠️ Vécu le 2026-08-02 : l'annuaire ne connaît pas `IDENTITE_FOYER` et
        délivrait donc des jetons valides à un membre d'un autre foyer. La
        connexion réussissait, puis **chaque** appel tombait en 401 — un écran
        qui s'ouvre et ne charge rien, sans un mot d'explication."""
        with patch("accounts.views.obtenir_jetons") as appel:
            appel.return_value = {
                "access": jeton(foyers=[{"id": FOYER_AILLEURS, "nom": "Foyer B"}]),
                "refresh": "r",
            }
            reponse = self.client.post(
                "/api/v1/auth/token/", {"username": "x@y.z", "password": "x"}
            )

        self.assertEqual(reponse.status_code, status.HTTP_403_FORBIDDEN)
        # Le message est destiné à être lu : il dit *pourquoi*, pas « erreur ».
        self.assertIn("foyer", reponse.data["detail"].lower())

    @override_settings(IDENTITE_FOYER=FOYER_ICI)
    def test_un_membre_de_ce_foyer_passe(self):
        with patch("accounts.views.obtenir_jetons") as appel:
            appel.return_value = {"access": jeton(), "refresh": "r"}
            reponse = self.client.post(
                "/api/v1/auth/token/", {"username": "x@y.z", "password": "x"}
            )
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)


class InterrupteurTest(APITestCase):
    """`IDENTITE_AUTORITE=False` rend exactement le comportement d'avant."""

    def test_la_connexion_locale_revient(self):
        User.objects.create_user(username="pierre", password="mot-de-passe-42")
        reponse = self.client.post(
            "/api/v1/auth/token/", {"username": "pierre", "password": "mot-de-passe-42"}
        )
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertIn("access", reponse.data)
