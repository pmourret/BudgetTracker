"""Rend l'email unique sur `auth_user` — préalable à la connexion par email.

Sans cette contrainte, deux comptes peuvent porter la même adresse et
« se connecter avec son email » n'a pas de sens : le serveur devrait choisir.
On ferme la porte en base plutôt qu'en Python, parce qu'une règle d'unicité
appliquée seulement à la création se contourne par l'admin Django, par un shell,
ou par le prochain code qui créera un compte sans repasser par le service.

Trois choix portés par l'index :

- **`LOWER(email)`** — « Pierre@… » et « pierre@… » sont la même boîte. Sans ça
  l'unicité serait contournable par une majuscule, et la connexion resterait
  ambiguë ;
- **`WHERE email <> ''`** — l'email est facultatif sur le `User` de Django et
  vaut `''` par défaut. Un index total interdirait un **second** compte sans
  adresse, ce qui n'a aucun rapport avec ce qu'on cherche à garantir ;
- **`RunSQL` et non `AddConstraint`** — le modèle appartient à
  `django.contrib.auth` ; on ajoute un index à sa table sans prétendre modifier
  sa définition, ce que les migrations de l'app `auth` reprendraient.

⚠️ Cette migration **échoue si des doublons existent déjà**, et c'est voulu :
les fusionner demande de savoir lequel garder, ce qu'une migration ne peut pas
deviner. Le cas échéant, corriger les comptes puis rejouer.
"""
from django.conf import settings
from django.db import migrations

NOM = "auth_user_email_unique_ci"

CREER = f"""
CREATE UNIQUE INDEX {NOM}
    ON auth_user (LOWER(email))
    WHERE email <> '';
"""

SUPPRIMER = f"DROP INDEX IF EXISTS {NOM};"


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(sql=CREER, reverse_sql=SUPPRIMER),
    ]
