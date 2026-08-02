"""Base commune des tests qui appellent l'API.

Depuis le durcissement (août 2026), une requête anonyme reçoit `401`. Les 33
classes de test qui existaient avant décrivent du **comportement métier**, pas de
l'authentification : les laisser tomber en 401 ne prouverait rien et masquerait
les vraies régressions derrière un mur d'échecs identiques.

⚠️ **L'authentification est posée dans `_pre_setup`, pas dans `setUp`.** C'est
délibéré : la quasi-totalité de ces classes définissent déjà leur propre `setUp`
et **n'appellent pas `super()`** — ce qui est sans conséquence tant que la classe
mère n'a rien à faire. Mettre l'authentification dans un `setUp` de base la
rendrait donc silencieusement inopérante partout, et il aurait fallu retoucher 33
corps de méthode en espérant n'en oublier aucun. `_pre_setup` est le point
d'accroche que Django appelle **avant** `setUp`, quoi que fasse la sous-classe :
on ne peut pas l'oublier.

L'authentification réelle — obtention du jeton, expiration, refus anonyme — est
testée pour elle-même dans `accounts/tests.py`. Ici on utilise
`force_authenticate`, qui court-circuite les classes d'authentification : c'est
le bon outil pour un test qui parle d'autre chose.
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class APIAuthTestCase(APITestCase):
    """`APITestCase` dont le client porte un utilisateur authentifié."""

    def _pre_setup(self):
        super()._pre_setup()
        self.utilisateur = get_user_model().objects.create_user(
            username="tests", password="mot-de-passe-de-tests-42"
        )
        self.client.force_authenticate(self.utilisateur)
