"""Vérification des jetons du service d'identité — étape 4 du cadrage.

BudgetTracker devient **vérificateur** : il lit les jetons signés par l'annuaire
avec sa clé publique, et ne lui parle jamais pour ça (cadrage §3.1). Il continue
d'accepter ses propres jetons tant que `IDENTITE_AUTORITE` est à `False` — même
double régime qu'en 3a côté FoyerOS, et pour la même raison : la bascule doit
être un réglage, pas un déploiement.

**Le provisionnement est trivial ici, et il faut savoir pourquoi** : BudgetTracker
n'a **aucune clé étrangère vers `User`** (vérifié au cadrage). Un compte n'y est
qu'une porte ; le créer à la volée ne laisse aucune donnée orpheline et n'oblige
à rapprocher quoi que ce soit.

⚠️ **Le rapprochement se fait sur l'email**, pas sur `sub`. `auth.User` a une clé
primaire entière, elle ne peut pas porter l'UUID de l'annuaire. L'email est
l'identifiant de connexion depuis août 2026 et porte une contrainte d'unicité
insensible à la casse — c'est la seule clé commune fiable entre les deux mondes.
Conséquence heureuse : un compte local existant (`pierre`) est **retrouvé**, pas
dupliqué, dès que l'annuaire présente la même adresse.
"""
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions

ALGORITHME = "RS256"
PREFIXE = "Bearer"


def foyers_du_jeton(claims):
    return {
        (f.get("id") if isinstance(f, dict) else f)
        for f in (claims.get("foyers") or [])
    }


def provisionner(claims):
    """Retrouve ou crée le compte local correspondant au porteur du jeton."""
    User = get_user_model()
    email = (claims.get("email") or "").lower()
    if not email:
        return None

    compte = User.objects.filter(email__iexact=email).first()
    if compte is None:
        compte = User.objects.create(
            # L'email fait office d'identifiant : `ConnexionSerializer` sait déjà
            # se connecter par l'un ou l'autre, et cela évite d'inventer un nom
            # court qui entrerait en collision.
            username=email[: User._meta.get_field("username").max_length],
            email=email,
            first_name=claims.get("prenom") or "",
        )
        # Aucun mot de passe local : on ne s'authentifie qu'à un seul endroit.
        compte.set_unusable_password()
        compte.save(update_fields=["password"])
    else:
        prenom = claims.get("prenom") or ""
        if prenom and compte.first_name != prenom:
            compte.first_name = prenom
            compte.save(update_fields=["first_name"])
    return compte


class JetonAnnuaire(authentication.BaseAuthentication):
    """Vérifie un jeton de l'annuaire et contrôle qu'il porte **ce** foyer.

    ⚠️ **Renvoie `None` quand le jeton n'est pas pour elle.** DRF s'arrête à la
    première classe qui **lève** : refuser ce qu'on ne reconnaît pas empêcherait
    `JWTAuthentication` d'examiner les jetons locaux, et déconnecterait tout le
    monde. Le tri se fait sur l'algorithme — BudgetTracker signe en HS256.
    """

    def authenticate(self, request):
        brut = self._jeton_brut(request)
        if brut is None:
            return None

        try:
            entete = jwt.get_unverified_header(brut)
        except jwt.PyJWTError:
            return None
        if entete.get("alg") != ALGORITHME:
            return None

        cle = getattr(settings, "IDENTITE_CLE_PUBLIQUE", "")
        foyer = getattr(settings, "IDENTITE_FOYER", "")
        if not cle or not foyer:
            # **Fermé par défaut.** Sans clé, ou sans savoir de quel foyer cette
            # instance est celle, on ne peut pas juger l'appartenance — et
            # accepter « au cas où » ouvrirait l'étanchéité inter-foyers, la
            # seule chose que ce contrôle existe pour protéger.
            return None

        try:
            claims = jwt.decode(brut, cle, algorithms=[ALGORITHME])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed(_("Jeton expiré."), "token_expired")
        except jwt.PyJWTError:
            raise exceptions.AuthenticationFailed(_("Jeton invalide."), "token_invalid")

        if claims.get("service"):
            # Identifiant **machine** : il administre l'annuaire, il n'ouvre
            # aucune application. BudgetTracker n'en a même pas — c'est FoyerOS
            # qui administre — raison de plus pour ne pas en accepter un ici.
            raise exceptions.AuthenticationFailed(
                _("Un compte de service ne se connecte pas à l'application."),
                "compte_de_service",
            )

        if str(foyer) not in foyers_du_jeton(claims):
            # Un membre du foyer B devant le BudgetTracker du foyer A. C'est
            # exactement le cas que le claim `foyers` existe pour attraper.
            raise exceptions.AuthenticationFailed(
                _("Ce compte n'appartient pas au foyer de cette instance."),
                "foyer_etranger",
            )

        compte = provisionner(claims)
        if compte is None:
            raise exceptions.AuthenticationFailed(_("Jeton sans email."), "no_email")
        if not compte.is_active:
            raise exceptions.AuthenticationFailed(_("Compte inactif."), "user_inactive")

        request.claims_annuaire = claims
        return (compte, brut)

    def authenticate_header(self, request):
        return PREFIXE

    @staticmethod
    def _jeton_brut(request):
        entete = authentication.get_authorization_header(request).split()
        if len(entete) != 2 or entete[0].lower() != PREFIXE.lower().encode():
            return None
        return entete[1].decode()
