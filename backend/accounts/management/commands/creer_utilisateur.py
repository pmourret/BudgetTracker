"""Crée ou met à jour un compte de connexion, **sans invite interactive**.

`createsuperuser` existe déjà, mais il pose des questions : inutilisable dans un
`docker compose exec` de déploiement, dans un script, ou dans le `entrypoint` de
production. Or au moment précis où l'API se ferme (durcissement, août 2026), il
n'existe **aucun** compte : sans cette commande, l'application se verrouille
elle-même dehors et seul un accès direct à la base la rattrape.

    python manage.py creer_utilisateur --nom pierre --mot-de-passe '…'
    python manage.py creer_utilisateur --nom pierre --mot-de-passe '…' \
        --email pierre@foyer.local --admin

`--nom` **et** `--email` permettent tous deux de se connecter (cf.
`accounts/serializers.py::ConnexionSerializer`) ; l'email est facultatif, mais un
compte sans adresse ne se connecte que par son identifiant.

**Idempotente** : relancée sur un compte existant, elle repose le mot de passe
plutôt que d'échouer — c'est aussi la porte de secours quand on l'a perdu.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée un compte de connexion (ou repose son mot de passe)."

    def add_arguments(self, parseur):
        parseur.add_argument("--nom", required=True, help="Identifiant de connexion.")
        parseur.add_argument("--mot-de-passe", required=True, dest="mot_de_passe")
        parseur.add_argument("--email", default="")
        parseur.add_argument(
            "--admin",
            action="store_true",
            help="Donne aussi l'accès à l'admin Django (staff + superuser).",
        )

    def handle(self, *args, **options):
        Utilisateur = get_user_model()
        nom = options["nom"].strip()
        mot_de_passe = options["mot_de_passe"]
        email = options["email"].strip()

        # L'email sert à se connecter (`ConnexionSerializer`) : il doit désigner
        # **un** compte. La base le garantit (`0001_email_unique`) ; on le
        # vérifie ici seulement pour remplacer une `IntegrityError` illisible par
        # une phrase. La garantie reste en base, pas dans ce contrôle.
        if email:
            occupant = (
                Utilisateur.objects.filter(email__iexact=email)
                .exclude(username=nom)
                .values_list("username", flat=True)
                .first()
            )
            if occupant:
                raise CommandError(
                    f"L'adresse « {email} » est déjà celle du compte "
                    f"« {occupant} ». Un email identifie un seul compte."
                )

        # Les validateurs sont ceux de `AUTH_PASSWORD_VALIDATORS`, déjà réglés
        # dans `base.py` mais jusqu'ici jamais appelés : rien ne créait de compte.
        # Les court-circuiter ici rendrait le réglage décoratif.
        #
        # ⚠️ **`user=` est obligatoire**, et son oubli ne se voit pas :
        # `UserAttributeSimilarityValidator` compare le mot de passe aux
        # attributs du compte, donc sans instance il ne compare rien et
        # s'abstient **en silence**. « pmourret_adm » passait comme mot de passe
        # du compte « pmourret_adm ». Un compte à créer n'existe pas encore : on
        # passe une instance non enregistrée, comme le fait
        # `FoyerOS/accounts/services/comptes.py`.
        provisoire = Utilisateur(username=nom, email=email)
        try:
            validate_password(mot_de_passe, user=provisoire)
        except ValidationError as erreur:
            raise CommandError(" ".join(erreur.messages))

        utilisateur, cree = Utilisateur.objects.get_or_create(
            username=nom, defaults={"email": email}
        )
        # Relancée avec un email, la commande le pose : c'est ainsi qu'on ajoute
        # une adresse de connexion à un compte créé sans.
        if email and utilisateur.email != email:
            utilisateur.email = email
        utilisateur.set_password(mot_de_passe)
        if options["admin"]:
            utilisateur.is_staff = True
            utilisateur.is_superuser = True
        utilisateur.save()

        verbe = "créé" if cree else "mis à jour"
        self.stdout.write(self.style.SUCCESS(f"Compte « {nom} » {verbe}."))
