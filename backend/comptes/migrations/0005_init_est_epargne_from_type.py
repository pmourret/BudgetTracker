from django.db import migrations


def initialiser_est_epargne(apps, schema_editor):
    """
    Bootstrap ponctuel : marque `est_epargne=True` les comptes existants dont
    le type de compte est « EPARGNE » (type seedé par `seed_referentiels`).

    Amorçage de données uniquement — la logique applicative ne dépend PAS de
    ce code de type (règle 1) : elle lit exclusivement le flag `est_epargne`.
    """
    Compte = apps.get_model("comptes", "Compte")
    Compte.objects.filter(type_compte__code="EPARGNE").update(est_epargne=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("comptes", "0004_compte_est_epargne_compte_taux_annuel"),
    ]

    operations = [
        migrations.RunPython(initialiser_est_epargne, noop),
    ]
