"""Lanceur de tests — neutralise les réglages de déploiement.

Motif, vécu côté FoyerOS à la livraison de l'étape 3b : poser
`IDENTITE_AUTORITE=True` dans le `.env` y a fait **échouer 48 tests d'un coup**,
la suite se mettant à appeler le vrai service d'identité par le réseau. Le code
était bon ; c'est la suite qui dépendait d'un réglage de machine. On ferme la
porte ici avant de la rencontrer.

**Un test ne décrit jamais l'état d'un déploiement.** Le mode « annuaire fait
autorité » est exercé par les tests qui le demandent, via `override_settings`.
"""
from django.test.runner import DiscoverRunner


class LanceurBudgetTracker(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)

        from django.conf import settings

        settings.IDENTITE_AUTORITE = False
        # Injoignable : un appel oublié échoue vite et bruyamment, plutôt que
        # d'attendre un timeout sur une vraie adresse.
        settings.IDENTITE_URL = ""
        # ⚠️ **Tout** le bloc identité, pas seulement l'interrupteur. Oublier le
        # foyer et la clé laissait des tests passer pour de mauvaises raisons —
        # ou échouer selon le `.env` de la machine.
        settings.IDENTITE_FOYER = ""
        settings.IDENTITE_CLE_PUBLIQUE = ""
