from rest_framework import serializers
from .models import Compte


class CompteSerializer(serializers.ModelSerializer):
    # Champs calculés — lecture seule, erreur 400 si tentative d'écriture
    solde_theorique = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    solde_reel = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    ecart_solde = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    # Représentations lisibles des FK — code ET libellé
    type_compte_code = serializers.CharField(
        source="type_compte.code", read_only=True
    )
    type_compte_libelle = serializers.CharField(
        source="type_compte.libelle", read_only=True
    )
    titulaire_code = serializers.CharField(
        source="titulaire.code", read_only=True
    )
    titulaire_libelle = serializers.CharField(
        source="titulaire.libelle", read_only=True
    )
    etablissement_libelle = serializers.CharField(
        source="etablissement.libelle", read_only=True
    )
    devise_symbole = serializers.CharField(
        source="devise.symbole", read_only=True
    )

    class Meta:
        model = Compte
        fields = [
            "id",
            "code",
            "nom",
            "type_compte",
            "type_compte_code",
            "type_compte_libelle",
            "titulaire",
            "titulaire_code",
            "titulaire_libelle",
            "etablissement",
            "etablissement_libelle",
            "devise",
            "devise_symbole",
            "solde_initial",
            "solde_reel",
            "solde_theorique",   # read_only
            "ecart_solde",       # read_only
            "actif",
            "est_commun",
            "date_ouverture",
            "date_fermeture",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "solde_theorique",
            "solde_reel",
            "ecart_solde",
            "created_at",
            "updated_at",
        ]

    def validate_code(self, code):
        """
        Unicité du code y compris contre les comptes soft-deletés
        (la contrainte en base les compte aussi → éviter un 500 IntegrityError).
        """
        qs = Compte.objects.all_with_deleted().filter(code=code)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError(
                "Ce code est déjà utilisé (éventuellement par un compte supprimé)."
            )
        return code

    def validate(self, data):
        champs_interdits = {"solde_theorique", "solde_reel", "ecart_solde"}
        tentatives = champs_interdits & set(self.initial_data.keys())
        if tentatives:
            raise serializers.ValidationError(
                {champ: "Ce champ est calculé et non modifiable." for champ in tentatives}
            )
        return data