import datetime

from django.test import TestCase
from core.models import BaseModel, SoftDeleteManager, SoftDeleteQuerySet
from core.services.periode import bornes_mois_comptable, mois_comptable


class BaseModelMetaTest(TestCase):
    """Vérifie que BaseModel est bien abstrait et correctement configuré."""

    def test_est_abstrait(self):
        self.assertTrue(BaseModel._meta.abstract)

    def test_champs_presents(self):
        champs = [f.name for f in BaseModel._meta.fields]
        self.assertIn("id", champs)
        self.assertIn("created_at", champs)
        self.assertIn("updated_at", champs)
        self.assertIn("is_deleted", champs)

    def test_manager_par_defaut(self):
        # Sur un modèle abstrait, on vérifie la déclaration du manager
        # via _meta.managers rather than l'accès direct à .objects
        manager_classes = [
            type(m) for m in BaseModel._meta.managers
        ]
        self.assertIn(SoftDeleteManager, manager_classes)


def D(y, m, d):
    return datetime.date(y, m, d)


class MoisComptableTest(TestCase):
    """Fonction pure de découpage en mois comptables."""

    def test_jour_1_equivaut_au_calendrier(self):
        # jour <= 1 : comportement historique, toute date → 1er calendaire.
        for jour in (0, 1):
            self.assertEqual(mois_comptable(D(2026, 6, 27), jour), D(2026, 6, 1))
            self.assertEqual(mois_comptable(D(2026, 6, 1), jour), D(2026, 6, 1))
            self.assertEqual(mois_comptable(D(2026, 6, 30), jour), D(2026, 6, 1))

    def test_bascule_25_avant_le_jour(self):
        # Jour < 25 → mois calendaire courant.
        self.assertEqual(mois_comptable(D(2026, 6, 20), 25), D(2026, 6, 1))
        self.assertEqual(mois_comptable(D(2026, 7, 10), 25), D(2026, 7, 1))
        self.assertEqual(mois_comptable(D(2026, 6, 24), 25), D(2026, 6, 1))

    def test_bascule_25_a_partir_du_jour(self):
        # Jour >= 25 → bascule sur le mois suivant (le mois financé).
        self.assertEqual(mois_comptable(D(2026, 6, 25), 25), D(2026, 7, 1))
        self.assertEqual(mois_comptable(D(2026, 6, 27), 25), D(2026, 7, 1))
        self.assertEqual(mois_comptable(D(2026, 6, 30), 25), D(2026, 7, 1))

    def test_bascule_passage_annee(self):
        # Décembre → bascule sur janvier de l'année suivante.
        self.assertEqual(mois_comptable(D(2026, 12, 28), 25), D(2027, 1, 1))
        self.assertEqual(mois_comptable(D(2026, 12, 20), 25), D(2026, 12, 1))

    def test_meme_periode_salaire_et_debut_mois_suivant(self):
        # 27 juin (salaire) et 10 juillet (dépenses) tombent dans le même
        # mois comptable « juillet ».
        self.assertEqual(
            mois_comptable(D(2026, 6, 27), 25),
            mois_comptable(D(2026, 7, 10), 25),
        )

    def test_mois_courts_jour_28(self):
        # Jour de bascule borné à 28 : valide même en février.
        self.assertEqual(mois_comptable(D(2026, 2, 28), 28), D(2026, 3, 1))
        self.assertEqual(mois_comptable(D(2026, 2, 27), 28), D(2026, 2, 1))


class BornesMoisComptableTest(TestCase):
    """Bornes (début, fin) d'une période comptable."""

    def test_jour_1_bornes_calendaires(self):
        debut, fin = bornes_mois_comptable(D(2026, 6, 1), 1)
        self.assertEqual(debut, D(2026, 6, 1))
        self.assertEqual(fin, D(2026, 6, 30))

    def test_bascule_25_bornes(self):
        # Mois comptable « juillet » = 25 juin → 24 juillet.
        debut, fin = bornes_mois_comptable(D(2026, 7, 1), 25)
        self.assertEqual(debut, D(2026, 6, 25))
        self.assertEqual(fin, D(2026, 7, 24))

    def test_bornes_coherentes_avec_mapping(self):
        # Toute date de la période est bien mappée sur le label.
        label = D(2026, 7, 1)
        debut, fin = bornes_mois_comptable(label, 25)
        for d in (debut, D(2026, 6, 30), D(2026, 7, 1), fin):
            self.assertEqual(mois_comptable(d, 25), label)
        # Les bords extérieurs basculent sur les périodes voisines.
        self.assertNotEqual(mois_comptable(debut - datetime.timedelta(days=1), 25), label)
        self.assertNotEqual(mois_comptable(fin + datetime.timedelta(days=1), 25), label)