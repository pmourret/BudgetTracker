"""Client HTTP du service d'identité — **émission de jetons, et rien d'autre.**

⚠️ **BudgetTracker n'administre pas l'annuaire.** Contrairement à FoyerOS, il n'a
ici ni compte de service, ni fonction de création de compte : il ne fait que
relayer une connexion. Les comptes naissent dans FoyerOS, qui porte les écrans
d'administration (cadrage §2.2). Ne pas ajouter de fonction d'écriture ici sans
rouvrir cette décision — ce serait donner à une seconde application le pouvoir
de refaire l'annuaire.

Rappel de la frontière : la **vérification** d'un jeton est locale, par clé
publique (`accounts/annuaire.py`), et ne passe jamais par ce module. C'est ce qui
permet à BudgetTracker de tourner quand l'annuaire est éteint.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings


class AnnuaireIndisponible(Exception):
    """L'annuaire n'a pas répondu. **Ce n'est pas un refus.**

    Même distinction que dans `api/client.js` : confondre une panne avec un
    refus fait rejouer le mauvais geste — ici, cela afficherait « mot de passe
    incorrect » pendant un redéploiement.
    """


class AnnuaireRefuse(Exception):
    def __init__(self, statut, detail):
        self.statut = statut
        self.detail = detail
        super().__init__(f"{statut}: {detail}")


def _appeler(chemin, charge):
    base = getattr(settings, "IDENTITE_URL", "").rstrip("/")
    if not base:
        raise AnnuaireIndisponible("IDENTITE_URL n'est pas configurée.")

    requete = urllib.request.Request(
        f"{base}{chemin}",
        data=json.dumps(charge).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            requete, timeout=getattr(settings, "IDENTITE_TIMEOUT", 5)
        ) as reponse:
            corps = reponse.read()
            return json.loads(corps) if corps else {}
    except urllib.error.HTTPError as erreur:
        try:
            detail = json.loads(erreur.read() or b"{}")
        except ValueError:
            detail = {}
        raise AnnuaireRefuse(erreur.code, detail)
    except (urllib.error.URLError, TimeoutError, OSError) as erreur:
        raise AnnuaireIndisponible(str(erreur))


def obtenir_jetons(*, email, mot_de_passe):
    return _appeler("/api/v1/auth/token/", {"email": email, "password": mot_de_passe})


def rafraichir_jetons(*, refresh):
    return _appeler("/api/v1/auth/token/refresh/", {"refresh": refresh})


def revoquer(*, refresh):
    """Met la session sur liste noire côté annuaire.

    Sans cet appel, se déconnecter n'efface que les jetons du navigateur : le
    refresh reste valable ses 7 jours.
    """
    return _appeler("/api/v1/auth/deconnexion/", {"refresh": refresh})
