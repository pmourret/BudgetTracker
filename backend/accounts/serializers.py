from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class ConnexionSerializer(TokenObtainPairSerializer):
    """Connexion par **email ou identifiant**, au choix.

    `USERNAME_FIELD` vaut `username` (on ne touche pas à `AUTH_USER_MODEL` sur
    une base réelle — cf. §5). Mais personne ne retient un identifiant technique
    quand FoyerOS, l'autre application de la suite, se connecte par email : le
    premier compte créé ici s'est fait refuser pour cette raison exacte. On
    traduit donc l'email en identifiant **avant** de laisser SimpleJWT
    authentifier ; le reste de la mécanique est inchangé.

    ⚠️ **On ne devine pas à la présence d'un `@`.** Un identifiant *peut* en
    contenir — c'est précisément ce qu'on avait tenté de créer. La règle est
    donc : si un compte porte cette adresse, on prend son identifiant ; sinon on
    laisse la saisie telle quelle et elle est essayée comme identifiant. Les deux
    voies fonctionnent, et aucune n'en écrase une autre.

    **Aucune fuite d'information** : une adresse inconnue n'est pas signalée, la
    saisie passe simplement à l'authentification normale, qui répond 401 comme
    pour un mot de passe faux. On ne dit jamais « ce compte n'existe pas ».

    L'unicité de l'email est garantie **en base** (`accounts/0001_email_unique`),
    pas ici : c'est ce qui rend cette résolution non ambiguë.
    """

    def validate(self, attrs):
        saisie = attrs.get(self.username_field, "")
        if saisie:
            compte = (
                get_user_model()
                .objects.filter(email__iexact=saisie)
                .values_list(self.username_field, flat=True)
                .first()
            )
            if compte:
                attrs[self.username_field] = compte
        return super().validate(attrs)


class UtilisateurSerializer(serializers.ModelSerializer):
    """Le porteur du jeton, et rien d'autre.

    Sert au front à savoir qui est connecté après un rechargement de page : le
    jeton est opaque côté navigateur, l'écran a besoin d'un nom à afficher.

    ⚠️ **`is_staff` et `is_superuser` ne sont pas exposés.** Un écran qui décide
    de ce qu'il montre d'après un drapeau renvoyé par l'API finit par croire que
    c'est une garantie ; la garantie est au serveur. Même parti que FoyerOS, où
    l'omission de ces deux champs porte un test de régression dédié.
    """

    nom_affiche = serializers.SerializerMethodField()
    # Le compte vient-il du service d'identité commun à la suite ? Exposé plutôt
    # qu'écrit en dur dans l'écran : `IDENTITE_AUTORITE` est un interrupteur, et
    # une interface qui annoncerait un partage inexistant serait fausse la
    # moitié du temps.
    identite_partagee = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "nom_affiche",
            "identite_partagee",
        )
        read_only_fields = fields

    def get_identite_partagee(self, utilisateur):
        from django.conf import settings

        return bool(settings.IDENTITE_AUTORITE)

    def get_nom_affiche(self, utilisateur):
        return utilisateur.get_full_name() or utilisateur.get_username()
