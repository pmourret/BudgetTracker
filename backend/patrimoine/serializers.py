from rest_framework import serializers
from .models import Actif


class ActifSerializer(serializers.ModelSerializer):
    type_actif_display = serializers.CharField(
        source="get_type_actif_display", read_only=True
    )
    fiscalite_libelle = serializers.CharField(
        source="fiscalite.libelle", read_only=True
    )
    devise_symbole = serializers.CharField(
        source="devise.symbole", read_only=True
    )
    compte_associe_nom = serializers.CharField(
        source="compte_associe.nom", read_only=True
    )
    frequence_valorisation_libelle = serializers.CharField(
        source="frequence_valorisation.libelle", read_only=True
    )

    # Propriétés calculées
    plus_value_latente = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    est_valorise_recemment = serializers.BooleanField(read_only=True)
    date_prochaine_valorisation = serializers.DateField(read_only=True)
    valorisation_a_faire = serializers.BooleanField(read_only=True)

    class Meta:
        model = Actif
        fields = [
            "id",
            "nom",
            "type_actif",
            "type_actif_display",
            "compte_associe",
            "compte_associe_nom",
            "fiscalite",
            "fiscalite_libelle",
            "devise",
            "devise_symbole",
            "valeur_acquisition",
            "valeur_actuelle",
            "date_valorisation",
            "frequence_valorisation",
            "frequence_valorisation_libelle",
            "rappel_jours_avant",
            "date_prochaine_valorisation",  # read_only
            "valorisation_a_faire",         # read_only
            "plus_value_latente",           # read_only
            "est_valorise_recemment",       # read_only
            "actif",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "plus_value_latente",
            "est_valorise_recemment",
            "date_prochaine_valorisation",
            "valorisation_a_faire",
            "created_at",
            "updated_at",
        ]

    def validate_valeur_actuelle(self, valeur):
        if valeur < 0:
            raise serializers.ValidationError(
                "La valeur actuelle ne peut pas être négative."
            )
        return valeur

    def validate_valeur_acquisition(self, valeur):
        if valeur is not None and valeur < 0:
            raise serializers.ValidationError(
                "La valeur d'acquisition ne peut pas être négative."
            )
        return valeur


class ValorisationInputSerializer(serializers.Serializer):
    """Serializer pour l'action de mise à jour de valorisation."""
    valeur = serializers.DecimalField(max_digits=14, decimal_places=2)

    def validate_valeur(self, valeur):
        if valeur < 0:
            raise serializers.ValidationError(
                "La valeur ne peut pas être négative."
            )
        return valeur


class PatrimoineTotalSerializer(serializers.Serializer):
    """Serializer pour le résultat de calculer_patrimoine_total."""
    total_estime = serializers.DecimalField(max_digits=14, decimal_places=2)
    plus_value_latente_globale_estimee = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    par_type = serializers.DictField()
    fiabilite = serializers.CharField()
    avertissement = serializers.CharField()