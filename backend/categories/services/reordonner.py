"""
Service de réordonnancement manuel des catégories.

Le tri par défaut est alphabétique (`ordering = ["ordre", "nom"]` avec
`ordre=0` partout). Dès que l'utilisateur réordonne un groupe de catégories
sœurs par glisser-déposer, on persiste leur position dans `ordre` (1, 2, 3…).

Logique pure et atomique : la view se contente d'appeler ce service.
"""
from django.db import transaction


def reordonner_categories(ids, CategorieModel=None):
    """
    Réassigne le champ `ordre` des catégories selon l'ordre de la liste `ids`.

    Chaque catégorie reçoit `ordre = index + 1` (1-based ; 0 reste la valeur
    par défaut « non réordonné », qui retombe sur le tri alphabétique).

    Le réordonnancement est attendu *intra-groupe* (entre sœurs : majeures
    entre elles, ou mineures d'une même majeure) — le service ne le vérifie
    pas, il applique simplement les positions reçues.

    Args:
        ids: liste d'identifiants de catégories dans l'ordre voulu.
        CategorieModel: injectable pour les tests.

    Returns:
        Le nombre de catégories effectivement mises à jour.

    Raises:
        ValueError: si un identifiant ne correspond à aucune catégorie.
    """
    if CategorieModel is None:
        from categories.models import Categorie
        CategorieModel = Categorie

    if not ids:
        return 0

    categories = {
        str(c.id): c
        for c in CategorieModel.objects.filter(id__in=ids)
    }

    manquants = [str(i) for i in ids if str(i) not in categories]
    if manquants:
        raise ValueError(
            f"Catégorie(s) introuvable(s) : {', '.join(manquants)}"
        )

    with transaction.atomic():
        for index, cat_id in enumerate(ids, start=1):
            cat = categories[str(cat_id)]
            if cat.ordre != index:
                cat.ordre = index
                cat.save(update_fields=["ordre", "updated_at"])

    return len(ids)
