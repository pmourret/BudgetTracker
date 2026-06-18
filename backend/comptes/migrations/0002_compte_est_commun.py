from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comptes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='compte',
            name='est_commun',
            field=models.BooleanField(
                default=False,
                help_text='Compte partagé du foyer (joint) — affiché avec un indicateur dédié.',
            ),
        ),
    ]
