"""Authentification de BudgetTracker — durcissement (août 2026).

L'app `accounts` existait depuis l'origine sans modèle, sans vue et sans test :
l'auth était repoussée à la phase de durcissement. Elle y est.

**Aucun modèle ajouté** : `AUTH_USER_MODEL` reste le `User` de Django. Le
basculer sur un modèle sur mesure alors que l'application tourne sur des données
réelles est l'opération la plus risquée de Django, et elle n'apporterait rien
ici — BudgetTracker ne rattache aucun objet métier à un utilisateur
(`Compte.titulaire` pointe un *référentiel*, pas un compte de connexion). La
divergence avec FoyerOS, qui s'identifie par email, est **assumée et
documentée** : c'est au futur service d'identité partagé de la résoudre, pas à
ce chantier.
"""
import jwt
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from providers.identite import (
    AnnuaireIndisponible,
    AnnuaireRefuse,
    obtenir_jetons,
    rafraichir_jetons,
    revoquer,
)

from .serializers import ConnexionSerializer, UtilisateurSerializer


def _relayer(appel):
    """Traduit les réponses de l'annuaire, en distinguant **refus et panne**.

    Un mot de passe faux et un annuaire éteint ne se disent pas pareil : le
    premier appelle à retaper, le second à attendre. C'est la même distinction
    que porte déjà `api/client.js` côté front, et pour la même raison.
    """
    try:
        return Response(appel())
    except AnnuaireRefuse as refus:
        return Response(
            refus.detail or {"detail": "Identifiants refusés."}, status=refus.statut
        )
    except AnnuaireIndisponible:
        return Response(
            {"detail": "Service d'identité injoignable. Réessayez dans un instant."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _refuser_si_autre_foyer(reponse):
    """Refuse **à la connexion** un compte étranger à ce foyer.

    ⚠️ Ajouté le 2026-08-02, après l'avoir vécu : l'annuaire ne connaît pas
    `IDENTITE_FOYER`, il délivrait donc des jetons parfaitement valides à un
    membre d'un autre foyer. La connexion réussissait, puis **chaque** appel
    tombait en 401 — un écran qui s'ouvre et ne charge rien, sans un message
    qui explique pourquoi.

    Le contrôle existait déjà côté authentification (`accounts/annuaire.py`), et
    il y reste : c'est lui la garantie. Celui-ci ne fait que le dire **au moment
    où on peut encore comprendre**, et il ne remplace rien.
    """
    from accounts.annuaire import foyers_du_jeton

    foyer = getattr(settings, "IDENTITE_FOYER", "")
    acces = reponse.data.get("access") if isinstance(reponse.data, dict) else None
    if not foyer or not acces:
        return reponse

    # Signature déjà vérifiée par l'annuaire qui vient de l'émettre : on ne lit
    # ici que la charge utile, pour trancher une question d'aiguillage.
    try:
        charge = jwt.decode(acces, options={"verify_signature": False})
    except jwt.PyJWTError:
        # Jeton illisible : on ne bloque pas la connexion ici. **La garantie est
        # à l'authentification** (`accounts/annuaire.py`), qui vérifie la
        # signature à chaque requête ; ce contrôle-ci n'existe que pour donner
        # un message compréhensible au bon moment. Le faire échouer sur une
        # réponse inattendue transformerait une amélioration de confort en
        # panne de connexion.
        return reponse

    if str(foyer) in foyers_du_jeton(charge):
        return reponse

    return Response(
        {
            "detail": (
                "Ce compte n'appartient pas au foyer géré par cette instance "
                "de BudgetTracker."
            )
        },
        status=status.HTTP_403_FORBIDDEN,
    )


class ConnexionView(APIView):
    """`POST /api/v1/auth/token/` — locale, ou **relayée** vers l'annuaire.

    Sous `IDENTITE_AUTORITE`, BudgetTracker ne signe plus : il transmet à
    l'annuaire et rend ses jetons. **Le front ne change pas** — il appelle la
    même URL et ignore la différence ; envoyer le navigateur vers l'annuaire
    aurait imposé du CORS et une seconde origine, pour le même résultat.

    ⚠️ Ce relais n'est **pas** l'appel réseau que le cadrage interdit : cette
    règle porte sur la *vérification*, qui reste locale par clé publique. Ici
    c'est l'*émission*, une fois par session.

    ⚠️ Sous autorité, l'identifiant est **l'email** : c'est ce que l'annuaire
    connaît. Se connecter par `username` reste possible tant que l'autorité
    n'est pas basculée, et par l'admin Django ensuite (porte de secours).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not settings.IDENTITE_AUTORITE:
            return TokenObtainPairView.as_view(serializer_class=ConnexionSerializer)(
                request._request
            )

        reponse = _relayer(
            lambda: obtenir_jetons(
                email=request.data.get("username", ""),
                mot_de_passe=request.data.get("password", ""),
            )
        )
        if reponse.status_code != status.HTTP_200_OK:
            return reponse
        return _refuser_si_autre_foyer(reponse)


class DeconnexionView(APIView):
    """`POST /api/v1/auth/deconnexion/ {refresh}` — révoque la session.

    Relayée vers l'annuaire, qui tient la liste noire. **Toujours `204`** : une
    session qu'on n'a pas pu révoquer côté serveur doit quand même se fermer
    côté navigateur — refuser laisserait quelqu'un connecté sur un poste qu'il
    quitte, le pire des deux échecs.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh and settings.IDENTITE_AUTORITE:
            try:
                revoquer(refresh=refresh)
            except (AnnuaireRefuse, AnnuaireIndisponible):
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class RafraichissementView(APIView):
    """Le refresh part **au même émetteur** que l'access.

    Un jeton signé par l'annuaire ne se renouvelle que là-bas : BudgetTracker
    n'a pas sa clé privée, et c'est précisément l'intérêt de RS256.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not settings.IDENTITE_AUTORITE:
            return TokenRefreshView.as_view()(request._request)
        return _relayer(
            lambda: rafraichir_jetons(refresh=request.data.get("refresh", ""))
        )


class MoiView(APIView):
    """`GET /api/v1/auth/me/` — qui porte ce jeton.

    Le front s'en sert au démarrage pour distinguer « jeton encore valide » de
    « jeton expiré », sans avoir à interpréter un 401 tombé d'une route métier.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UtilisateurSerializer(request.user).data)
