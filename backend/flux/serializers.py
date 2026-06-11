from rest_framework import serializers
from .models import Flux


class FluxSerializer(serializers.ModelSerializer):
    # Représentations lisibles
    compte_nom = serializers.CharField(source="compte.nom", read_only=True)
    categorie_nom = serializers.CharField(source="categorie.nom", read_only=True)
    type_flux_code = serializers.CharField(source="type_flux.code", read_only=True)
    statut_code = serializers.CharField(source="statut.code", read_only=True)
    devise_symbole = serializers.CharField(source="devise.symbole", read_only=True)

    # Champ calculé — jamais éditable
    mois = serializers.DateField(read_only=True)

    class Meta:
        model = Flux
        fields = [
            "id",
            "compte",
            "compte_nom",
            "categorie",
            "categorie_nom",
            "type_flux",
            "type_flux_code",
            "statut",
            "statut_code",
            "titulaire",
            "mode_paiement",
            "devise",
            "devise_symbole",
            "montant",
            "date_flux",
            "mois",           # read_only
            "est_transfert",
            "est_ajustement",
            "libelle",
            "notes",
            "reference_externe",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "mois", "est_ajustement", "created_at", "updated_at"]

    def validate_montant(self, montant):
        """Le montant ne peut pas être nul."""
        if montant == 0:
            raise serializers.ValidationError("Le montant ne peut pas être zéro.")
        return montant

    def validate(self, data):
        """
        Un flux non-transfert doit avoir une catégorie.
        Un flux de transfert ne doit pas être créé directement via ce serializer
        — il passe par le service TransfertSerializer.
        """
        est_transfert = data.get("est_transfert", False)
        categorie = data.get("categorie", None)

        if not est_transfert and categorie is None:
            raise serializers.ValidationError(
                {"categorie": "Une catégorie est obligatoire pour un flux non-transfert."}
            )
        return data