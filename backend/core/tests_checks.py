"""Le garde-fou de `SECRET_KEY` doit **bloquer** hors développement.

La propriété qui compte n'est pas « le contrôle existe » mais « son niveau
change avec l'environnement » : un *warning* passe
`check --deploy --fail-level ERROR`, donc les 20 octets de cette application
seraient partis en production sans que rien ne les arrête.
"""
from django.core.checks import Error, Warning
from django.test import SimpleTestCase, override_settings

from core.checks import verifier_cle_de_signature

FAIBLE = "trop-courte"
REPLI = "django-insecure-dev-only"
SOLIDE = "z" * 64


class GardeFouSecretTest(SimpleTestCase):
    def anomalies(self, **reglages):
        with override_settings(**reglages):
            return verifier_cle_de_signature(None)

    def test_bloque_une_cle_courte_en_production(self):
        self.assertEqual(
            [type(a) for a in self.anomalies(DEBUG=False, SECRET_KEY=FAIBLE)], [Error]
        )

    def test_bloque_la_cle_de_repli_en_production(self):
        self.assertEqual(
            [type(a) for a in self.anomalies(DEBUG=False, SECRET_KEY=REPLI)], [Error]
        )

    def test_avertit_seulement_en_developpement(self):
        self.assertEqual(
            [type(a) for a in self.anomalies(DEBUG=True, SECRET_KEY=FAIBLE)], [Warning]
        )

    def test_une_cle_solide_ne_dit_rien(self):
        self.assertEqual(self.anomalies(DEBUG=False, SECRET_KEY=SOLIDE), [])
